from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import User
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.authorization import can_access_property
from accounts.models import Property
from accounts.serializers import display_name
from cases.access import accessible_follow_ups, can_access_case
from cases.activity import log_activity, log_assigned, log_created
from cases.models import (
    ActivityEvent,
    Case,
    CaseFollowUp,
    FollowUpStatus,
    FollowUpType,
)
from cases.numbering import allocate_case_number, link_conversation
from crm.models import Customer
from pipeline.models import PIPELINE_STAGE_ORDER, PipelineStage


class CaseError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_payload"):
        super().__init__(message)
        self.code = code


# Compatibility for pipeline imports.
PipelineError = CaseError


def stage_values() -> set[str]:
    return set(PipelineStage.values)


def validate_stage(value) -> str:
    if value in (None, ""):
        return PipelineStage.NEW
    stage = str(value).strip().lower()
    if stage not in stage_values():
        raise CaseError("Unknown pipeline stage.", code="invalid_stage")
    return stage


def _parse_value(value):
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CaseError("value must be a valid number.", code="invalid_value") from exc
    if amount < 0:
        raise CaseError("value cannot be negative.", code="invalid_value")
    return amount


def resolve_customer(customer_id, user) -> Customer:
    if customer_id in (None, ""):
        raise CaseError("customer_id is required.", code="invalid_customer")
    try:
        customer = Customer.objects.filter(pk=int(customer_id)).first()
    except (TypeError, ValueError) as exc:
        raise CaseError("customer_id must be an integer.", code="invalid_customer") from exc
    if customer is None:
        raise CaseError("Customer not found.", code="unknown_customer")
    from crm.access import can_access_customer

    if not can_access_customer(user, customer):
        raise CaseError("You do not have access to this customer.", code="property_forbidden")
    return customer


def resolve_property(property_id, user) -> Property | None:
    if property_id in (None, ""):
        return None
    try:
        property_obj = Property.objects.filter(pk=int(property_id)).first()
    except (TypeError, ValueError) as exc:
        raise CaseError("property_id must be an integer.", code="invalid_property") from exc
    if property_obj is None:
        raise CaseError("Unknown property.", code="unknown_property")
    if not can_access_property(user, property_obj):
        raise CaseError("You do not have access to this property.", code="property_forbidden")
    return property_obj


def resolve_assignee(user_id, *, case: Case | None = None, property_obj=None, actor=None) -> User | None:
    if user_id in (None, ""):
        return None
    try:
        assignee = User.objects.filter(pk=int(user_id), is_active=True).first()
    except (TypeError, ValueError) as exc:
        raise CaseError("assigned_to_id must be an integer.", code="invalid_assignee") from exc
    if assignee is None:
        raise CaseError("Assigned user not found.", code="unknown_assignee")
    property_to_check = case.property if case is not None else property_obj
    if property_to_check is not None and not can_access_property(assignee, property_to_check):
        raise CaseError("That staff member cannot access this property.", code="property_forbidden")
    return assignee


def _request_text(payload: dict, conversation=None) -> str:
    explicit = str(payload.get("original_request") or payload.get("request") or "").strip()
    if explicit:
        return explicit
    if conversation is not None and conversation.last_message_preview:
        return conversation.last_message_preview
    return str(payload.get("description") or "").strip()


def create_case(*, actor, payload: dict) -> Case:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise CaseError("title is required.", code="invalid_title")
    customer = resolve_customer(payload.get("customer_id"), actor)
    property_obj = resolve_property(payload.get("property_id"), actor)
    if property_obj is None and customer.property_id:
        property_obj = customer.property
        if property_obj is not None and not can_access_property(actor, property_obj):
            property_obj = None
    conversation = None
    conversation_id = payload.get("conversation_id")
    if conversation_id not in (None, ""):
        from crm.models import Conversation

        conversation = Conversation.objects.filter(pk=int(conversation_id)).first()
    sequence, case_number = allocate_case_number()
    original_request = _request_text(payload, conversation)
    source = str(payload.get("source") or (conversation.channel if conversation is not None else "")).strip()
    case = Case.objects.create(
        sequence=sequence,
        case_number=case_number,
        customer=customer,
        property=property_obj,
        originating_conversation=conversation,
        title=title,
        description=str(payload.get("description") or original_request),
        original_request=original_request,
        source=source,
        stage=validate_stage(payload.get("stage")),
        value=_parse_value(payload.get("value")),
        assigned_to=resolve_assignee(payload.get("assigned_to_id"), property_obj=property_obj, actor=actor),
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        external_key=str(payload.get("external_key") or ""),
    )
    if conversation is not None:
        link_conversation(case, conversation, originating=True)
    log_created(case, actor=actor)
    if case.assigned_to_id:
        log_assigned(case, actor=actor)
    return case


