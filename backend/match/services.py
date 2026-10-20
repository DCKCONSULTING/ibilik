from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.authorization import (
    accessible_properties,
    can_access_property,
    get_role,
    has_global_property_access,
    is_superuser,
    user_has_permission,
)
from accounts.catalog import ROLE_LEVELS, ROLE_STAFF, ROLE_SUPERUSER
from accounts.models import Property
from accounts.serializers import display_name
from cases.services import CaseError, parse_date_bound
from crm.access import can_access_customer
from crm.models import Customer
from match.access import accessible_requests
from match.errors import MatchError
from match.history import log_history
from match.assignment import assign_request_automatically
from match.models import (
    OPEN_STATUSES,
    MatchAssignmentMethod,
    MatchHistoryAction,
    MatchRequest,
    MatchRequestNote,
    MatchRequestPriority,
    MatchRequestStatus,
    MatchRequestType,
)
from match.numbering import allocate_request_number
from match.permissions import (
    ADD_NOTES,
    ASSIGN,
    CHANGE_PRIORITY,
    CHANGE_STATUS,
    DELETE,
    REASSIGN,
    RESOLVE,
    UNASSIGN,
)

ALLOWED_ORDERING = {
    "created_at",
    "-created_at",
    "updated_at",
    "-updated_at",
    "due_at",
    "-due_at",
    "priority",
    "-priority",
    "status",
    "-status",
    "request_number",
    "-request_number",
}

CLOSED_STATUSES = {MatchRequestStatus.RESOLVED, MatchRequestStatus.CANCELLED}


def request_queryset():
    return MatchRequest.objects.select_related(
        "customer",
        "property",
        "location",
        "related_case",
        "related_quote",
        "related_payment",
        "assigned_to",
        "assigned_by",
        "created_by",
    )


def require_permission(user, permission: str):
    if is_superuser(user) or user_has_permission(user, permission):
        return
    raise MatchError("You do not have permission to perform this action.", code="permission_denied")


def _parse_int(value, *, field: str, code: str):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise MatchError(f"{field} must be an integer.", code=code) from exc


def resolve_customer(customer_id, user) -> Customer:
    if customer_id in (None, ""):
        raise MatchError("customer_id is required.", code="invalid_customer")
    customer = Customer.objects.filter(pk=_parse_int(customer_id, field="customer_id", code="invalid_customer")).first()
    if customer is None:
        raise MatchError("Customer not found.", code="unknown_customer")
    if not can_access_customer(user, customer):
        raise MatchError("You do not have access to this customer.", code="property_forbidden")
    return customer


def resolve_property(property_id, user) -> Property | None:
    if property_id in (None, ""):
        return None
    property_obj = Property.objects.filter(pk=_parse_int(property_id, field="property_id", code="invalid_property")).first()
    if property_obj is None:
        raise MatchError("Unknown property.", code="unknown_property")
    if not can_access_property(user, property_obj):
        raise MatchError("You do not have access to this property.", code="property_forbidden")
    return property_obj


def actor_level(user) -> int:
    if is_superuser(user):
        return ROLE_LEVELS[ROLE_SUPERUSER]
    role = get_role(user)
    return ROLE_LEVELS.get(role, ROLE_LEVELS[ROLE_STAFF])


def can_assign_to(actor, assignee: User, *, property_obj=None) -> bool:
    if not assignee.is_active:
        return False
    if is_superuser(actor):
        return True
    if property_obj is not None and not can_access_property(assignee, property_obj):
        return False
    if property_obj is None and not has_global_property_access(assignee) and not has_global_property_access(actor):
        actor_ids = set(accessible_properties(actor).values_list("pk", flat=True))
        assignee_ids = set(accessible_properties(assignee).values_list("pk", flat=True))
        if actor_ids and assignee_ids.isdisjoint(actor_ids) and not has_global_property_access(assignee):
            return False
    if is_superuser(assignee) and not is_superuser(actor):
        return False
    return actor_level(actor) <= actor_level(assignee)


