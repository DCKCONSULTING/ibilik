from __future__ import annotations

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from locations.errors import LocationError
from locations.models import (
    CleaningStatus,
    CleaningTask,
    Location,
    LocationStatus,
    LocationStatusHistory,
    MaintenanceIssue,
    MaintenancePriority,
    MaintenanceStatus,
)
from pipeline.models import PipelineStage

OCCUPANCY_FREE = "free"
OCCUPANCY_RESERVED = "reserved"
OCCUPANCY_IN_HOUSE = "in_house"

OCCUPANCY_LABELS = {
    OCCUPANCY_FREE: "Free",
    OCCUPANCY_RESERVED: "Reserved",
    OCCUPANCY_IN_HOUSE: "In house",
}

BLOCKING_STATUSES = {
    LocationStatus.MAINTENANCE,
    LocationStatus.OUT_OF_ORDER,
    LocationStatus.INACTIVE,
}
NOT_READY_STATUSES = BLOCKING_STATUSES | {
    LocationStatus.DIRTY,
    LocationStatus.CLEANING,
    LocationStatus.INSPECTION,
}


def stay_cases(location: Location):
    cached = getattr(location, "stay_cases", None)
    if cached is not None:
        return list(cached)
    from cases.models import Case

    return list(
        Case.objects.filter(location=location)
        .select_related("customer", "property")
        .order_by("check_in", "id")
    )


def _is_open_stay(case) -> bool:
    return case.stage != PipelineStage.LOST and case.actual_check_out is None


def is_current_stay(case, now) -> bool:
    if not _is_open_stay(case):
        return False
    return bool(case.actual_check_in)


def is_future_reservation(case, now) -> bool:
    if not _is_open_stay(case) or case.actual_check_in:
        return False
    return bool(case.check_in)


def current_stay(location: Location, now=None):
    now = now or timezone.now()
    for case in stay_cases(location):
        if is_current_stay(case, now):
            return case
    return None


def next_reservation(location: Location, now=None):
    now = now or timezone.now()
    upcoming = None
    for case in stay_cases(location):
        if not is_future_reservation(case, now):
            continue
        if upcoming is None or case.check_in < upcoming.check_in:
            upcoming = case
    return upcoming


def occupancy_for(location: Location, now=None) -> str:
    now = now or timezone.now()
    if current_stay(location, now):
        return OCCUPANCY_IN_HOUSE
    if next_reservation(location, now):
        return OCCUPANCY_RESERVED
    return OCCUPANCY_FREE


def is_bookable(location: Location, *, now=None, start=None, end=None) -> bool:
    now = now or timezone.now()
    if not location.active or not location.is_bookable:
        return False
    if location.status in NOT_READY_STATUSES:
        return False
    if current_stay(location, now) and start is None:
        return False
    if start is None:
        return True
    return not has_conflicting_reservation(location, start, end, now=now)


def has_conflicting_reservation(location: Location, start, end=None, *, now=None, exclude_case_id=None) -> bool:
    now = now or timezone.now()
    for case in stay_cases(location):
        if exclude_case_id and case.pk == exclude_case_id:
            continue
        if not _is_open_stay(case):
            continue
        case_start = case.actual_check_in or case.check_in
        case_end = case.actual_check_out or case.check_out
        if case_start is None:
            continue
        if end is None:
            if case_end is None or case_end > start:
                return True
            continue
        if case_end is None or (case_start < end and case_end > start):
            return True
    return False


def allowed_actions(location: Location, *, user=None, now=None) -> list[str]:
    now = now or timezone.now()
    stay = current_stay(location, now)
    upcoming = next_reservation(location, now)
    actions = []
    if stay is None and upcoming is not None and location.active and location.status != LocationStatus.INACTIVE:
        actions.append("check_in")
    if stay is not None:
        actions.append("check_out")
    if location.status == LocationStatus.DIRTY:
        actions.append("start_cleaning")
    if location.status == LocationStatus.CLEANING:
        actions.append("complete_cleaning")
    if location.status not in {LocationStatus.AVAILABLE, LocationStatus.INACTIVE}:
        actions.append("mark_available")
    if location.status != LocationStatus.DIRTY:
        actions.append("mark_dirty")
    if location.status not in BLOCKING_STATUSES:
        actions.append("start_maintenance")
        actions.append("mark_out_of_order")
    if location.status in {LocationStatus.MAINTENANCE, LocationStatus.OUT_OF_ORDER}:
        actions.append("resolve_maintenance")
    if location.active:
        actions.append("deactivate")
    actions.append("edit")
    return actions