def create_opportunity(*, actor, payload: dict) -> Case:
    return create_case(actor=actor, payload=payload)


def update_case(case: Case, payload: dict, *, actor) -> Case:
    previous_assignee = case.assigned_to_id
    previous_property = case.property_id
    previous_stage = case.stage
    if "title" in payload:
        title = str(payload.get("title") or "").strip()
        if not title:
            raise CaseError("title is required.", code="invalid_title")
        case.title = title
    if "description" in payload:
        case.description = str(payload.get("description") or "")
    if "stage" in payload:
        case.stage = validate_stage(payload.get("stage"))
    if "value" in payload:
        case.value = _parse_value(payload.get("value"))
    if "customer_id" in payload:
        case.customer = resolve_customer(payload.get("customer_id"), actor)
    if "property_id" in payload:
        case.property = resolve_property(payload.get("property_id"), actor)
    if "assigned_to_id" in payload:
        case.assigned_to = resolve_assignee(payload.get("assigned_to_id"), case=case, actor=actor)
    if "staff_notes" in payload:
        case.staff_notes = str(payload.get("staff_notes") or "")
    if "quote_notes" in payload:
        case.quote_notes = str(payload.get("quote_notes") or "")
    case.save()
    if previous_assignee != case.assigned_to_id:
        log_assigned(case, actor=actor)
    if previous_property != case.property_id:
        name = case.property.name if case.property else "none"
        log_activity(case, ActivityEvent.PROPERTY_CHANGED, f"Property changed to {name}.", actor=actor)
    if previous_stage != case.stage:
        log_activity(
            case,
            ActivityEvent.STAGE_CHANGED,
            f"Moved from {PipelineStage(previous_stage).label} → {PipelineStage(case.stage).label}.",
            actor=actor,
        )
        if case.stage in {PipelineStage.WON, PipelineStage.LOST} and case.closed_at is None:
            case.closed_at = timezone.now()
            case.save(update_fields=["closed_at", "updated_at"])
            log_activity(case, ActivityEvent.CLOSED, "Case closed.", actor=actor)
        from quotes.services import sync_quote_for_stage

        sync_quote_for_stage(case)
    if "staff_notes" in payload and payload.get("staff_notes"):
        log_activity(case, ActivityEvent.NOTE_ADDED, "Note added.", actor=actor)
    return case


def update_opportunity(opportunity: Case, payload: dict, *, actor) -> Case:
    return update_case(opportunity, payload, actor=actor)


def update_case_stage(case: Case, stage) -> Case:
    previous = case.stage
    case.stage = validate_stage(stage)
    update_fields = ["stage", "updated_at"]
    if case.stage in {PipelineStage.WON, PipelineStage.LOST} and case.closed_at is None:
        case.closed_at = timezone.now()
        update_fields.append("closed_at")
    case.save(update_fields=update_fields)
    if previous != case.stage:
        log_activity(
            case,
            ActivityEvent.STAGE_CHANGED,
            f"Moved from {PipelineStage(previous).label} → {PipelineStage(case.stage).label}.",
        )
        from quotes.services import sync_quote_for_stage

        sync_quote_for_stage(case)
    return case


def update_opportunity_stage(opportunity: Case, stage) -> Case:
    return update_case_stage(opportunity, stage)


def filter_cases(queryset, params):
    stage = params.get("stage")
    if stage:
        queryset = queryset.filter(stage=validate_stage(stage))

    customer_id = params.get("customer")
    if customer_id:
        try:
            queryset = queryset.filter(customer_id=int(customer_id))
        except (TypeError, ValueError) as exc:
            raise CaseError("customer must be an integer.", code="invalid_customer") from exc

    property_id = params.get("property")
    if property_id:
        try:
            queryset = queryset.filter(property_id=int(property_id))
        except (TypeError, ValueError) as exc:
            raise CaseError("property must be an integer.", code="invalid_property") from exc

    has_stay = (params.get("has_stay") or "").strip().lower()
    if has_stay in {"1", "true", "yes"}:
        queryset = queryset.filter(check_in__isnull=False)

    search = (params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(case_number__icontains=search)
            | Q(title__icontains=search)
            | Q(original_request__icontains=search)
            | Q(description__icontains=search)
            | Q(customer__name__icontains=search)
            | Q(customer__phone__icontains=search)
            | Q(customer__email__icontains=search)
            | Q(property__name__icontains=search)
        )
    return queryset


