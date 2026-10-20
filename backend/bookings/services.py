from __future__ import annotations

from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from cases.models import Case
from cases.services import CaseError, follow_up_filter_properties, follow_up_filter_staff, parse_date_bound
from pipeline.models import PipelineStage

from bookings.access import accessible_bookings
from bookings.errors import BookingError

BOOKING_STATUSES = {"upcoming", "in_house", "completed", "cancelled"}

ALLOWED_ORDERING = {
    "check_in",
    "-check_in",
    "check_out",
    "-check_out",
    "created_at",
    "-created_at",
    "updated_at",
    "-updated_at",
    "value",
    "-value",
}


def booking_queryset():
    return Case.objects.select_related(
        "customer",
        "property",
        "location",
        "assigned_to",
        "created_by",
    )


def booking_status(case, *, now=None) -> str:
    now = now or timezone.now()
    if case.stage == PipelineStage.LOST:
        return "cancelled"
    if case.check_in and case.check_in > now:
        return "upcoming"
    if case.check_in and case.check_in <= now and (case.check_out is None or now < case.check_out):
        return "in_house"
    return "completed"


def booking_nights(case) -> int | None:
    if case.check_in is None or case.check_out is None:
        return None
    delta = case.check_out.date() - case.check_in.date()
    return max(delta.days, 0)


def _apply_status(queryset, status: str, now):
    if status == "cancelled":
        return queryset.filter(stage=PipelineStage.LOST)
    queryset = queryset.exclude(stage=PipelineStage.LOST)
    if status == "upcoming":
        return queryset.filter(check_in__gt=now)
    if status == "in_house":
        return queryset.filter(check_in__lte=now).filter(Q(check_out__isnull=True) | Q(check_out__gt=now))
    if status == "completed":
        return queryset.filter(check_out__lte=now)
    raise BookingError("Unknown booking status.", code="invalid_status")


def filter_bookings(queryset, params):
    status = (params.get("status") or "all").strip().lower()
    if status not in {"", "all"}:
        if status not in BOOKING_STATUSES:
            raise BookingError("Unknown booking status.", code="invalid_status")
        queryset = _apply_status(queryset, status, timezone.now())

    property_id = params.get("property")
    if property_id not in (None, "", "all"):
        try:
            queryset = queryset.filter(property_id=int(property_id))
        except (TypeError, ValueError) as exc:
            raise BookingError("property must be an integer.", code="invalid_property") from exc

    staff = params.get("staff") or params.get("assigned_staff")
    if staff not in (None, "", "all"):
        try:
            queryset = queryset.filter(assigned_to_id=int(staff))
        except (TypeError, ValueError) as exc:
            raise BookingError("staff must be an integer.", code="invalid_assignee") from exc

    customer_id = params.get("customer") or params.get("customer_id")
    if customer_id not in (None, "", "all"):
        try:
            queryset = queryset.filter(customer_id=int(customer_id))
        except (TypeError, ValueError) as exc:
            raise BookingError("customer must be an integer.", code="invalid_customer") from exc

    location_id = params.get("location")
    if location_id not in (None, "", "all"):
        try:
            queryset = queryset.filter(location_id=int(location_id))
        except (TypeError, ValueError) as exc:
            raise BookingError("location must be an integer.", code="invalid_location") from exc

    case_id = params.get("case") or params.get("case_id")
    if case_id not in (None, "", "all"):
        try:
            queryset = queryset.filter(pk=int(case_id))
        except (TypeError, ValueError):
            queryset = queryset.filter(case_number__icontains=str(case_id).strip())

    case_number = (params.get("case_number") or params.get("booking_number") or "").strip()
    if case_number:
        queryset = queryset.filter(case_number__icontains=case_number)

    date_field = (params.get("date_field") or "check_in").strip()
    field_map = {
        "check_in": "check_in",
        "checkin": "check_in",
        "check_out": "check_out",
        "checkout": "check_out",
        "created_at": "created_at",
        "created": "created_at",
        "updated_at": "updated_at",
        "updated": "updated_at",
    }
    if date_field not in field_map:
        raise BookingError("Unknown date field.", code="invalid_date_field")
    lookup = field_map[date_field]
    due = (params.get("due") or params.get("date") or "all").strip().lower()
    if due not in (None, "", "all"):
        now = timezone.now()
        local = timezone.localtime(now)
        start_today = local.replace(hour=0, minute=0, second=0, microsecond=0)
        if due == "today":
            queryset = queryset.filter(**{f"{lookup}__gte": start_today, f"{lookup}__lt": start_today + timedelta(days=1)})
        elif due == "this_week":
            week_start = start_today - timedelta(days=local.weekday())
            queryset = queryset.filter(**{f"{lookup}__gte": week_start, f"{lookup}__lt": week_start + timedelta(days=7)})
        elif due == "this_month":
            month_start = start_today.replace(day=1)
            if month_start.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1)
            queryset = queryset.filter(**{f"{lookup}__gte": month_start, f"{lookup}__lt": month_end})
        elif due == "custom":
            try:
                date_from = parse_date_bound(params.get("date_from") or params.get("from"))
                date_to = parse_date_bound(params.get("date_to") or params.get("to"), end=True)
            except CaseError as exc:
                raise BookingError(str(exc), code=getattr(exc, "code", "invalid_date")) from exc
            if date_from is not None:
                queryset = queryset.filter(**{f"{lookup}__gte": date_from})
            if date_to is not None:
                queryset = queryset.filter(**{f"{lookup}__lte": date_to})
        else:
            raise BookingError("Unknown date filter.", code="invalid_due_filter")

    search = (params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(case_number__icontains=search)
            | Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(customer__name__icontains=search)
            | Q(customer__phone__icontains=search)
            | Q(customer__email__icontains=search)
            | Q(property__name__icontains=search)
            | Q(location__name__icontains=search)
            | Q(location__code__icontains=search)
        )
    return queryset


def order_bookings(queryset, params):
    ordering = (params.get("ordering") or params.get("sort") or "check_in").strip()
    if ordering not in ALLOWED_ORDERING:
        raise BookingError("Unknown sort field.", code="invalid_ordering")
    field = ordering.lstrip("-")
    descending = ordering.startswith("-")
    expression = F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_last=True)
    return queryset.order_by(expression, "-id" if descending else "id")


def booking_filter_staff(user):
    return follow_up_filter_staff(user)


def booking_filter_properties(user):
    return follow_up_filter_properties(user)


def booking_filter_locations(user):
    from locations.access import accessible_locations

    location_ids = accessible_booking_queryset(user).exclude(location=None).values("location_id")
    return accessible_locations(user).filter(pk__in=location_ids).order_by("name", "id")


def accessible_booking_queryset(user):
    return accessible_bookings(user, booking_queryset())
