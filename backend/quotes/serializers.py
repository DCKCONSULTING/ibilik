from __future__ import annotations

from decimal import Decimal

from cases.serializers import format_value, isoformat, serialize_user_summary
from quotes.models import Quote, QuoteStatus


def format_money(amount: Decimal | None, currency: str = "MYR") -> str | None:
    if amount is None:
        return None
    quantized = amount.quantize(Decimal("0.01"))
    if quantized == quantized.to_integral():
        return f"{currency} {int(quantized):,}"
    return f"{currency} {quantized:,.2f}"


def serialize_quote(quote: Quote, *, include_detail: bool = False) -> dict:
    case = quote.case
    customer = case.customer
    property_obj = case.property
    display_status = "expired" if quote.is_expired() else quote.status
    payload = {
        "id": quote.pk,
        "quote_number": quote.quote_number,
        "amount": format_value(quote.amount),
        "amount_label": format_money(quote.amount, quote.currency),
        "currency": quote.currency,
        "workflow_status": quote.status,
        "status": display_status,
        "status_label": "Expired" if display_status == "expired" else quote.get_status_display(),
        "is_expired": quote.is_expired(),
        "valid_until": isoformat(quote.valid_until),
        "notes": quote.notes,
        "created_by": serialize_user_summary(quote.created_by),
        "created_at": isoformat(quote.created_at),
        "updated_at": isoformat(quote.updated_at),
        "case": {
            "id": case.pk,
            "case_number": case.case_number,
            "title": case.title,
            "stage": case.stage,
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
    if include_detail:
        payload["case"]["value"] = format_value(case.value)
        payload["case"]["quote_notes"] = case.quote_notes
    return payload


def serialize_statuses():
    return [{"id": value, "label": label} for value, label in QuoteStatus.choices] + [
        {"id": "expired", "label": "Expired"}
    ]