def filter_opportunities(queryset, params):
    return filter_cases(queryset, params)


def pipeline_summary(queryset) -> dict:
    counts = {stage: 0 for stage in PIPELINE_STAGE_ORDER}
    for row in queryset.values("stage").annotate(total=Count("id")):
        if row["stage"] in counts:
            counts[row["stage"]] = row["total"]
    open_stages = (
        PipelineStage.NEW,
        PipelineStage.QUALIFIED,
        PipelineStage.QUOTED,
        PipelineStage.NEGOTIATING,
    )
    total_value = queryset.exclude(stage=PipelineStage.LOST).aggregate(total=Sum("value"))["total"]
    open_value = queryset.filter(stage__in=open_stages).aggregate(total=Sum("value"))["total"]
    return {
        "stage_counts": {str(stage): int(total) for stage, total in counts.items()},
        "total_value": f"{total_value:.2f}" if total_value is not None else None,
        "open_value": f"{open_value:.2f}" if open_value is not None else None,
    }


def parse_due_at(value):
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        return value
    parsed = parse_datetime(str(value))
    if parsed is None:
        raise CaseError("due_at must be a valid datetime.", code="invalid_due_at")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def create_follow_up(case: Case, payload: dict, *, actor) -> CaseFollowUp:
    title = str(payload.get("title") or "").strip()
    follow_up_type = str(payload.get("type") or payload.get("follow_up_type") or FollowUpType.FOLLOW_UP).strip()
    if follow_up_type not in FollowUpType.values:
        raise CaseError("Unknown follow-up type.", code="invalid_follow_up_type")
    if not title:
        title = FollowUpType(follow_up_type).label
    assigned = case.assigned_to
    if "assigned_to_id" in payload:
        assigned = resolve_assignee(payload.get("assigned_to_id"), case=case, actor=actor)
    follow_up = CaseFollowUp.objects.create(
        case=case,
        follow_up_type=follow_up_type,
        title=title,
        description=str(payload.get("description") or ""),
        assigned_to=assigned,
        due_at=parse_due_at(payload.get("due_at")),
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    assignee = display_name(assigned) if assigned else "Unassigned"
    log_activity(case, ActivityEvent.FOLLOW_UP_CREATED, f"Follow-up created: {follow_up.title} ({assignee}).", actor=actor)
    return follow_up


def update_follow_up(follow_up: CaseFollowUp, payload: dict, *, actor) -> CaseFollowUp:
    previous_assignee = follow_up.assigned_to
    previous_due = follow_up.due_at
    previous_status = follow_up.status
    if "title" in payload:
        title = str(payload.get("title") or "").strip()
        if not title:
            raise CaseError("title is required.", code="invalid_title")
        follow_up.title = title
    if "description" in payload:
        follow_up.description = str(payload.get("description") or "")
    if "type" in payload or "follow_up_type" in payload:
        follow_up_type = str(payload.get("type") or payload.get("follow_up_type")).strip()
        if follow_up_type not in FollowUpType.values:
            raise CaseError("Unknown follow-up type.", code="invalid_follow_up_type")
        follow_up.follow_up_type = follow_up_type
    if "assigned_to_id" in payload:
        follow_up.assigned_to = resolve_assignee(payload.get("assigned_to_id"), case=follow_up.case, actor=actor)
    if "due_at" in payload:
        follow_up.due_at = parse_due_at(payload.get("due_at"))
    if "status" in payload:
        status = str(payload.get("status") or "").strip().lower()
        if status == "overdue":
            status = FollowUpStatus.PENDING
        if status not in FollowUpStatus.values:
            raise CaseError("Unknown follow-up status.", code="invalid_follow_up_status")
        follow_up.status = status
        if status == FollowUpStatus.COMPLETED and follow_up.completed_at is None:
            follow_up.completed_at = timezone.now()
        if status != FollowUpStatus.COMPLETED:
            follow_up.completed_at = follow_up.completed_at if status == FollowUpStatus.COMPLETED else None
    follow_up.save()
    if previous_assignee_id(previous_assignee) != follow_up.assigned_to_id:
        previous_name = display_name(previous_assignee) if previous_assignee else "Unassigned"
        next_name = display_name(follow_up.assigned_to) if follow_up.assigned_to else "Unassigned"
        log_activity(
            follow_up.case,
            ActivityEvent.FOLLOW_UP_REASSIGNED,
            f"Follow-up reassigned from {previous_name} to {next_name}.",
            actor=actor,
        )
    if previous_due != follow_up.due_at:
        log_activity(follow_up.case, ActivityEvent.FOLLOW_UP_RESCHEDULED, "Follow-up due date changed.", actor=actor)
    if previous_status != follow_up.status:
        if follow_up.status == FollowUpStatus.COMPLETED:
            complete_follow_up(follow_up, actor=actor, already_saved=True)
        elif follow_up.status == FollowUpStatus.CANCELLED:
            log_activity(
                follow_up.case,
                ActivityEvent.FOLLOW_UP_CANCELLED,
                f"Follow-up cancelled: {follow_up.title}.",
                actor=actor,
            )
    return follow_up


def previous_assignee_id(user) -> int | None:
    return user.pk if user is not None else None


def complete_follow_up(follow_up: CaseFollowUp, *, actor, already_saved: bool = False) -> CaseFollowUp:
    was_complete = follow_up.status == FollowUpStatus.COMPLETED and follow_up.completed_at is not None
    follow_up.status = FollowUpStatus.COMPLETED
    follow_up.completed_at = follow_up.completed_at or timezone.now()
    if not already_saved:
        follow_up.save(update_fields=["status", "completed_at", "updated_at"])
    if was_complete and not already_saved:
        return follow_up
    actor_label = display_name(actor) if actor is not None and getattr(actor, "is_authenticated", False) else "Staff"
    log_activity(
        follow_up.case,
        ActivityEvent.FOLLOW_UP_COMPLETED,
        f"{actor_label} completed follow-up: {follow_up.title}",
        actor=actor,
    )
    return follow_up


def cancel_follow_up(follow_up: CaseFollowUp, *, actor) -> CaseFollowUp:
    follow_up.status = FollowUpStatus.CANCELLED
    follow_up.save(update_fields=["status", "updated_at"])
    log_activity(follow_up.case, ActivityEvent.FOLLOW_UP_CANCELLED, f"Follow-up cancelled: {follow_up.title}.", actor=actor)
    return follow_up


ALLOWED_FOLLOW_UP_ORDERING = {
    "due_at",
    "-due_at",
    "created_at",
    "-created_at",
    "updated_at",
    "-updated_at",
}


def follow_up_queryset():
    return CaseFollowUp.objects.select_related(
        "assigned_to",
        "created_by",
        "case",
        "case__customer",
        "case__property",
        "case__assigned_to",
    )


def _day_bounds(reference):
    local = timezone.localtime(reference)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def parse_date_bound(value, *, end: bool = False):
    if value in (None, ""):
        return None
    raw = str(value).strip()
    parsed = parse_datetime(raw)
    if parsed is not None:
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed
    try:
        day = date.fromisoformat(raw[:10])
    except (TypeError, ValueError) as exc:
        raise CaseError("Date filters must be valid dates.", code="invalid_date") from exc
    combined = datetime.combine(day, time.max if end else time.min)
    if timezone.is_naive(combined):
        combined = timezone.make_aware(combined, timezone.get_current_timezone())
    return combined


def filter_follow_ups(queryset, params):
    now = timezone.now()
    status = (params.get("status") or "actionable").strip().lower()
    if status in {"", "all"}:
        pass
    elif status == "actionable":
        queryset = queryset.filter(status=FollowUpStatus.PENDING)
    elif status == "overdue":
        queryset = queryset.filter(status=FollowUpStatus.PENDING, due_at__lt=now)
    elif status == FollowUpStatus.PENDING:
        queryset = queryset.filter(status=FollowUpStatus.PENDING).filter(Q(due_at__isnull=True) | Q(due_at__gte=now))
    elif status in FollowUpStatus.values:
        queryset = queryset.filter(status=status)
    else:
        raise CaseError("Unknown follow-up status.", code="invalid_follow_up_status")

    assigned = params.get("assigned_staff") or params.get("staff") or params.get("assigned_to")
    if assigned not in (None, "", "all"):
        try:
            queryset = queryset.filter(assigned_to_id=int(assigned))
        except (TypeError, ValueError) as exc:
            raise CaseError("assigned_staff must be an integer.", code="invalid_assignee") from exc

    property_id = params.get("property")
    if property_id not in (None, "", "all"):
        try:
            queryset = queryset.filter(case__property_id=int(property_id))
        except (TypeError, ValueError) as exc:
            raise CaseError("property must be an integer.", code="invalid_property") from exc

    follow_up_type = params.get("type") or params.get("follow_up_type")
    if follow_up_type not in (None, "", "all"):
        if follow_up_type not in FollowUpType.values:
            raise CaseError("Unknown follow-up type.", code="invalid_follow_up_type")
        queryset = queryset.filter(follow_up_type=follow_up_type)

    stage = params.get("case_stage") or params.get("stage")
    if stage not in (None, "", "all"):
        queryset = queryset.filter(case__stage=validate_stage(stage))

    source = (params.get("source") or "").strip().lower()
    if source not in (None, "", "all"):
        queryset = queryset.filter(case__source=source)

    due = (params.get("due") or params.get("due_date") or "all").strip().lower()
    if due not in (None, "", "all"):
        start_today, end_today = _day_bounds(now)
        if due == "today":
            queryset = queryset.filter(due_at__gte=start_today, due_at__lt=end_today)
        elif due == "tomorrow":
            queryset = queryset.filter(due_at__gte=end_today, due_at__lt=end_today + timedelta(days=1))
        elif due == "this_week":
            local = timezone.localtime(now)
            week_start = local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=local.weekday())
            queryset = queryset.filter(due_at__gte=week_start, due_at__lt=week_start + timedelta(days=7))
        elif due == "overdue":
            queryset = queryset.filter(status=FollowUpStatus.PENDING, due_at__lt=now)
        elif due == "custom":
            due_from = parse_date_bound(params.get("due_from") or params.get("from"))
            due_to = parse_date_bound(params.get("due_to") or params.get("to"), end=True)
            if due_from is not None:
                queryset = queryset.filter(due_at__gte=due_from)
            if due_to is not None:
                queryset = queryset.filter(due_at__lte=due_to)
        else:
            raise CaseError("Unknown due date filter.", code="invalid_due_filter")

    search = (params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(case__case_number__icontains=search)
            | Q(case__title__icontains=search)
            | Q(case__customer__name__icontains=search)
            | Q(case__customer__phone__icontains=search)
            | Q(case__customer__email__icontains=search)
        )
    return queryset


