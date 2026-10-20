from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Q

from cases.access import accessible_cases, accessible_follow_ups
from cases.models import Case, CaseFollowUp, FollowUpStatus
from cases.serializers import (
    CHANNEL_LABELS,
    format_value,
    isoformat,
    serialize_follow_up_sources,
    serialize_pipeline_stages,
    serialize_user_summary,
    stage_label,
)
from cases.services import CaseError, follow_up_filter_properties, follow_up_filter_staff, parse_date_bound
from payments.models import Payment


CALENDAR_EVENT_TYPES = (
    ("check_in", "Check-in"),
    ("check_out", "Check-out"),
    ("follow_up", "Follow-up"),
    ("payment", "Payment"),
    ("quote", "Quote"),
    ("approval", "Approval"),
    ("finance", "Finance"),
)

CALENDAR_TYPE_ALIASES = {
    "all": "all",
    "check_in": "check_in",
    "check-in": "check_in",
    "checkin": "check_in",
    "checkins": "check_in",
    "check-ins": "check_in",
    "check_out": "check_out",
    "check-out": "check_out",
    "checkout": "check_out",
    "checkouts": "check_out",
    "check-outs": "check_out",
    "follow_up": "follow_up",
    "follow-up": "follow_up",
    "follow-ups": "follow_up",
    "followups": "follow_up",
    "payment": "payment",
    "payments": "payment",
    "quote": "quote",
    "quotes": "quote",
    "approval": "approval",
    "approvals": "approval",
    "finance": "finance",
}

CALENDAR_TYPE_LABELS = {key: label for key, label in CALENDAR_EVENT_TYPES}
DEFAULT_EVENT_DURATION = timedelta(hours=1)
MAX_RANGE_DAYS = 93

FOLLOW_UP_STATUSES = {FollowUpStatus.PENDING, FollowUpStatus.COMPLETED, FollowUpStatus.CANCELLED, "overdue"}
PAYMENT_STATUSES = {"expected", "received", "cancelled", "rejected", "overdue"}


def serialize_calendar_event_types() -> list[dict]:
    return [{"id": key, "label": label} for key, label in CALENDAR_EVENT_TYPES]


def format_money(amount: Decimal | None, currency: str = "MYR") -> str | None:
    if amount is None:
        return None
    quantized = amount.quantize(Decimal("0.01"))
    if quantized == quantized.to_integral():
        return f"{currency} {int(quantized):,}"
    return f"{currency} {quantized:,.2f}"