def location_state(location: Location, *, now=None) -> dict:
    now = now or timezone.now()
    stay = current_stay(location, now)
    upcoming = next_reservation(location, now)
    value = occupancy_for(location, now)
    return {
        "occupancy": value,
        "occupancy_label": OCCUPANCY_LABELS[value],
        "is_free": value == OCCUPANCY_FREE,
        "is_bookable_now": is_bookable(location, now=now),
        "current_stay": stay,
        "next_reservation": upcoming,
        "allowed_actions": allowed_actions(location, now=now),
    }


def record_status_change(location: Location, previous: str, *, actor=None, reason: str = "") -> None:
    if previous == location.status:
        return
    LocationStatusHistory.objects.create(
        location=location,
        previous_status=previous or "",
        new_status=location.status,
        reason=reason,
        changed_by=actor if getattr(actor, "is_authenticated", False) else None,
    )


@transaction.atomic
def set_operational_status(location: Location, status: str, *, actor=None, reason: str = "") -> Location:
    if status not in LocationStatus.values:
        raise LocationError("Unknown operational status.", code="invalid_status")
    previous = location.status
    location.status = status
    location.active = status != LocationStatus.INACTIVE
    if status == LocationStatus.INACTIVE:
        location.active = False
    location.save(update_fields=["status", "active", "updated_at"])
    record_status_change(location, previous, actor=actor, reason=reason)
    return location


@transaction.atomic
def check_in_location(location: Location, case, *, actor=None, override: bool = False) -> dict:
    from cases.models import Case

    location = Location.objects.select_for_update().select_related("property").get(pk=location.pk)
    if case is None:
        raise LocationError("Reservation is required.", code="invalid_reservation")
    case = Case.objects.select_for_update().select_related("customer", "property").get(pk=case.pk)
    now = timezone.now()
    if case.location_id != location.pk:
        raise LocationError("This reservation is not assigned to this location.", code="reservation_mismatch")
    if case.stage == PipelineStage.LOST:
        raise LocationError("This reservation is not eligible for check-in.", code="reservation_ineligible")
    if case.actual_check_out:
        raise LocationError("This stay has already been checked out.", code="already_checked_out")
    if case.actual_check_in:
        raise LocationError("This reservation is already checked in.", code="already_checked_in")
    if not location.active or location.status == LocationStatus.INACTIVE:
        raise LocationError("This location is inactive.", code="location_inactive")
    if location.status in BLOCKING_STATUSES and not override:
        raise LocationError("Check-in is blocked while the location is out of service.", code="status_blocked")
    if location.status in {LocationStatus.DIRTY, LocationStatus.CLEANING, LocationStatus.INSPECTION} and not override:
        raise LocationError("The location must be cleaned before check-in.", code="location_not_ready")
    other = current_stay(location, now)
    if other is not None and other.pk != case.pk:
        raise LocationError("Another guest is already staying in this location.", code="stay_conflict")
    case.actual_check_in = now
    if case.check_in is None:
        case.check_in = now
    case.save(update_fields=["actual_check_in", "check_in", "updated_at"])
    location.refresh_from_db()
    if hasattr(location, "stay_cases"):
        del location.stay_cases
    return location_state(location, now=now)


@transaction.atomic
def check_out_location(location: Location, case=None, *, actor=None, override: bool = False) -> dict:
    from cases.models import Case

    location = Location.objects.select_for_update().select_related("property").get(pk=location.pk)
    now = timezone.now()
    stay = Case.objects.select_for_update().select_related("customer", "property").get(pk=case.pk) if case is not None else current_stay(location, now)
    if stay is None:
        raise LocationError("There is no active stay to check out.", code="no_active_stay")
    if stay.location_id != location.pk:
        raise LocationError("This stay is not assigned to this location.", code="reservation_mismatch")
    if stay.actual_check_out:
        raise LocationError("This stay has already been checked out.", code="already_checked_out")
    from payments.ledger import case_balance

    outstanding = case_balance(stay)["outstanding"]
    if outstanding > 0 and not override:
        raise LocationError(
            f"Outstanding balance of {stay.property.currency if stay.property_id else 'MYR'} {outstanding} must be settled before check-out.",
            code="payment_required",
        )
    stay.actual_check_out = now
    if stay.check_out is None or stay.check_out > now:
        stay.check_out = now
    stay.save(update_fields=["actual_check_out", "check_out", "updated_at"])
    set_operational_status(location, LocationStatus.DIRTY, actor=actor, reason="Checked out")
    if hasattr(location, "stay_cases"):
        del location.stay_cases
    return location_state(location, now=now)