def order_follow_ups(queryset, params):
    ordering = (params.get("ordering") or params.get("sort") or "due_at").strip()
    if ordering not in ALLOWED_FOLLOW_UP_ORDERING:
        raise CaseError("Unknown sort field.", code="invalid_ordering")
    field = ordering.lstrip("-")
    descending = ordering.startswith("-")
    expression = F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_last=True)
    return queryset.order_by(expression, "-id" if descending else "id")


def follow_up_filter_staff(user):
    from accounts.scope import get_visible_users

    assigned_ids = accessible_follow_ups(user).exclude(assigned_to=None).values_list("assigned_to_id", flat=True)
    return get_visible_users(user, User.objects.filter(is_active=True)).filter(
        Q(pk__in=assigned_ids) | Q(pk=user.pk)
    ).distinct().order_by("first_name", "last_name", "username")


def follow_up_filter_properties(user):
    from accounts.authorization import accessible_properties

    return accessible_properties(user).order_by("name", "id")


def create_global_follow_up(*, actor, payload: dict) -> CaseFollowUp:
    case_id = payload.get("case_id")
    if case_id in (None, ""):
        raise CaseError("case_id is required.", code="invalid_case")
    try:
        case = Case.objects.select_related("property").filter(pk=int(case_id)).first()
    except (TypeError, ValueError) as exc:
        raise CaseError("case_id must be an integer.", code="invalid_case") from exc
    if case is None:
        raise CaseError("Case not found.", code="not_found")
    if not can_access_case(actor, case):
        raise CaseError("You do not have access to this case.", code="property_forbidden")
    return create_follow_up(case, payload, actor=actor)


def attach_inbound_message_to_case(message) -> Case:
    from cases.numbering import open_case_for_conversation

    conversation = message.conversation
    case = open_case_for_conversation(conversation)
    if case is not None:
        link_conversation(case, conversation, originating=False)
        case.save(update_fields=["updated_at"])
        return case
    title = (conversation.subject or message.content or "Customer request").strip()[:255]
    sequence, case_number = allocate_case_number()
    case = Case.objects.create(
        sequence=sequence,
        case_number=case_number,
        customer=conversation.customer,
        property=conversation.property,
        originating_conversation=conversation,
        originating_message=message,
        title=title,
        description=message.content,
        original_request=message.content,
        source=conversation.channel or message.channel,
        stage=PipelineStage.NEW,
    )
    link_conversation(case, conversation, originating=True)
    log_created(case)
    return case
