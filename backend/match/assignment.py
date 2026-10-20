from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max

from accounts.authorization import user_has_permission
from accounts.serializers import display_name
from match.errors import MatchError
from match.history import log_history
from match.models import (
    ACTIVE_WORKLOAD_STATUSES,
    MatchAssignmentMethod,
    MatchHistoryAction,
    MatchRequest,
    MatchRequestStatus,
    MatchSettings,
)
from match.permissions import VIEW_ASSIGNED, VIEW_MATCH

NO_PROPERTY_STAFF = "No active staff member is assigned to this property."
NO_ELIGIBLE_STAFF = "No eligible staff member is available."
NEVER_ASSIGNED = datetime.min.replace(tzinfo=dt_timezone.utc)


def get_match_settings(*, lock: bool = False) -> MatchSettings:
    queryset = MatchSettings.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    settings = queryset.first()
    if settings is None:
        settings, _ = MatchSettings.objects.get_or_create(pk=1)
        if lock:
            settings = MatchSettings.objects.select_for_update().get(pk=settings.pk)
    return settings


def can_receive_match_requests(user: User) -> bool:
    if not getattr(user, "is_active", False) or getattr(user, "is_superuser", False):
        return False
    return user_has_permission(user, VIEW_MATCH) or user_has_permission(user, VIEW_ASSIGNED)


def active_workload(user_id: int) -> int:
    return MatchRequest.objects.filter(
        assigned_to_id=user_id,
        status__in=ACTIVE_WORKLOAD_STATUSES,
    ).count()


def last_assignment_at(user_id: int):
    return MatchRequest.objects.filter(assigned_to_id=user_id, assigned_at__isnull=False).aggregate(
        latest=Max("assigned_at")
    )["latest"]


def eligible_assignees(property_obj, settings: MatchSettings) -> list[User]:
    queryset = User.objects.filter(is_active=True).exclude(is_superuser=True)
    if property_obj is not None:
        if settings.property_staff_only:
            queryset = queryset.filter(assigned_properties=property_obj)
    elif not settings.org_wide_when_no_property:
        return []
    users = list(queryset.distinct().prefetch_related("assigned_properties"))
    return [user for user in users if can_receive_match_requests(user)]


def select_lowest_workload(users: list[User]) -> User | None:
    if not users:
        return None
    ranked = sorted(
        users,
        key=lambda user: (
            active_workload(user.pk),
            last_assignment_at(user.pk) or NEVER_ASSIGNED,
            user.pk,
        ),
    )
    return ranked[0]


def staff_workload_rows(*, property_obj=None, settings: MatchSettings | None = None) -> list[dict]:
    settings = settings or get_match_settings()
    if property_obj is not None:
        candidates = list(
            User.objects.filter(is_active=True, assigned_properties=property_obj)
            .exclude(is_superuser=True)
            .distinct()
            .prefetch_related("assigned_properties")
        )
    else:
        candidates = list(
            User.objects.filter(is_active=True)
            .exclude(is_superuser=True)
            .prefetch_related("assigned_properties")
        )
    eligible_ids = {user.pk for user in eligible_assignees(property_obj, settings)}
    rows = []
    for user in candidates:
        properties = [{"id": item.pk, "name": item.name} for item in user.assigned_properties.all()]
        rows.append(
            {
                "id": user.pk,
                "username": user.username,
                "name": display_name(user),
                "display_name": display_name(user),
                "active_requests": active_workload(user.pk),
                "last_assigned_at": last_assignment_at(user.pk),
                "eligible": user.pk in eligible_ids,
                "assigned_properties": properties,
            }
        )
    rows.sort(key=lambda item: (item["active_requests"], item["last_assigned_at"] or NEVER_ASSIGNED, item["id"]))
    return rows


@transaction.atomic
def assign_request_automatically(request: MatchRequest, *, force: bool = False, actor=None) -> MatchRequest:
    settings = get_match_settings(lock=True)
    locked = MatchRequest.objects.select_for_update().filter(pk=request.pk).select_related("property", "assigned_to").first()
    if locked is None:
        raise MatchError("Request not found.", code="not_found")

    if locked.assigned_to_id and not force:
        return locked

    if not settings.auto_assign_enabled and not force:
        return locked

    if not settings.auto_assign_enabled and force:
        raise MatchError("Automatic assignment is disabled.", code="auto_assign_disabled")

    eligible = eligible_assignees(locked.property, settings)
    if not eligible:
        reason = NO_PROPERTY_STAFF if locked.property_id else NO_ELIGIBLE_STAFF
        previous = display_name(locked.assigned_to) if locked.assigned_to else "Unassigned"
        locked.assigned_to = None
        locked.assigned_by = None
        locked.assigned_at = None
        locked.assignment_method = ""
        locked.workload_at_assignment = None
        locked.unassigned_reason = reason
        if locked.status not in {MatchRequestStatus.RESOLVED, MatchRequestStatus.CANCELLED}:
            locked.status = MatchRequestStatus.UNASSIGNED
        locked.save()
        log_history(
            locked,
            MatchHistoryAction.AUTO_UNASSIGNED,
            actor=actor,
            previous_value=previous,
            new_value=reason,
        )
        return locked

    winner = select_lowest_workload(eligible)
    workload = active_workload(winner.pk)
    from match.services import _apply_assignment

    assigned = _apply_assignment(
        locked,
        winner,
        actor=actor,
        action=MatchHistoryAction.AUTO_ASSIGNED,
        method=MatchAssignmentMethod.AUTOMATIC,
        workload=workload,
    )
    assigned.unassigned_reason = ""
    assigned.save(update_fields=["unassigned_reason", "updated_at"])
    return assigned
