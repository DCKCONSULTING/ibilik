from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from cases.activity import log_activity
from cases.models import ActivityEvent, Case
from pipeline.models import PipelineStage
from payments.errors import PaymentError
from payments.models import (
    CaseCharge,
    ChargeCategory,
    ChargeKind,
    ChargeStatus,
    Payment,
    PaymentRefund,
    PaymentStatus,
    PaymentType,
    RefundStatus,
)

ZERO = Decimal("0.00")

ACCOUNT_UNPAID = "unpaid"
ACCOUNT_PARTIALLY_PAID = "partially_paid"
ACCOUNT_PAID = "paid"
ACCOUNT_OVERPAID = "overpaid"
ACCOUNT_REFUND_PENDING = "refund_pending"
ACCOUNT_REFUNDED = "refunded"
ACCOUNT_CANCELLED = "cancelled"

ACCOUNT_LABELS = {
    ACCOUNT_UNPAID: "Unpaid",
    ACCOUNT_PARTIALLY_PAID: "Partially paid",
    ACCOUNT_PAID: "Paid",
    ACCOUNT_OVERPAID: "Overpaid",
    ACCOUNT_REFUND_PENDING: "Refund pending",
    ACCOUNT_REFUNDED: "Refunded",
    ACCOUNT_CANCELLED: "Cancelled",
}


def _money(value) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


def _sum(queryset, field="amount") -> Decimal:
    return _money(queryset.aggregate(total=Sum(field))["total"])


def account_status(*, case: Case, total_charges: Decimal, paid: Decimal, refunded: Decimal, outstanding: Decimal, pending_refunds: Decimal) -> str:
    if pending_refunds > 0:
        return ACCOUNT_REFUND_PENDING
    if refunded > 0 and paid > 0 and refunded >= paid and outstanding >= ZERO:
        return ACCOUNT_REFUNDED
    if outstanding < ZERO:
        return ACCOUNT_OVERPAID
    if paid > 0 and outstanding == ZERO:
        return ACCOUNT_PAID
    if paid > 0 and outstanding > ZERO:
        return ACCOUNT_PARTIALLY_PAID
    if case.stage == PipelineStage.LOST:
        return ACCOUNT_CANCELLED
    return ACCOUNT_UNPAID


def case_balance(case: Case) -> dict:
    payments = Payment.objects.filter(case=case)
    approved = payments.filter(status=PaymentStatus.APPROVED)
    paid = _sum(approved)
    deposits = _sum(approved.filter(payment_type=PaymentType.DEPOSIT))
    refunds = PaymentRefund.objects.filter(payment__case=case)
    refunded = _sum(refunds.filter(status=RefundStatus.COMPLETED))
    pending_refunds = _sum(refunds.filter(status__in={RefundStatus.REQUESTED, RefundStatus.PENDING_APPROVAL, RefundStatus.APPROVED}))
    charges = CaseCharge.objects.filter(case=case, status=ChargeStatus.ACTIVE)
    extra_charges = _sum(charges.filter(kind=ChargeKind.CHARGE))
    penalties = _sum(charges.filter(kind=ChargeKind.PENALTY))
    taxes = _sum(charges.filter(kind=ChargeKind.TAX))
    discounts = _sum(charges.filter(kind=ChargeKind.DISCOUNT))
    adjustments = _sum(charges.filter(kind=ChargeKind.ADJUSTMENT))
    room_charges = _money(case.value)
    total_charges = room_charges + extra_charges + penalties + taxes - discounts + adjustments
    outstanding = total_charges - paid + refunded
    status = account_status(
        case=case,
        total_charges=total_charges,
        paid=paid,
        refunded=refunded,
        outstanding=outstanding,
        pending_refunds=pending_refunds,
    )
    return {
        "case_value": room_charges,
        "room_charges": room_charges,
        "extra_charges": extra_charges,
        "penalties": penalties,
        "taxes": taxes,
        "discounts": discounts,
        "adjustments": adjustments,
        "total_charges": total_charges,
        "paid": paid,
        "deposits": deposits,
        "refunded": refunded,
        "pending_refunds": pending_refunds,
        "outstanding": outstanding,
        "account_status": status,
        "account_status_label": ACCOUNT_LABELS[status],
    }