def assignable_staff(actor, *, request: MatchRequest | None = None, property_obj=None):
    property_to_use = property_obj
    if request is not None and request.property is not None:
        property_to_use = request.property

    queryset = User.objects.filter(is_active=True).exclude(is_superuser=True)
    if is_superuser(actor):
        queryset = User.objects.filter(is_active=True)

    if property_to_use is not None:
        if has_global_property_access(actor) or is_superuser(actor):
            queryset = queryset.filter(
                Q(assigned_properties=property_to_use) | Q(property_access_profile__mode="GLOBAL") | Q(is_superuser=True)
            )
        else:
            queryset = queryset.filter(assigned_properties=property_to_use)
    else:
        property_ids = accessible_properties(actor).values("pk")
        if not (is_superuser(actor) or has_global_property_access(actor)):
            queryset = queryset.filter(Q(assigned_properties__in=property_ids) | Q(property_access_profile__mode="GLOBAL"))

    users = list(queryset.distinct().select_related("property_access_profile").prefetch_related("assigned_properties"))
    allowed = [user for user in users if can_assign_to(actor, user, property_obj=property_to_use)]
    allowed.sort(key=lambda user: (display_name(user).lower(), user.username.lower(), user.pk))
    return allowed


def resolve_assignee(user_id, *, actor, request: MatchRequest | None = None, property_obj=None) -> User:
    if user_id in (None, ""):
        raise MatchError("assigned_to_id is required.", code="invalid_assignee")
    assignee = User.objects.filter(pk=_parse_int(user_id, field="assigned_to_id", code="invalid_assignee")).first()
    if assignee is None:
        raise MatchError("Assigned user not found.", code="unknown_assignee")
    if not assignee.is_active:
        raise MatchError("That staff member is inactive.", code="inactive_assignee")
    target_property = request.property if request is not None else property_obj
    if not can_assign_to(actor, assignee, property_obj=target_property):
        raise MatchError("You cannot assign this request to that staff member.", code="assignment_forbidden")
    return assignee


def validate_status(value) -> str:
    status = str(value or "").strip().lower()
    if status not in MatchRequestStatus.values:
        raise MatchError("Unknown request status.", code="invalid_status")
    return status


def validate_priority(value) -> str:
    priority = str(value or "").strip().lower()
    if priority not in MatchRequestPriority.values:
        raise MatchError("Unknown request priority.", code="invalid_priority")
    return priority


def validate_type(value) -> str:
    request_type = str(value or "").strip().lower()
    if request_type not in MatchRequestType.values:
        raise MatchError("Unknown request type.", code="invalid_type")
    return request_type


def _parse_due_at(value):
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        return value
    parsed = parse_datetime(str(value))
    if parsed is None:
        raise MatchError("due_at must be a valid datetime.", code="invalid_due_at")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


