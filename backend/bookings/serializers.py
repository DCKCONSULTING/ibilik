from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from cases.serializers import format_value, isoformat, serialize_user_summary, stage_label
from pipeline.models import PipelineStage

from bookings.services import booking_nights, booking_status

STATUS_LABELS = {
    "upcoming": "Upcoming",
    "in_house": "In house",
    "completed": "Completed",
    "cancelled": "Cancelled",
}


def format_money(amount: Decimal | None, currency: str = "MYR") -> str | None:
    if amount is None:
        return None
    quantized = amount.quantize(Decimal("0.01"))
    if quantized == quantized.to_integral():
        return f"{currency} {int(quantized):,}"
    return f"{currency} {quantized:,.2f}"


def serialize_booking(case, *, include_detail: bool = False, now=None) -> dict:
    now = now or timezone.now()
    customer = case.customer
    property_obj = case.property
    location = getattr(case, "location", None)
    status = booking_status(case, now=now)
    payload = {
        "id": case.pk,
        "booking_number": case.case_number,
        "title": case.title,
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "stage": case.stage,
        "stage_label": stage_label(case.stage),
        "nights": booking_nights(case),
        "value": format_value(case.value),
        "value_label": format_money(case.value),
        "check_in": isoformat(case.check_in),
        "check_out": isoformat(case.check_out),
        "notes": case.staff_notes or "",
        "created_at": isoformat(case.created_at),
        "updated_at": isoformat(case.updated_at),
        "case": {
            "id": case.pk,
            "case_number": case.case_number,
            "title": case.title,
            "stage": case.stage,
            "stage_label": stage_label(case.stage),
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
        else {
            "id": location.pk,
            "name": location.name,
            "code": location.code,
            "type": location.location_type,
            "type_label": location.get_location_type_display(),
        },
        "staff": serialize_user_summary(case.assigned_to),
    }
    if include_detail:
        payload["description"] = case.description
        payload["request"] = case.original_request or case.description
        payload["source"] = case.source
        payload["case"]["value"] = format_value(case.value)
        payload["case"]["quote_notes"] = case.quote_notes
    return payload


def serialize_statuses():
    return [{"id": key, "label": label} for key, label in STATUS_LABELS.items()]


def serialize_stages():
    return [{"id": value, "label": label} for value, label in PipelineStage.choices]