def first_name(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return text.split()[0]


def _parse_range(params) -> tuple:
    start = parse_date_bound(params.get("start") or params.get("from"))
    end = parse_date_bound(params.get("end") or params.get("to"), end=True)
    if start is None or end is None:
        raise CaseError("start and end query parameters are required.", code="invalid_date_range")
    if end <= start:
        raise CaseError("end must be after start.", code="invalid_date_range")
    if end - start > timedelta(days=MAX_RANGE_DAYS):
        raise CaseError("Calendar range cannot exceed 93 days.", code="invalid_date_range")
    return start, end


def _normalize_type(value) -> str:
    raw = (value or "all").strip().lower()
    if raw in ("", "all"):
        return "all"
    if raw not in CALENDAR_TYPE_ALIASES:
        raise CaseError("Unknown calendar event type.", code="invalid_event_type")
    return CALENDAR_TYPE_ALIASES[raw]


def _wants(selected: str, event_type: str) -> bool:
    return selected == "all" or selected == event_type


def _case_context(case: Case) -> dict:
    customer = case.customer
    property_obj = case.property
    source = case.source
    return {
        "case": {
            "id": case.pk,
            "case_number": case.case_number,
            "title": case.title,
            "stage": case.stage,
            "stage_label": stage_label(case.stage),
            "source": source or None,
            "source_label": CHANNEL_LABELS.get(source, source) if source else None,
        },
        "customer": {
            "id": customer.pk,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
        },
        "property": None if property_obj is None else {"id": property_obj.pk, "name": property_obj.name},
        "staff": serialize_user_summary(case.assigned_to),
    }


def _event(*, event_type: str, title: str, start, end, case: Case, source_model: str, source_id: int, staff=None, status=None, status_label=None, metadata=None, all_day=False):
    context = _case_context(case)
    if staff is not None:
        context["staff"] = serialize_user_summary(staff) if not isinstance(staff, dict) else staff
    return {
        "id": f"{source_model}:{source_id}:{event_type}",
        "type": event_type,
        "type_label": CALENDAR_TYPE_LABELS[event_type],
        "title": title,
        "start": isoformat(start),
        "end": isoformat(end),
        "all_day": all_day,
        "status": status,
        "status_label": status_label,
        "source_model": source_model,
        "source_id": source_id,
        "case_id": case.pk,
        **context,
        "metadata": metadata or {},
    }


def _matches_search(case: Case, search: str) -> bool:
    needle = search.lower()
    property_name = case.property.name if case.property else ""
    haystacks = (
        case.case_number,
        case.title,
        case.customer.name,
        case.customer.phone or "",
        case.customer.email or "",
        property_name,
    )
    return any(needle in value.lower() for value in haystacks if value)


def _matches_staff(assigned, staff_id: int) -> bool:
    if assigned is None:
        return False
    if isinstance(assigned, dict):
        return assigned.get("id") == staff_id
    return assigned.pk == staff_id


def _follow_up_status(follow_up: CaseFollowUp) -> tuple[str, str]:
    if follow_up.is_overdue():
        return "overdue", "Overdue"
    return follow_up.status, follow_up.get_status_display()


def _matches_status(event_type: str, status: str | None, selected: str) -> bool:
    if selected in ("", "all"):
        return True
    if event_type == "follow_up":
        return status == selected
    if event_type == "payment":
        return status == selected
    return False


def calendar_case_queryset(user):
    return accessible_cases(
        user,
        Case.objects.select_related("customer", "property", "assigned_to"),
    )


def list_calendar_events(user, params) -> dict:
    start, end = _parse_range(params)
    selected_type = _normalize_type(params.get("type") or params.get("event_type"))
    status = (params.get("status") or "all").strip().lower()
    if status not in ("", "all", *FOLLOW_UP_STATUSES, *PAYMENT_STATUSES):
        raise CaseError("Unknown calendar status.", code="invalid_status")
    search = (params.get("search") or "").strip()
    staff_id = None
    assigned = params.get("staff") or params.get("assigned_staff") or params.get("assigned_to")
    if assigned not in (None, "", "all"):
        try:
            staff_id = int(assigned)
        except (TypeError, ValueError) as exc:
            raise CaseError("staff must be an integer.", code="invalid_assignee") from exc
    property_id = params.get("property")
    stage = params.get("case_stage") or params.get("stage")
    source = (params.get("source") or "").strip().lower()

    cases = calendar_case_queryset(user)
    if property_id not in (None, "", "all"):
        try:
            cases = cases.filter(property_id=int(property_id))
        except (TypeError, ValueError) as exc:
            raise CaseError("property must be an integer.", code="invalid_property") from exc
    if stage not in (None, "", "all"):
        cases = cases.filter(stage=stage)
    if source not in (None, "", "all"):
        cases = cases.filter(source=source)

    events: list[dict] = []
    case_ids = cases.values("pk")

    if _wants(selected_type, "follow_up"):
        follow_ups = (
            accessible_follow_ups(user)
            .filter(case_id__in=case_ids, due_at__gte=start, due_at__lt=end)
            .select_related("assigned_to", "created_by", "case", "case__customer", "case__property", "case__assigned_to")
        )
        for follow_up in follow_ups:
            event_status, status_label = _follow_up_status(follow_up)
            if not _matches_status("follow_up", event_status, status):
                continue
            if staff_id is not None and not _matches_staff(follow_up.assigned_to, staff_id):
                continue
            if search and not (
                _matches_search(follow_up.case, search)
                or search.lower() in (follow_up.title or "").lower()
                or search.lower() in (follow_up.description or "").lower()
            ):
                continue
            staff = follow_up.assigned_to or follow_up.case.assigned_to
            staff_label = (serialize_user_summary(staff) or {}).get("display_name") or "Unassigned"
            events.append(
                _event(
                    event_type="follow_up",
                    title=f"Follow-up — {follow_up.title}",
                    start=follow_up.due_at,
                    end=follow_up.due_at + DEFAULT_EVENT_DURATION,
                    case=follow_up.case,
                    source_model="case_follow_up",
                    source_id=follow_up.pk,
                    staff=staff,
                    status=event_status,
                    status_label=status_label,
                    metadata={
                        "follow_up_title": follow_up.title,
                        "follow_up_type": follow_up.follow_up_type,
                        "description": follow_up.description,
                        "staff_name": staff_label,
                    },
                )
            )

    if _wants(selected_type, "payment"):
        payments = (
            Payment.objects.filter(case_id__in=case_ids, expected_date__gte=start, expected_date__lt=end)
            .select_related("case", "case__customer", "case__property", "case__assigned_to")
        )
        for payment in payments:
            event_status = payment.calendar_status()
            if not _matches_status("payment", event_status, status):
                continue
            if staff_id is not None and not _matches_staff(payment.case.assigned_to, staff_id):
                continue
            if search and not _matches_search(payment.case, search):
                continue
            money = format_money(payment.amount, payment.currency)
            customer_name = first_name(payment.case.customer.name) or payment.case.customer.name
            events.append(
                _event(
                    event_type="payment",
                    title=f"Payment — {money}",
                    start=payment.expected_date,
                    end=payment.expected_date + DEFAULT_EVENT_DURATION,
                    case=payment.case,
                    source_model="payment",
                    source_id=payment.pk,
                    status=event_status,
                    status_label=payment.get_status_display() if event_status != "overdue" else "Overdue",
                    metadata={
                        "amount": format_value(payment.amount),
                        "amount_label": money,
                        "currency": payment.currency,
                        "customer_name": customer_name,
                        "payment_number": payment.payment_number,
                    },
                )
            )

    case_date_fields = []
    if _wants(selected_type, "check_in"):
        case_date_fields.append(("check_in", "check_in", "Check-in"))
    if _wants(selected_type, "check_out"):
        case_date_fields.append(("check_out", "check_out", "Check-out"))
    if _wants(selected_type, "quote"):
        case_date_fields.append(("quoted_at", "quote", "Quote sent"))
    if _wants(selected_type, "approval"):
        case_date_fields.append(("approved_at", "approval", "Approval completed"))
    if _wants(selected_type, "finance"):
        case_date_fields.append(("finance_moved_at", "finance", "Sent to finance"))

    if case_date_fields and status in ("", "all"):
        date_filter = Q()
        for field_name, _, _ in case_date_fields:
            date_filter |= Q(**{f"{field_name}__gte": start, f"{field_name}__lt": end})
        dated_cases = cases.filter(date_filter)
        if staff_id is not None:
            dated_cases = dated_cases.filter(assigned_to_id=staff_id)
        for case in dated_cases:
            if search and not _matches_search(case, search):
                continue
            customer_name = first_name(case.customer.name) or case.customer.name
            for field_name, event_type, label in case_date_fields:
                value = getattr(case, field_name)
                if value is None or value < start or value >= end:
                    continue
                title = f"{label} — {customer_name}"
                if event_type in {"check_in", "check_out"}:
                    title = f"{label} — {customer_name}"
                events.append(
                    _event(
                        event_type=event_type,
                        title=title,
                        start=value,
                        end=value + DEFAULT_EVENT_DURATION,
                        case=case,
                        source_model="case",
                        source_id=case.pk,
                        metadata={"customer_name": customer_name, "field": field_name},
                    )
                )

    events.sort(key=lambda item: (item["start"] or "", item["id"]))
    return {
        "resource": "calendar-events",
        "count": len(events),
        "start": isoformat(start),
        "end": isoformat(end),
        "types": serialize_calendar_event_types(),
        "stages": serialize_pipeline_stages(),
        "sources": serialize_follow_up_sources(),
        "staff": [serialize_user_summary(user) for user in follow_up_filter_staff(user)],
        "properties": [{"id": item.pk, "name": item.name} for item in follow_up_filter_properties(user)],
        "results": events,
    }
