"""Hotel CRM dashboard aggregates from live bookings, rooms, payments, and pipeline."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.authorization import accessible_properties
from accounts.scope import ScopeError, require_visible_property
from bookings.access import accessible_bookings
from bookings.serializers import format_money, serialize_booking
from cases.access import accessible_cases, accessible_follow_ups
from cases.models import FollowUpStatus
from cases.serializers import format_value, isoformat, serialize_follow_up
from crm.access import accessible_customers
from locations.access import accessible_locations
from locations.location_state import OCCUPANCY_LABELS, occupancy_for
from locations.models import LocationStatus, MaintenanceIssue, MaintenanceStatus
from locations.services import prefetch_stay_cases
from payments.access import accessible_payments
from payments.models import PaymentStatus
from payments.serializers import format_money as format_payment_money
from payments.serializers import format_value as format_payment_value
from pipeline.models import PipelineStage


OPEN_PIPELINE_STAGES = (
    PipelineStage.NEW,
    PipelineStage.QUALIFIED,
    PipelineStage.QUOTED,
    PipelineStage.NEGOTIATING,
)
PENDING_PAYMENT_STATUSES = (
    PaymentStatus.PENDING,
    PaymentStatus.PROOF_SUBMITTED,
    PaymentStatus.PENDING_APPROVAL,
)
ATTENTION_STATUSES = (
    LocationStatus.DIRTY,
    LocationStatus.CLEANING,
    LocationStatus.MAINTENANCE,
    LocationStatus.OUT_OF_ORDER,
    LocationStatus.INSPECTION,
)
LIST_LIMIT = 8


class DashboardError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid", status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def _day_bounds(now):
    local = timezone.localtime(now)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _month_bounds(now):
    local = timezone.localtime(now)
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _parse_property_id(params) -> int | None:
    value = params.get("property")
    if value in (None, "", "all"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise DashboardError("property must be an integer.", code="invalid_property") from exc


def _active_stays(queryset):
    return queryset.exclude(stage=PipelineStage.LOST)


def _in_house(queryset, now):
    return _active_stays(queryset).filter(check_in__lte=now).filter(Q(check_out__isnull=True) | Q(check_out__gt=now))


def _upcoming(queryset, now):
    return _active_stays(queryset).filter(check_in__gt=now)


def _money_total(queryset, field="amount") -> Decimal:
    return queryset.aggregate(total=Sum(field))["total"] or Decimal("0.00")


def _serialize_dashboard_payment(payment) -> dict:
    case = payment.case
    customer = case.customer
    property_obj = case.property
    location = getattr(case, "location", None)
    display_status = "overdue" if payment.is_overdue() else payment.status
    return {
        "id": payment.pk,
        "payment_number": payment.payment_number,
        "payment_type": payment.payment_type,
        "payment_type_label": payment.get_payment_type_display(),
        "amount": format_payment_value(payment.amount),
        "amount_label": format_payment_money(payment.amount, payment.currency),
        "currency": payment.currency,
        "status": display_status,
        "status_label": "Overdue" if display_status == "overdue" else payment.get_status_display(),
        "is_overdue": payment.is_overdue(),
        "expected_date": isoformat(payment.expected_date),
        "case": {
            "id": case.pk,
            "case_number": case.case_number,
            "title": case.title,
        },
        "customer": {
            "id": customer.pk,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
        },
        "property": None if property_obj is None else {"id": property_obj.pk, "name": property_obj.name},
        "location": None
        if location is None
        else {"id": location.pk, "name": location.name, "code": location.code},
    }


def _serialize_room(location, now) -> dict:
    occupancy = occupancy_for(location, now)
    property_obj = location.property
    return {
        "id": location.pk,
        "name": location.name,
        "code": location.code,
        "type": location.location_type,
        "type_label": location.get_location_type_display(),
        "status": location.status,
        "status_label": location.get_status_display(),
        "occupancy": occupancy,
        "occupancy_label": OCCUPANCY_LABELS.get(occupancy, occupancy),
        "property": None if property_obj is None else {"id": property_obj.pk, "name": property_obj.name},
    }


def _count_map(rows, key="status") -> dict[str, int]:
    return {item[key]: item["count"] for item in rows}


def build_dashboard(user, params) -> dict:
    now = timezone.now()
    start_today, end_today = _day_bounds(now)
    month_start, month_end = _month_bounds(now)
    property_id = _parse_property_id(params)
    if property_id is not None:
        try:
            require_visible_property(user, property_id)
        except ScopeError as exc:
            raise DashboardError(str(exc), code=exc.code, status=exc.status) from exc

    bookings = accessible_bookings(user).select_related(
        "customer",
        "property",
        "location",
        "assigned_to",
        "created_by",
    )
    if property_id is not None:
        bookings = bookings.filter(property_id=property_id)
    active_bookings = _active_stays(bookings)

    arrivals_qs = active_bookings.filter(check_in__gte=start_today, check_in__lt=end_today).order_by("check_in", "id")
    departures_qs = active_bookings.filter(check_out__gte=start_today, check_out__lt=end_today).order_by("check_out", "id")
    in_house_qs = _in_house(bookings, now).order_by("check_out", "id")
    upcoming_qs = _upcoming(bookings, now)

    arrivals_count = arrivals_qs.count()
    departures_count = departures_qs.count()
    in_house_count = in_house_qs.count()
    upcoming_count = upcoming_qs.count()

    occupied_rooms = (
        in_house_qs.exclude(location_id=None).values_list("location_id", flat=True).distinct().count()
    )

    locations = accessible_locations(user).select_related("property").filter(active=True)
    if property_id is not None:
        locations = locations.filter(property_id=property_id)
    bookable_rooms = locations.filter(is_bookable=True).exclude(status=LocationStatus.INACTIVE)
    bookable_count = bookable_rooms.count()
    occupancy_rate = float(round((Decimal(occupied_rooms) / Decimal(bookable_count)) * 100, 1)) if bookable_count else 0.0

    status_counts = _count_map(locations.values("status").annotate(count=Count("id")))
    rooms_by_status = [
        {"id": value, "label": label, "count": status_counts.get(value, 0)}
        for value, label in LocationStatus.choices
    ]
    rooms_attention_count = locations.filter(status__in=ATTENTION_STATUSES).count()
    attention_rooms = list(
        prefetch_stay_cases(locations.filter(status__in=ATTENTION_STATUSES)).order_by("status", "name", "id")[:LIST_LIMIT]
    )

    cases = accessible_cases(user)
    if property_id is not None:
        cases = cases.filter(property_id=property_id)
    open_pipeline = cases.filter(stage__in=OPEN_PIPELINE_STAGES)
    open_pipeline_count = open_pipeline.count()
    open_pipeline_value = _money_total(open_pipeline, "value")
    pipeline_by_stage = []
    for stage_id, stage_label in PipelineStage.choices:
        stage_qs = cases.filter(stage=stage_id)
        stage_value = _money_total(stage_qs, "value")
        pipeline_by_stage.append(
            {
                "id": stage_id,
                "label": stage_label,
                "count": stage_qs.count(),
                "value": format_value(stage_value),
                "value_label": format_money(stage_value),
            }
        )

    payments = accessible_payments(user).select_related(
        "case",
        "case__customer",
        "case__property",
        "case__location",
        "case__assigned_to",
    )
    if property_id is not None:
        payments = payments.filter(case__property_id=property_id)
    pending_payments = payments.filter(status__in=PENDING_PAYMENT_STATUSES)
    overdue_payments = pending_payments.filter(expected_date__lt=now)
    pending_count = pending_payments.count()
    overdue_count = overdue_payments.count()
    pending_amount = _money_total(pending_payments)
    overdue_amount = _money_total(overdue_payments)
    approved_month = payments.filter(status=PaymentStatus.APPROVED).filter(
        Q(paid_at__gte=month_start, paid_at__lt=month_end)
        | Q(paid_at__isnull=True, approved_at__gte=month_start, approved_at__lt=month_end)
    )
    revenue = _money_total(approved_month)

    follow_ups = (
        accessible_follow_ups(user)
        .select_related("case", "case__customer", "case__property", "assigned_to", "created_by")
        .filter(status=FollowUpStatus.PENDING)
    )
    if property_id is not None:
        follow_ups = follow_ups.filter(case__property_id=property_id)
    overdue_follow_ups = follow_ups.filter(due_at__lt=now)
    follow_up_count = follow_ups.count()
    overdue_follow_up_count = overdue_follow_ups.count()

    customers = accessible_customers(user)
    if property_id is not None:
        customers = customers.filter(Q(property_id=property_id) | Q(conversations__property_id=property_id)).distinct()

    properties = accessible_properties(user).order_by("name", "id")
    maintenance = MaintenanceIssue.objects.filter(
        status__in=(MaintenanceStatus.OPEN, MaintenanceStatus.IN_PROGRESS),
        property__in=properties,
    )
    if property_id is not None:
        maintenance = maintenance.filter(property_id=property_id)

    arrivals = [serialize_booking(item, now=now) for item in arrivals_qs[:LIST_LIMIT]]
    departures = [serialize_booking(item, now=now) for item in departures_qs[:LIST_LIMIT]]
    in_house = [serialize_booking(item, now=now) for item in in_house_qs[:LIST_LIMIT]]
    recent_bookings = [serialize_booking(item, now=now) for item in bookings.order_by("-created_at", "-id")[:LIST_LIMIT]]
    pending_payment_rows = [
        _serialize_dashboard_payment(item)
        for item in pending_payments.order_by("expected_date", "id")[:LIST_LIMIT]
    ]
    follow_up_rows = [
        serialize_follow_up(item, include_context=True)
        for item in follow_ups.order_by("due_at", "id")[:LIST_LIMIT]
    ]

    return {
        "resource": "dashboard",
        "generated_at": isoformat(now),
        "kpis": {
            "check_ins_today": arrivals_count,
            "check_outs_today": departures_count,
            "in_house": in_house_count,
            "upcoming": upcoming_count,
            "occupancy_rate": occupancy_rate,
            "occupied_rooms": occupied_rooms,
            "bookable_rooms": bookable_count,
            "open_pipeline": open_pipeline_count,
            "pipeline_value": format_value(open_pipeline_value),
            "pipeline_value_label": format_money(open_pipeline_value),
            "pending_payments": pending_count,
            "pending_amount": format_value(pending_amount),
            "pending_amount_label": format_money(pending_amount),
            "overdue_payments": overdue_count,
            "overdue_amount": format_value(overdue_amount),
            "overdue_amount_label": format_money(overdue_amount),
            "open_follow_ups": follow_up_count,
            "overdue_follow_ups": overdue_follow_up_count,
            "rooms_attention": rooms_attention_count,
            "open_maintenance": maintenance.count(),
            "customers": customers.count(),
            "revenue_this_month": format_value(revenue),
            "revenue_this_month_label": format_money(revenue),
        },
        "rooms": {
            "total": locations.count(),
            "bookable": bookable_count,
            "occupied": occupied_rooms,
            "occupancy_rate": occupancy_rate,
            "by_status": rooms_by_status,
            "attention": [_serialize_room(item, now) for item in attention_rooms],
        },
        "pipeline": {
            "open_count": open_pipeline_count,
            "open_value": format_value(open_pipeline_value),
            "open_value_label": format_money(open_pipeline_value),
            "by_stage": pipeline_by_stage,
        },
        "arrivals": arrivals,
        "departures": departures,
        "in_house": in_house,
        "recent_bookings": recent_bookings,
        "pending_payments": pending_payment_rows,
        "follow_ups": follow_up_rows,
        "properties": [{"id": item.pk, "name": item.name} for item in properties],
    }