@transaction.atomic
def create_request(*, actor, payload: dict) -> MatchRequest:
    subject = str(payload.get("subject") or payload.get("title") or "").strip()
    if not subject:
        raise MatchError("subject is required.", code="invalid_subject")
    customer = resolve_customer(payload.get("customer_id"), actor)
    property_obj = resolve_property(payload.get("property_id"), actor)
    if property_obj is None and customer.property_id:
        property_obj = customer.property
        if property_obj is not None and not can_access_property(actor, property_obj):
            property_obj = None
    source_module = str(payload.get("source_module") or "match").strip() or "match"
    source_ref = str(payload.get("source_ref") or "").strip()
    if not source_ref:
        source_ref = f"manual:{timezone.now().timestamp()}:{actor.pk if actor is not None else 0}"
    existing = MatchRequest.objects.filter(source_module=source_module, source_ref=source_ref).first()
    if existing is not None:
        return existing
    sequence, request_number = allocate_request_number()
    request = MatchRequest(
        sequence=sequence,
        request_number=request_number,
        request_type=validate_type(payload.get("request_type") or MatchRequestType.OTHER),
        source_module=source_module,
        source_ref=source_ref,
        customer=customer,
        property=property_obj,
        subject=subject[:255],
        description=str(payload.get("description") or ""),
        priority=validate_priority(payload.get("priority") or MatchRequestPriority.NORMAL),
        status=MatchRequestStatus.NEW,
        due_at=_parse_due_at(payload.get("due_at")),
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    if payload.get("related_case_id") not in (None, ""):
        from cases.models import Case

        request.related_case_id = _parse_int(payload.get("related_case_id"), field="related_case_id", code="invalid_case")
        if not Case.objects.filter(pk=request.related_case_id).exists():
            raise MatchError("Related case not found.", code="unknown_case")
    try:
        request.save()
    except IntegrityError:
        existing = MatchRequest.objects.filter(source_module=source_module, source_ref=source_ref).first()
        if existing is not None:
            return existing
        raise
    log_history(request, MatchHistoryAction.CREATED, actor=actor, new_value=request.request_number)
    return assign_request_automatically(request, actor=actor)


def ensure_match_request(
    *,
    source_module: str,
    source_ref: str,
    request_type: str,
    subject: str,
    description: str = "",
    customer=None,
    property_obj=None,
    location=None,
    related_case=None,
    related_quote=None,
    related_payment=None,
    priority: str = MatchRequestPriority.NORMAL,
    actor=None,
) -> tuple[MatchRequest, bool]:
    existing = MatchRequest.objects.filter(source_module=source_module, source_ref=source_ref).first()
    if existing is not None:
        return existing, False
    sequence, request_number = allocate_request_number()
    request = MatchRequest(
        sequence=sequence,
        request_number=request_number,
        request_type=request_type,
        source_module=source_module,
        source_ref=source_ref,
        customer=customer,
        property=property_obj,
        location=location,
        related_case=related_case,
        related_quote=related_quote,
        related_payment=related_payment,
        subject=(subject or "Incoming request")[:255],
        description=description or "",
        priority=priority if priority in MatchRequestPriority.values else MatchRequestPriority.NORMAL,
        status=MatchRequestStatus.NEW,
        created_by=actor if actor is not None and getattr(actor, "is_authenticated", False) else None,
    )
    try:
        request.save()
    except IntegrityError:
        existing = MatchRequest.objects.filter(source_module=source_module, source_ref=source_ref).first()
        if existing is not None:
            return existing, False
        raise
    log_history(request, MatchHistoryAction.CREATED, actor=actor, new_value=request.request_number)
    request = assign_request_automatically(request, actor=actor)
    return request, True


def _apply_assignment(
    request: MatchRequest,
    assignee: User | None,
    *,
    actor,
    action: str,
    method: str = "",
    workload: int | None = None,
):
    previous = display_name(request.assigned_to) if request.assigned_to else "Unassigned"
    request.assigned_to = assignee
    request.assigned_by = actor if actor is not None and getattr(actor, "is_authenticated", False) else None
    request.assigned_at = timezone.now() if assignee is not None else None
    request.assignment_method = method if assignee is not None else ""
    request.workload_at_assignment = workload if assignee is not None else None
    request.unassigned_reason = ""
    if assignee is None:
        if request.status not in CLOSED_STATUSES:
            request.status = MatchRequestStatus.UNASSIGNED
        new_value = "Unassigned"
    else:
        if request.status in {MatchRequestStatus.NEW, MatchRequestStatus.UNASSIGNED}:
            request.status = MatchRequestStatus.ASSIGNED
        label = display_name(assignee)
        if method == MatchAssignmentMethod.AUTOMATIC and workload is not None:
            new_value = f"{label} (automatic, workload {workload})"
        elif method:
            new_value = f"{label} ({method})"
        else:
            new_value = label
    request.save()
    log_history(request, action, actor=actor, previous_value=previous, new_value=new_value)
    return request


def assign_request(request: MatchRequest, *, actor, assigned_to_id) -> MatchRequest:
    require_permission(actor, ASSIGN)
    if request.assigned_to_id:
        raise MatchError("This request is already assigned. Use reassign instead.", code="already_assigned")
    assignee = resolve_assignee(assigned_to_id, actor=actor, request=request)
    return _apply_assignment(
        request,
        assignee,
        actor=actor,
        action=MatchHistoryAction.ASSIGNED,
        method=MatchAssignmentMethod.MANUAL,
        workload=active_workload_for(assignee.pk),
    )


def reassign_request(request: MatchRequest, *, actor, assigned_to_id) -> MatchRequest:
    require_permission(actor, REASSIGN)
    if not request.assigned_to_id:
        raise MatchError("This request is not assigned. Use assign instead.", code="not_assigned")
    assignee = resolve_assignee(assigned_to_id, actor=actor, request=request)
    if assignee.pk == request.assigned_to_id:
        return request
    return _apply_assignment(
        request,
        assignee,
        actor=actor,
        action=MatchHistoryAction.REASSIGNED,
        method=MatchAssignmentMethod.REASSIGNED,
        workload=active_workload_for(assignee.pk),
    )


def unassign_request(request: MatchRequest, *, actor) -> MatchRequest:
    require_permission(actor, UNASSIGN)
    if not request.assigned_to_id:
        return request
    return _apply_assignment(request, None, actor=actor, action=MatchHistoryAction.UNASSIGNED)


def active_workload_for(user_id: int) -> int:
    from match.assignment import active_workload

    return active_workload(user_id)


def change_status(request: MatchRequest, status: str, *, actor, resolution_notes: str | None = None) -> MatchRequest:
    next_status = validate_status(status)
    if next_status == MatchRequestStatus.RESOLVED:
        require_permission(actor, RESOLVE)
    elif next_status == MatchRequestStatus.CANCELLED:
        require_permission(actor, CHANGE_STATUS)
    else:
        require_permission(actor, CHANGE_STATUS)
    if next_status == request.status:
        return request
    previous = request.get_status_display()
    request.status = next_status
    if next_status == MatchRequestStatus.RESOLVED:
        if resolution_notes not in (None, ""):
            request.resolution_notes = str(resolution_notes)
        action = MatchHistoryAction.RESOLVED
    elif next_status == MatchRequestStatus.CANCELLED:
        if resolution_notes not in (None, ""):
            request.resolution_notes = str(resolution_notes)
        action = MatchHistoryAction.CANCELLED
    else:
        action = MatchHistoryAction.STATUS_CHANGED
    if next_status == MatchRequestStatus.UNASSIGNED:
        request.assigned_to = None
        request.assigned_at = None
        request.assignment_method = ""
        request.workload_at_assignment = None
    request.save()
    log_history(request, action, actor=actor, previous_value=previous, new_value=request.get_status_display())
    return request


def change_priority(request: MatchRequest, priority: str, *, actor) -> MatchRequest:
    require_permission(actor, CHANGE_PRIORITY)
    next_priority = validate_priority(priority)
    if next_priority == request.priority:
        return request
    previous = request.get_priority_display()
    request.priority = next_priority
    request.save(update_fields=["priority", "updated_at"])
    log_history(
        request,
        MatchHistoryAction.PRIORITY_CHANGED,
        actor=actor,
        previous_value=previous,
        new_value=request.get_priority_display(),
    )
    return request


def add_note(request: MatchRequest, body: str, *, actor) -> MatchRequestNote:
    require_permission(actor, ADD_NOTES)
    text = str(body or "").strip()
    if not text:
        raise MatchError("note is required.", code="invalid_note")
    note = MatchRequestNote.objects.create(
        request=request,
        body=text,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    existing = request.internal_notes.strip()
    request.internal_notes = f"{existing}\n{text}".strip() if existing else text
    request.save(update_fields=["internal_notes", "updated_at"])
    preview = text if len(text) <= 80 else f"{text[:77]}..."
    log_history(request, MatchHistoryAction.NOTE_ADDED, actor=actor, new_value=preview)
    return note


def update_request(request: MatchRequest, payload: dict, *, actor) -> MatchRequest:
    if "status" in payload:
        request = change_status(request, payload.get("status"), actor=actor, resolution_notes=payload.get("resolution_notes"))
    if "priority" in payload:
        request = change_priority(request, payload.get("priority"), actor=actor)
    if "due_at" in payload:
        request.due_at = _parse_due_at(payload.get("due_at"))
        request.save(update_fields=["due_at", "updated_at"])
    if "resolution_notes" in payload and "status" not in payload:
        request.resolution_notes = str(payload.get("resolution_notes") or "")
        request.save(update_fields=["resolution_notes", "updated_at"])
    return request


def delete_request(request: MatchRequest, *, actor) -> None:
    require_permission(actor, DELETE)
    request.delete()


def filter_requests(queryset, params):
    status = (params.get("status") or "all").strip().lower()
    if status not in {"", "all"}:
        if status == "open":
            queryset = queryset.filter(status__in=OPEN_STATUSES)
        elif status == "unassigned":
            queryset = queryset.filter(assigned_to__isnull=True).exclude(status__in=CLOSED_STATUSES)
        elif status in MatchRequestStatus.values:
            queryset = queryset.filter(status=status)
        else:
            raise MatchError("Unknown request status.", code="invalid_status")

    if str(params.get("unassigned") or params.get("unassigned_only") or "").strip().lower() in {"1", "true", "yes"}:
        queryset = queryset.filter(assigned_to__isnull=True).exclude(status__in=CLOSED_STATUSES)

    request_type = (params.get("type") or params.get("request_type") or "all").strip().lower()
    if request_type not in {"", "all"}:
        if request_type not in MatchRequestType.values:
            raise MatchError("Unknown request type.", code="invalid_type")
        queryset = queryset.filter(request_type=request_type)

    priority = (params.get("priority") or "all").strip().lower()
    if priority not in {"", "all"}:
        if priority not in MatchRequestPriority.values:
            raise MatchError("Unknown request priority.", code="invalid_priority")
        queryset = queryset.filter(priority=priority)

    property_id = params.get("property")
    if property_id not in (None, "", "all"):
        queryset = queryset.filter(property_id=_parse_int(property_id, field="property", code="invalid_property"))

    staff = params.get("staff") or params.get("assigned_staff")
    if staff not in (None, "", "all"):
        if str(staff).strip().lower() == "unassigned":
            queryset = queryset.filter(assigned_to__isnull=True)
        else:
            queryset = queryset.filter(assigned_to_id=_parse_int(staff, field="staff", code="invalid_assignee"))

    date_field = (params.get("date_field") or "created_at").strip()
    field_map = {
        "created_at": "created_at",
        "created": "created_at",
        "updated_at": "updated_at",
        "updated": "updated_at",
        "due_at": "due_at",
        "due": "due_at",
        "assigned_at": "assigned_at",
    }
    if date_field not in field_map:
        raise MatchError("Unknown date field.", code="invalid_date_field")
    lookup = field_map[date_field]
    due = (params.get("due") or params.get("date") or "all").strip().lower()
    if due not in {"", "all"}:
        now = timezone.now()
        local = timezone.localtime(now)
        start_today = local.replace(hour=0, minute=0, second=0, microsecond=0)
        if due == "today":
            queryset = queryset.filter(**{f"{lookup}__gte": start_today, f"{lookup}__lt": start_today + timedelta(days=1)})
        elif due == "this_week":
            week_start = start_today - timedelta(days=local.weekday())
            queryset = queryset.filter(**{f"{lookup}__gte": week_start, f"{lookup}__lt": week_start + timedelta(days=7)})
        elif due == "overdue":
            queryset = queryset.filter(due_at__lt=now, status__in=OPEN_STATUSES)
        elif due == "custom":
            try:
                date_from = parse_date_bound(params.get("date_from") or params.get("due_from") or params.get("created_from"))
                date_to = parse_date_bound(params.get("date_to") or params.get("due_to") or params.get("created_to"), end=True)
            except CaseError as exc:
                raise MatchError(str(exc), code=getattr(exc, "code", "invalid_date")) from exc
            if date_from is not None:
                queryset = queryset.filter(**{f"{lookup}__gte": date_from})
            if date_to is not None:
                queryset = queryset.filter(**{f"{lookup}__lte": date_to})
        else:
            raise MatchError("Unknown date filter.", code="invalid_date")
    else:
        try:
            date_from = parse_date_bound(params.get("date_from") or params.get("created_from"))
            date_to = parse_date_bound(params.get("date_to") or params.get("created_to"), end=True)
        except CaseError as exc:
            raise MatchError(str(exc), code=getattr(exc, "code", "invalid_date")) from exc
        if date_from is not None:
            queryset = queryset.filter(**{f"{lookup}__gte": date_from})
        if date_to is not None:
            queryset = queryset.filter(**{f"{lookup}__lte": date_to})

    search = (params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(request_number__icontains=search)
            | Q(subject__icontains=search)
            | Q(description__icontains=search)
            | Q(customer__name__icontains=search)
            | Q(customer__email__icontains=search)
            | Q(customer__phone__icontains=search)
            | Q(property__name__icontains=search)
            | Q(related_case__case_number__icontains=search)
            | Q(related_quote__quote_number__icontains=search)
            | Q(related_payment__payment_number__icontains=search)
        )
    return queryset


def order_requests(queryset, params):
    ordering = (params.get("ordering") or params.get("sort") or "-created_at").strip()
    if ordering not in ALLOWED_ORDERING:
        raise MatchError("Unknown sort field.", code="invalid_ordering")
    field = ordering.lstrip("-")
    descending = ordering.startswith("-")
    expression = F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_last=True)
    return queryset.order_by(expression, "-id" if descending else "id")


def request_summary(queryset) -> dict:
    open_qs = queryset.filter(status__in=OPEN_STATUSES)
    counts = {row["status"]: row["total"] for row in queryset.values("status").annotate(total=Count("id"))}
    return {
        "new": int(counts.get(MatchRequestStatus.NEW, 0)),
        "unassigned": int(open_qs.filter(assigned_to__isnull=True).count()),
        "assigned": int(open_qs.filter(assigned_to__isnull=False).count()),
        "in_progress": int(counts.get(MatchRequestStatus.IN_PROGRESS, 0)),
        "urgent": int(open_qs.filter(priority=MatchRequestPriority.URGENT).count()),
        "resolved": int(counts.get(MatchRequestStatus.RESOLVED, 0)),
        "new_unassigned_count": int(
            queryset.filter(
                assigned_to__isnull=True,
                status__in={MatchRequestStatus.NEW, MatchRequestStatus.UNASSIGNED},
            ).count()
        ),
    }


def filter_staff(user):
    property_ids = accessible_properties(user).values("pk")
    assigned_ids = accessible_requests(user).exclude(assigned_to=None).values_list("assigned_to_id", flat=True)
    return (
        User.objects.filter(is_active=True)
        .filter(Q(assigned_properties__in=property_ids) | Q(pk__in=assigned_ids) | Q(property_access_profile__mode="GLOBAL"))
        .distinct()
        .order_by("first_name", "last_name", "username")
    )


def filter_properties(user):
    return accessible_properties(user).order_by("name", "id")


@transaction.atomic
def update_match_settings(*, actor, payload: dict):
    from match.assignment import get_match_settings

    if not (
        is_superuser(actor)
        or user_has_permission(actor, ASSIGN)
        or user_has_permission(actor, "settings.change_setting")
    ):
        raise MatchError("You do not have permission to change Match settings.", code="permission_denied")
    settings = get_match_settings(lock=True)
    if "auto_assign_enabled" in payload:
        settings.auto_assign_enabled = bool(payload.get("auto_assign_enabled"))
    if "property_staff_only" in payload:
        settings.property_staff_only = bool(payload.get("property_staff_only"))
    if "org_wide_when_no_property" in payload:
        settings.org_wide_when_no_property = bool(payload.get("org_wide_when_no_property"))
    settings.assignment_mode = "lowest_workload"
    settings.save()
    return settings