def case_ledger(case: Case) -> list[dict]:
    rows = []
    room = _money(case.value)
    if room > 0:
        rows.append(
            {
                "id": f"room-{case.pk}",
                "source": "reservation",
                "source_id": case.pk,
                "type": "charge",
                "type_label": "Charge",
                "description": "Room booking",
                "amount": room,
                "signed_amount": room,
                "method": "",
                "method_label": "",
                "status": "active",
                "status_label": "Active",
                "reference": case.case_number,
                "notes": "",
                "reason": "",
                "created_by": None,
                "occurred_at": case.created_at,
                "voidable": False,
            }
        )
    for charge in case.case_charges.select_related("created_by", "voided_by").all():
        signed = charge.amount if charge.kind != ChargeKind.DISCOUNT else -charge.amount
        if charge.status == ChargeStatus.VOIDED:
            signed = ZERO
        rows.append(
            {
                "id": f"charge-{charge.pk}",
                "source": "charge",
                "source_id": charge.pk,
                "type": charge.kind,
                "type_label": charge.get_kind_display(),
                "description": charge.description,
                "amount": charge.amount,
                "signed_amount": signed,
                "method": charge.category,
                "method_label": charge.get_category_display(),
                "status": charge.status,
                "status_label": charge.get_status_display(),
                "reference": "",
                "notes": charge.notes,
                "reason": charge.reason or charge.void_reason,
                "created_by": charge.created_by,
                "occurred_at": charge.occurred_at or charge.created_at,
                "voidable": charge.status == ChargeStatus.ACTIVE,
            }
        )
    for payment in Payment.objects.filter(case=case).select_related("created_by"):
        included = payment.status == PaymentStatus.APPROVED
        rows.append(
            {
                "id": f"payment-{payment.pk}",
                "source": "payment",
                "source_id": payment.pk,
                "type": "payment",
                "type_label": payment.get_payment_type_display(),
                "description": f"{payment.get_payment_method_display()} payment",
                "amount": payment.amount,
                "signed_amount": -payment.amount if included else ZERO,
                "method": payment.payment_method,
                "method_label": payment.get_payment_method_display(),
                "status": payment.status,
                "status_label": payment.get_status_display(),
                "reference": payment.payment_number,
                "notes": payment.notes,
                "reason": payment.rejection_reason,
                "created_by": payment.created_by,
                "occurred_at": payment.paid_at or payment.created_at,
                "voidable": False,
            }
        )
        for refund in payment.refunds.select_related("requested_by", "completed_by").all():
            included = refund.status == RefundStatus.COMPLETED
            rows.append(
                {
                    "id": f"refund-{refund.pk}",
                    "source": "refund",
                    "source_id": refund.pk,
                    "type": "refund",
                    "type_label": "Refund",
                    "description": f"Refund of {payment.payment_number}",
                    "amount": refund.amount,
                    "signed_amount": refund.amount if included else ZERO,
                    "method": payment.payment_method,
                    "method_label": payment.get_payment_method_display(),
                    "status": refund.status,
                    "status_label": refund.get_status_display(),
                    "reference": refund.refund_number,
                    "notes": "",
                    "reason": refund.reason,
                    "created_by": refund.completed_by or refund.requested_by,
                    "occurred_at": refund.completed_at or refund.requested_at or refund.created_at,
                    "voidable": False,
                }
            )
    rows.sort(key=lambda item: (item["occurred_at"] or timezone.now(), str(item["id"])))
    return rows


@transaction.atomic
def create_case_charge(*, actor, case: Case, payload: dict, kind: str) -> CaseCharge:
    from payments.services import _parse_amount, _parse_datetime

    if kind not in ChargeKind.values:
        raise PaymentError("Unknown charge type.", code="invalid_kind")
    category = str(payload.get("category") or ChargeCategory.OTHER).strip()
    if category not in ChargeCategory.values:
        raise PaymentError("Unknown charge category.", code="invalid_category")
    description = str(payload.get("description") or "").strip() or ChargeCategory(category).label
    quantity = _parse_amount(payload.get("quantity") or "1")
    unit_price = _parse_amount(payload.get("unit_price") or payload.get("amount"))
    tax = Decimal(str(payload.get("tax") or payload.get("tax_amount") or "0") or "0").quantize(Decimal("0.01"))
    if tax < 0:
        raise PaymentError("Tax cannot be negative.", code="invalid_amount")
    amount = (quantity * unit_price + tax).quantize(Decimal("0.01"))
    if amount <= 0:
        raise PaymentError("amount must be greater than zero.", code="invalid_amount")
    reason = str(payload.get("reason") or "").strip()
    if kind == ChargeKind.PENALTY and not reason:
        raise PaymentError("A penalty reason is required.", code="invalid_reason")
    key = str(payload.get("idempotency_key") or "").strip()
    if key:
        existing = CaseCharge.objects.filter(case=case, idempotency_key=key).first()
        if existing:
            return existing
    try:
        charge = CaseCharge.objects.create(
            case=case,
            kind=kind,
            category=category,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            tax_amount=tax,
            amount=amount,
            currency=str(payload.get("currency") or (case.property.currency if case.property_id else "") or "MYR").strip().upper()[:8],
            reason=reason,
            notes=str(payload.get("notes") or "").strip(),
            occurred_at=_parse_datetime(payload.get("occurred_at") or payload.get("date")) or timezone.now(),
            idempotency_key=key,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
    except IntegrityError:
        existing = CaseCharge.objects.filter(case=case, idempotency_key=key).first() if key else None
        if existing:
            return existing
        raise
    event = ActivityEvent.PENALTY_CREATED if kind == ChargeKind.PENALTY else ActivityEvent.CHARGE_CREATED
    log_activity(case, event, f"{charge.get_kind_display()} added: {charge.description} ({charge.currency} {charge.amount}).", actor=actor)
    return charge


@transaction.atomic
def void_case_charge(charge: CaseCharge, *, actor, reason: str) -> CaseCharge:
    reason = str(reason or "").strip()
    if not reason:
        raise PaymentError("A void reason is required.", code="invalid_reason")
    if charge.status == ChargeStatus.VOIDED:
        return charge
    charge.status = ChargeStatus.VOIDED
    charge.void_reason = reason
    charge.voided_by = actor if getattr(actor, "is_authenticated", False) else None
    charge.voided_at = timezone.now()
    charge.save()
    log_activity(charge.case, ActivityEvent.CHARGE_VOIDED, f"{charge.get_kind_display()} voided: {charge.description}. {reason}", actor=actor)
    return charge
