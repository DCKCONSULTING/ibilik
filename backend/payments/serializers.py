from __future__ import annotations

from decimal import Decimal

from cases.serializers import CHANNEL_LABELS, format_value, isoformat, serialize_user_summary, stage_label
from crm.services import available_reply_channels
from payments.ledger import case_ledger
from payments.models import CaseCharge, ChargeCategory, ChargeKind, Payment, PaymentAttachment, PaymentMethod, PaymentRefund, PaymentStatus, PaymentType
from payments.services import case_balance, refundable_amount


def format_money(amount: Decimal | None, currency: str = "MYR") -> str | None:
    if amount is None:
        return None
    quantized = amount.quantize(Decimal("0.01"))
    if quantized == quantized.to_integral():
        return f"{currency} {int(quantized):,}"
    return f"{currency} {quantized:,.2f}"


def serialize_attachment(attachment: PaymentAttachment) -> dict:
    return {
        "id": attachment.pk,
        "original_name": attachment.original_name,
        "content_type": attachment.content_type,
        "description": attachment.description,
        "is_image": (attachment.content_type or "").startswith("image/"),
        "uploaded_by": serialize_user_summary(attachment.uploaded_by),
        "uploaded_at": isoformat(attachment.uploaded_at),
        "url": f"/api/payments/{attachment.payment_id}/attachments/{attachment.pk}/download/",
    }


def serialize_refund(refund: PaymentRefund) -> dict:
    return {
        "id": refund.pk,
        "refund_number": refund.refund_number,
        "payment_id": refund.payment_id,
        "amount": format_value(refund.amount),
        "amount_label": format_money(refund.amount, refund.payment.currency),
        "reason": refund.reason,
        "status": refund.status,
        "status_label": refund.get_status_display(),
        "requested_by": serialize_user_summary(refund.requested_by),
        "requested_at": isoformat(refund.requested_at),
        "approved_by": serialize_user_summary(refund.approved_by),
        "approved_at": isoformat(refund.approved_at),
        "rejected_by": serialize_user_summary(refund.rejected_by),
        "rejected_at": isoformat(refund.rejected_at),
        "rejection_reason": refund.rejection_reason,
        "completed_by": serialize_user_summary(refund.completed_by),
        "completed_at": isoformat(refund.completed_at),
    }


def serialize_payment(payment: Payment, *, include_detail: bool = False) -> dict:
    case = payment.case
    customer = case.customer
    property_obj = case.property
    display_status = "overdue" if payment.is_overdue() else payment.status
    payload = {
        "id": payment.pk,
        "payment_number": payment.payment_number,
        "payment_type": payment.payment_type,
        "payment_type_label": payment.get_payment_type_display(),
        "amount": format_value(payment.amount),
        "amount_label": format_money(payment.amount, payment.currency),
        "currency": payment.currency,
        "payment_method": payment.payment_method,
        "payment_method_label": payment.get_payment_method_display(),
        "workflow_status": payment.status,
        "status": display_status,
        "status_label": "Overdue" if display_status == "overdue" else payment.get_status_display(),
        "is_overdue": payment.is_overdue(),
        "expected_date": isoformat(payment.expected_date),
        "paid_at": isoformat(payment.paid_at),
        "notes": payment.notes,
        "created_by": serialize_user_summary(payment.created_by),
        "approved_by": serialize_user_summary(payment.approved_by),
        "approved_at": isoformat(payment.approved_at),
        "rejected_by": serialize_user_summary(payment.rejected_by),
        "rejected_at": isoformat(payment.rejected_at),
        "rejection_reason": payment.rejection_reason,
        "submitted_at": isoformat(payment.submitted_at),
        "created_at": isoformat(payment.created_at),
        "updated_at": isoformat(payment.updated_at),
        "refundable_amount": format_value(refundable_amount(payment)),
        "attachment_count": len(payment.attachments.all()),
        "case": {
            "id": case.pk,
            "case_number": case.case_number,
            "title": case.title,
            "stage": case.stage,
            "stage_label": stage_label(case.stage),
            "source": case.source or None,
            "source_label": CHANNEL_LABELS.get(case.source, case.source) if case.source else None,
            "value": format_value(case.value),
        },
        "customer": {
            "id": customer.pk,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
        },
        "property": None if property_obj is None else {"id": property_obj.pk, "name": property_obj.name},
        "location": None
        if case.location_id is None
        else {"id": case.location_id, "name": case.location.name, "code": case.location.code},
        "staff": serialize_user_summary(case.assigned_to),
        "check_in": isoformat(case.check_in),
        "check_out": isoformat(case.check_out),
    }
    if include_detail:
        payload["attachments"] = [serialize_attachment(item) for item in payment.attachments.all()]
        payload["refunds"] = [serialize_refund(item) for item in payment.refunds.select_related("payment", "requested_by", "approved_by", "rejected_by", "completed_by")]
        balance = case_balance(case)
        payload["balance"] = serialize_balance(balance)
        payload["balance_labels"] = serialize_balance_labels(balance, payment.currency)
        payload["charges"] = [serialize_charge(item) for item in case.case_charges.select_related("created_by", "voided_by")]
        payload["ledger"] = [serialize_ledger_row(item) for item in case_ledger(case)]
        payload["reply_channels"] = available_reply_channels(customer)
    return payload


def serialize_balance(balance: dict) -> dict:
    payload = {}
    for key, value in balance.items():
        if key in {"account_status", "account_status_label"}:
            payload[key] = value
        else:
            payload[key] = format_value(value)
    return payload


def serialize_balance_labels(balance: dict, currency: str = "MYR") -> dict:
    payload = {}
    for key, value in balance.items():
        if key in {"account_status", "account_status_label"}:
            payload[key] = value
        else:
            payload[key] = format_money(value, currency)
    return payload


def serialize_charge(charge: CaseCharge) -> dict:
    return {
        "id": charge.pk,
        "kind": charge.kind,
        "kind_label": charge.get_kind_display(),
        "category": charge.category,
        "category_label": charge.get_category_display(),
        "description": charge.description,
        "quantity": format_value(charge.quantity),
        "unit_price": format_value(charge.unit_price),
        "tax_amount": format_value(charge.tax_amount),
        "amount": format_value(charge.amount),
        "amount_label": format_money(charge.amount, charge.currency),
        "currency": charge.currency,
        "reason": charge.reason,
        "notes": charge.notes,
        "status": charge.status,
        "status_label": charge.get_status_display(),
        "occurred_at": isoformat(charge.occurred_at),
        "created_by": serialize_user_summary(charge.created_by),
        "voided_by": serialize_user_summary(charge.voided_by),
        "voided_at": isoformat(charge.voided_at),
        "void_reason": charge.void_reason,
        "created_at": isoformat(charge.created_at),
    }


def serialize_ledger_row(row: dict) -> dict:
    return {
        **row,
        "amount": format_value(row["amount"]),
        "signed_amount": format_value(row["signed_amount"]),
        "occurred_at": isoformat(row["occurred_at"]),
        "created_by": serialize_user_summary(row["created_by"]),
    }


def serialize_types():
    return [{"id": value, "label": label} for value, label in PaymentType.choices]


def serialize_methods():
    return [{"id": value, "label": label} for value, label in PaymentMethod.choices]


def serialize_statuses():
    return [{"id": value, "label": label} for value, label in PaymentStatus.choices] + [{"id": "overdue", "label": "Overdue"}]


def serialize_charge_kinds():
    return [{"id": value, "label": label} for value, label in ChargeKind.choices]


def serialize_charge_categories():
    return [{"id": value, "label": label} for value, label in ChargeCategory.choices]