@transaction.atomic
def start_cleaning(location: Location, *, actor=None, assigned_to=None, notes: str = "") -> CleaningTask:
    if location.status not in {LocationStatus.DIRTY, LocationStatus.INSPECTION, LocationStatus.AVAILABLE}:
        raise LocationError("Cleaning can only start from a dirty or inspectable location.", code="invalid_cleaning")
    now = timezone.now()
    task = CleaningTask.objects.create(
        location=location,
        assigned_to=assigned_to,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        status=CleaningStatus.IN_PROGRESS,
        notes=notes,
        started_at=now,
    )
    set_operational_status(location, LocationStatus.CLEANING, actor=actor, reason="Cleaning started")
    return task


@transaction.atomic
def complete_cleaning(location: Location, *, actor=None, notes: str = "") -> CleaningTask:
    task = location.cleaning_tasks.filter(status=CleaningStatus.IN_PROGRESS).order_by("-id").first()
    now = timezone.now()
    if task is None:
        task = CleaningTask.objects.create(
            location=location,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
            started_at=now,
        )
    task.status = CleaningStatus.COMPLETED
    task.completed_at = now
    if notes:
        task.notes = notes
    task.save()
    set_operational_status(location, LocationStatus.AVAILABLE, actor=actor, reason="Cleaning completed")
    return task


@transaction.atomic
def start_maintenance(
    location: Location,
    *,
    actor=None,
    title: str,
    description: str = "",
    priority: str = MaintenancePriority.MEDIUM,
    assigned_to=None,
    expected_at=None,
    out_of_order: bool = False,
) -> MaintenanceIssue:
    title = (title or "").strip()
    if not title:
        raise LocationError("Maintenance title is required.", code="invalid_title")
    if priority not in MaintenancePriority.values:
        raise LocationError("Unknown maintenance priority.", code="invalid_priority")
    now = timezone.now()
    issue = MaintenanceIssue.objects.create(
        location=location,
        property=location.property,
        title=title,
        description=description,
        priority=priority,
        status=MaintenanceStatus.IN_PROGRESS,
        assigned_to=assigned_to,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        started_at=now,
        expected_at=expected_at,
    )
    next_status = LocationStatus.OUT_OF_ORDER if out_of_order else LocationStatus.MAINTENANCE
    set_operational_status(location, next_status, actor=actor, reason=title)
    return issue


@transaction.atomic
def resolve_maintenance(location: Location, issue=None, *, actor=None, notes: str = "") -> MaintenanceIssue:
    issue = issue or location.maintenance_issues.exclude(status__in=[MaintenanceStatus.RESOLVED, MaintenanceStatus.CANCELLED]).order_by("-id").first()
    if issue is None:
        raise LocationError("There is no open maintenance issue.", code="no_maintenance")
    now = timezone.now()
    issue.status = MaintenanceStatus.RESOLVED
    issue.resolved_at = now
    if notes:
        issue.notes = notes
    issue.save()
    set_operational_status(location, LocationStatus.AVAILABLE, actor=actor, reason="Maintenance resolved")
    return issue


def start_of_day(now):
    local = timezone.localtime(now)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def occupancy_exists(now=None):
    from cases.models import Case

    now = now or timezone.now()
    in_house = (
        Case.objects.filter(location_id=OuterRef("pk"), actual_check_in__isnull=False, actual_check_out__isnull=True)
        .exclude(stage=PipelineStage.LOST)
    )
    upcoming = Case.objects.filter(
        location_id=OuterRef("pk"),
        check_in__isnull=False,
        actual_check_in__isnull=True,
        actual_check_out__isnull=True,
    ).exclude(stage=PipelineStage.LOST)
    return Exists(in_house), Exists(upcoming)
