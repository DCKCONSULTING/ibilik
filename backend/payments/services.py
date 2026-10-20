from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from cases.access import can_access_case
from cases.activity import log_activity
from cases.models import ActivityEvent, Case, FollowUpStatus, FollowUpType
from cases.services import CaseError, create_follow_up, follow_up_filter_properties, follow_up_filter_staff, parse_date_bound
from crm.models import Conversation
from crm.services import IngestError, available_reply_channels, send_outbound_message
from payments.access import accessible_payments
from payments.errors import PaymentError
from payments.ledger import case_balance as compute_case_balance
from payments.models import (
    Payment,
    PaymentAttachment,
    PaymentMethod,
    PaymentRefund,
    PaymentStatus,
    PaymentType,
    RefundStatus,
)
from payments.numbering import allocate_payment_number, allocate_refund_number


EDITABLE_STATUSES = {PaymentStatus.PENDING, PaymentStatus.PROOF_SUBMITTED, PaymentStatus.REJECTED}
UNPAID_STATUSES = {PaymentStatus.PENDING, PaymentStatus.PROOF_SUBMITTED, PaymentStatus.PENDING_APPROVAL}
RESERVED_REFUND_STATUSES = {RefundStatus.REQUESTED, RefundStatus.PENDING_APPROVAL, RefundStatus.APPROVED, RefundStatus.COMPLETED}


def payment_queryset():
    return Payment.objects.select_related(
        "case",
        "case__customer",
        "case__property",
        "case__location",
        "case__assigned_to",
        "created_by",
        "approved_by",
        "rejected_by",
    ).prefetch_related("attachments__uploaded_by", "refunds")


def _parse_amount(value) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PaymentError("amount must be a positive number.", code="invalid_amount") from exc
    if amount <= 0:
        raise PaymentError("amount must be greater than zero.", code="invalid_amount")
    return amount.quantize(Decimal("0.01"))


def _parse_datetime(value):
    if value in (None, ""):
        return None
    try:
        parsed = parse_datetime(str(value))
        if parsed is None:
            parsed = parse_date_bound(value)
    except CaseError as exc:
        raise PaymentError(str(exc), code=getattr(exc, "code", "invalid_date")) from exc
    if parsed is None:
        raise PaymentError("A valid datetime is required.", code="invalid_date")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def case_balance(case: Case) -> dict:
    return compute_case_balance(case)


def refundable_amount(payment: Payment) -> Decimal:
    if payment.status != PaymentStatus.APPROVED:
        return Decimal("0.00")
    reserved = payment.refunds.filter(status__in=RESERVED_REFUND_STATUSES).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    remaining = payment.amount - reserved
    return remaining if remaining > 0 else Decimal("0.00")


def maybe_create_payment_follow_up(payment: Payment, *, actor) -> None:
    if payment.expected_date is None:
        return
    exists = payment.case.follow_ups.filter(
        follow_up_type=FollowUpType.PAYMENT_FOLLOW_UP,
        status=FollowUpStatus.PENDING,
    ).exists()
    if exists:
        return
    due_at = payment.expected_date - timedelta(days=1)
    if due_at < timezone.now():
        due_at = payment.expected_date
    create_follow_up(
        payment.case,
        {
            "type": FollowUpType.PAYMENT_FOLLOW_UP,
            "title": "Send payment reminder",
            "description": f"Remind the guest about {payment.payment_number} ({payment.currency} {payment.amount}).",
            "assigned_to_id": payment.case.assigned_to_id,
            "due_at": due_at.isoformat(),
        },
        actor=actor,
    )


@transaction.atomic
def create_payment(*, actor, payload: dict) -> Payment:
    case_id = payload.get("case_id")
    if case_id in (None, ""):
        raise PaymentError("case_id is required.", code="invalid_case")
    try:
        case = Case.objects.select_related("customer", "property", "assigned_to").filter(pk=int(case_id)).first()
    except (TypeError, ValueError) as exc:
        raise PaymentError("case_id must be an integer.", code="invalid_case") from exc
    if case is None:
        raise PaymentError("Case not found.", code="not_found")
    if not can_access_case(actor, case):
        raise PaymentError("You do not have access to this case.", code="property_forbidden")
    payment_type = str(payload.get("payment_type") or PaymentType.PAYMENT).strip()
    if payment_type not in PaymentType.values:
        raise PaymentError("Unknown payment type.", code="invalid_type")
    method = str(payload.get("payment_method") or PaymentMethod.BANK_TRANSFER).strip()
    if method not in PaymentMethod.values:
        raise PaymentError("Unknown payment method.", code="invalid_method")
    key = str(payload.get("idempotency_key") or "").strip()
    if key:
        existing = Payment.objects.filter(case=case, idempotency_key=key).first()
        if existing:
            return existing
    from accounts.authorization import user_has_permission

    received = bool(payload.get("received"))
    can_verify = getattr(actor, "is_superuser", False) or user_has_permission(actor, "payments.verify_payment")
    sequence, payment_number = allocate_payment_number()
    now = timezone.now()
    paid_at = _parse_datetime(payload.get("paid_at"))
    status = PaymentStatus.PENDING
    if received and (can_verify or method == PaymentMethod.CASH):
        status = PaymentStatus.APPROVED
        paid_at = paid_at or now
    try:
        payment = Payment.objects.create(
            sequence=sequence,
            payment_number=payment_number,
            case=case,
            payment_type=payment_type,
            amount=_parse_amount(payload.get("amount")),
            currency=str(payload.get("currency") or "MYR").strip().upper()[:8],
            payment_method=method,
            status=status,
            expected_date=_parse_datetime(payload.get("expected_date")),
            paid_at=paid_at,
            notes=str(payload.get("notes") or ""),
            idempotency_key=key,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
            approved_by=actor if status == PaymentStatus.APPROVED and getattr(actor, "is_authenticated", False) else None,
            approved_at=now if status == PaymentStatus.APPROVED else None,
        )
    except IntegrityError:
        existing = Payment.objects.filter(case=case, idempotency_key=key).first() if key else None
        if existing:
            return existing
        raise
    log_activity(case, ActivityEvent.PAYMENT_CREATED, f"Payment created: {payment.payment_number} ({payment.get_payment_type_display()} {payment.currency} {payment.amount}).", actor=actor)
    if status == PaymentStatus.APPROVED:
        log_activity(case, ActivityEvent.PAYMENT_APPROVED, f"Payment {payment.payment_number} recorded as received.", actor=actor)
    maybe_create_payment_follow_up(payment, actor=actor)
    return payment


def update_payment(payment: Payment, payload: dict, *, actor) -> Payment:
    if payment.status not in EDITABLE_STATUSES:
        raise PaymentError("Only pending or rejected payments can be edited.", code="invalid_status")
    if "payment_type" in payload:
        payment_type = str(payload.get("payment_type") or "").strip()
        if payment_type not in PaymentType.values:
            raise PaymentError("Unknown payment type.", code="invalid_type")
        payment.payment_type = payment_type
    if "amount" in payload:
        payment.amount = _parse_amount(payload.get("amount"))
    if "currency" in payload:
        payment.currency = str(payload.get("currency") or "MYR").strip().upper()[:8]
    if "payment_method" in payload:
        method = str(payload.get("payment_method") or "").strip()
        if method not in PaymentMethod.values:
            raise PaymentError("Unknown payment method.", code="invalid_method")
        payment.payment_method = method
    if "expected_date" in payload:
        payment.expected_date = _parse_datetime(payload.get("expected_date"))
    if "paid_at" in payload:
        payment.paid_at = _parse_datetime(payload.get("paid_at"))
    if "notes" in payload:
        payment.notes = str(payload.get("notes") or "")
    if payment.status == PaymentStatus.REJECTED:
        payment.status = PaymentStatus.PENDING
        payment.rejection_reason = ""
    payment.save()
    return payment


def add_attachment(payment: Payment, *, uploaded_file, actor, description: str = "") -> PaymentAttachment:
    if payment.status in {PaymentStatus.APPROVED, PaymentStatus.CANCELLED}:
        raise PaymentError("Attachments cannot be added to this payment.", code="invalid_status")
    name = getattr(uploaded_file, "name", "attachment")
    content_type = getattr(uploaded_file, "content_type", "") or ""
    attachment = PaymentAttachment.objects.create(
        payment=payment,
        file=uploaded_file,
        original_name=name[:255],
        content_type=content_type[:128],
        description=str(description or "")[:255],
        uploaded_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    if payment.status == PaymentStatus.PENDING:
        payment.status = PaymentStatus.PROOF_SUBMITTED
        payment.save(update_fields=["status", "updated_at"])
    log_activity(payment.case, ActivityEvent.PAYMENT_PROOF_UPLOADED, f"Payment proof uploaded for {payment.payment_number}.", actor=actor)
    return attachment


def submit_payment(payment: Payment, *, actor) -> Payment:
    if payment.status not in {PaymentStatus.PENDING, PaymentStatus.PROOF_SUBMITTED, PaymentStatus.REJECTED}:
        raise PaymentError("This payment cannot be submitted for approval.", code="invalid_status")
    if not payment.attachments.exists():
        raise PaymentError("Attach payment proof before submitting for approval.", code="proof_required")
    payment.status = PaymentStatus.PENDING_APPROVAL
    payment.submitted_at = timezone.now()
    payment.save(update_fields=["status", "submitted_at", "updated_at"])
    log_activity(payment.case, ActivityEvent.PAYMENT_SUBMITTED, f"Payment {payment.payment_number} submitted for approval.", actor=actor)
    return payment


def approve_payment(payment: Payment, *, actor) -> Payment:
    if payment.status != PaymentStatus.PENDING_APPROVAL:
        raise PaymentError("Only payments pending approval can be approved.", code="invalid_status")
    now = timezone.now()
    payment.status = PaymentStatus.APPROVED
    payment.approved_by = actor
    payment.approved_at = now
    if payment.paid_at is None:
        payment.paid_at = now
    payment.save()
    log_activity(payment.case, ActivityEvent.PAYMENT_APPROVED, f"Payment {payment.payment_number} approved ({payment.currency} {payment.amount}).", actor=actor)
    return payment


def reject_payment(payment: Payment, *, actor, reason: str) -> Payment:
    if payment.status != PaymentStatus.PENDING_APPROVAL:
        raise PaymentError("Only payments pending approval can be rejected.", code="invalid_status")
    reason = str(reason or "").strip()
    if not reason:
        raise PaymentError("rejection_reason is required.", code="invalid_reason")
    payment.status = PaymentStatus.REJECTED
    payment.rejected_by = actor
    payment.rejected_at = timezone.now()
    payment.rejection_reason = reason
    payment.save()
    log_activity(payment.case, ActivityEvent.PAYMENT_REJECTED, f"Payment {payment.payment_number} rejected: {reason}", actor=actor)
    return payment


def cancel_payment(payment: Payment, *, actor) -> Payment:
    if payment.status == PaymentStatus.APPROVED:
        raise PaymentError("Approved payments cannot be deleted. Cancel is not allowed; request a refund instead.", code="invalid_status")
    if payment.status == PaymentStatus.CANCELLED:
        return payment
    payment.status = PaymentStatus.CANCELLED
    payment.save(update_fields=["status", "updated_at"])
    log_activity(payment.case, ActivityEvent.PAYMENT_CANCELLED, f"Payment {payment.payment_number} cancelled.", actor=actor)
    return payment


def default_reminder_message(payment: Payment) -> str:
    customer = payment.case.customer.name.split()[0] if payment.case.customer.name else "there"
    amount = f"{payment.currency} {payment.amount:,.2f}".replace(".00", "")
    return (
        f"Hello {customer},\n\n"
        f"This is a reminder regarding the payment of {amount} for your booking/request ({payment.case.case_number}).\n\n"
        "Please let us know if you need any assistance.\n\n"
        "Thank you,\niBilik"
    )


def send_payment_reminder(payment: Payment, *, actor, channel: str | None = None, content: str | None = None):
    customer = payment.case.customer
    channels = available_reply_channels(customer)
    if not channels:
        raise PaymentError("This customer has no outbound reply channel configured.", code="channel_unavailable")
    selected = (channel or "").strip() or channels[0]
    if selected not in channels:
        raise PaymentError("The selected channel cannot receive outbound replies.", code="channel_unavailable")
    conversation = payment.case.originating_conversation
    if conversation is None:
        conversation = Conversation.objects.filter(cases=payment.case).order_by("-updated_at").first()
    if conversation is None:
        conversation = Conversation.objects.filter(customer=customer).order_by("-updated_at").first()
    if conversation is None:
        raise PaymentError("No conversation is available to send this reminder.", code="channel_unavailable")
    try:
        message = send_outbound_message(
            conversation=conversation,
            actor=actor,
            content=(content or default_reminder_message(payment)).strip(),
            channel=selected,
        )
    except IngestError as exc:
        raise PaymentError(str(exc), code=getattr(exc, "code", "channel_unavailable")) from exc
    if message.status == "failed":
        log_activity(
            payment.case,
            ActivityEvent.PAYMENT_REMINDER_SENT,
            f"Payment reminder failed for {payment.payment_number} via {selected}: {message.error_message or 'provider unavailable'}.",
            actor=actor,
        )
        raise PaymentError(message.error_message or "Reminder failed.", code="reminder_failed")
    channel_label = selected.replace("_", " ").title()
    if selected == "facebook":
        channel_label = "Facebook Messenger"
    if selected == "whatsapp":
        channel_label = "WhatsApp"
    log_activity(
        payment.case,
        ActivityEvent.PAYMENT_REMINDER_SENT,
        f"Payment reminder sent for {payment.payment_number} via {channel_label}.",
        actor=actor,
    )
    return message


@transaction.atomic
def request_refund(payment: Payment, *, actor, payload: dict) -> PaymentRefund:
    if payment.status != PaymentStatus.APPROVED:
        raise PaymentError("Refunds can only be requested for approved payments.", code="invalid_status")
    amount = _parse_amount(payload.get("amount"))
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise PaymentError("A refund reason is required.", code="invalid_reason")
    available = refundable_amount(payment)
    if amount > available:
        raise PaymentError(f"Refund cannot exceed {payment.currency} {available}.", code="invalid_refund_amount")
    from accounts.authorization import user_has_permission

    complete_now = bool(payload.get("complete")) and (
        getattr(actor, "is_superuser", False) or user_has_permission(actor, "payments.refund_payment")
    )
    now = timezone.now()
    sequence, refund_number = allocate_refund_number()
    refund = PaymentRefund.objects.create(
        sequence=sequence,
        refund_number=refund_number,
        payment=payment,
        amount=amount,
        reason=reason,
        status=RefundStatus.COMPLETED if complete_now else RefundStatus.PENDING_APPROVAL,
        requested_by=actor if getattr(actor, "is_authenticated", False) else None,
        approved_by=actor if complete_now and getattr(actor, "is_authenticated", False) else None,
        approved_at=now if complete_now else None,
        completed_by=actor if complete_now and getattr(actor, "is_authenticated", False) else None,
        completed_at=now if complete_now else None,
    )
    log_activity(payment.case, ActivityEvent.REFUND_REQUESTED, f"Refund {refund.refund_number} requested for {payment.payment_number} ({payment.currency} {amount}).", actor=actor)
    if complete_now:
        log_activity(payment.case, ActivityEvent.REFUND_COMPLETED, f"Refund {refund.refund_number} completed.", actor=actor)
    return refund


def approve_refund(refund: PaymentRefund, *, actor) -> PaymentRefund:
    if refund.status != RefundStatus.PENDING_APPROVAL:
        raise PaymentError("Only refunds pending approval can be approved.", code="invalid_status")
    refund.status = RefundStatus.APPROVED
    refund.approved_by = actor
    refund.approved_at = timezone.now()
    refund.save()
    log_activity(refund.payment.case, ActivityEvent.REFUND_APPROVED, f"Refund {refund.refund_number} approved.", actor=actor)
    return refund


def reject_refund(refund: PaymentRefund, *, actor, reason: str) -> PaymentRefund:
    if refund.status != RefundStatus.PENDING_APPROVAL:
        raise PaymentError("Only refunds pending approval can be rejected.", code="invalid_status")
    reason = str(reason or "").strip()
    if not reason:
        raise PaymentError("rejection_reason is required.", code="invalid_reason")
    refund.status = RefundStatus.REJECTED
    refund.rejected_by = actor
    refund.rejected_at = timezone.now()
    refund.rejection_reason = reason
    refund.save()
    log_activity(refund.payment.case, ActivityEvent.REFUND_REJECTED, f"Refund {refund.refund_number} rejected: {reason}", actor=actor)
    return refund


def complete_refund(refund: PaymentRefund, *, actor) -> PaymentRefund:
    if refund.status != RefundStatus.APPROVED:
        raise PaymentError("Only approved refunds can be completed.", code="invalid_status")
    refund.status = RefundStatus.COMPLETED
    refund.completed_by = actor
    refund.completed_at = timezone.now()
    refund.save()
    log_activity(refund.payment.case, ActivityEvent.REFUND_COMPLETED, f"Refund {refund.refund_number} completed ({refund.payment.currency} {refund.amount}).", actor=actor)
    return refund


def filter_payments(queryset, params):
    status = (params.get("status") or "all").strip().lower()
    if status in {"", "all"}:
        pass
    elif status == "overdue":
        queryset = queryset.filter(status__in=UNPAID_STATUSES, expected_date__lt=timezone.now())
    elif status in PaymentStatus.values:
        queryset = queryset.filter(status=status)
    else:
        raise PaymentError("Unknown payment status.", code="invalid_status")

    payment_type = params.get("payment_type") or params.get("type")
    if payment_type not in (None, "", "all"):
        if payment_type not in PaymentType.values:
            raise PaymentError("Unknown payment type.", code="invalid_type")
        queryset = queryset.filter(payment_type=payment_type)

    method = params.get("payment_method") or params.get("method")
    if method not in (None, "", "all"):
        if method not in PaymentMethod.values:
            raise PaymentError("Unknown payment method.", code="invalid_method")
        queryset = queryset.filter(payment_method=method)

    property_id = params.get("property")
    if property_id not in (None, "", "all"):
        try:
            queryset = queryset.filter(case__property_id=int(property_id))
        except (TypeError, ValueError) as exc:
            raise PaymentError("property must be an integer.", code="invalid_property") from exc

    staff = params.get("staff") or params.get("assigned_staff")
    if staff not in (None, "", "all"):
        try:
            queryset = queryset.filter(case__assigned_to_id=int(staff))
        except (TypeError, ValueError) as exc:
            raise PaymentError("staff must be an integer.", code="invalid_assignee") from exc

    stage = params.get("case_stage") or params.get("stage")
    if stage not in (None, "", "all"):
        queryset = queryset.filter(case__stage=stage)

    source = (params.get("source") or "").strip().lower()
    if source not in (None, "", "all"):
        queryset = queryset.filter(case__source=source)

    case_id = params.get("case") or params.get("case_id")
    if case_id not in (None, "", "all"):
        try:
            queryset = queryset.filter(case_id=int(case_id))
        except (TypeError, ValueError) as exc:
            raise PaymentError("case must be an integer.", code="invalid_case") from exc

    customer_id = params.get("customer") or params.get("customer_id")
    if customer_id not in (None, "", "all"):
        try:
            queryset = queryset.filter(case__customer_id=int(customer_id))
        except (TypeError, ValueError) as exc:
            raise PaymentError("customer must be an integer.", code="invalid_customer") from exc

    date_field = (params.get("date_field") or "expected_date").strip()
    field_map = {"expected_date": "expected_date", "paid_at": "paid_at", "created_at": "created_at", "paid": "paid_at", "expected": "expected_date", "created": "created_at"}
    if date_field not in field_map:
        raise PaymentError("Unknown date field.", code="invalid_date_field")
    lookup = field_map[date_field]
    due = (params.get("due") or params.get("date") or "all").strip().lower()
    if due not in (None, "", "all"):
        now = timezone.now()
        local = timezone.localtime(now)
        start_today = local.replace(hour=0, minute=0, second=0, microsecond=0)
        if due == "today":
            queryset = queryset.filter(**{f"{lookup}__gte": start_today, f"{lookup}__lt": start_today + timedelta(days=1)})
        elif due == "tomorrow":
            queryset = queryset.filter(**{f"{lookup}__gte": start_today + timedelta(days=1), f"{lookup}__lt": start_today + timedelta(days=2)})
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
        elif due == "overdue":
            queryset = queryset.filter(status__in=UNPAID_STATUSES, expected_date__lt=now)
        elif due == "custom":
            date_from = parse_date_bound(params.get("date_from") or params.get("from"))
            date_to = parse_date_bound(params.get("date_to") or params.get("to"), end=True)
            if date_from is not None:
                queryset = queryset.filter(**{f"{lookup}__gte": date_from})
            if date_to is not None:
                queryset = queryset.filter(**{f"{lookup}__lte": date_to})
        else:
            raise PaymentError("Unknown date filter.", code="invalid_due_filter")

    search = (params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(payment_number__icontains=search)
            | Q(notes__icontains=search)
            | Q(case__case_number__icontains=search)
            | Q(case__title__icontains=search)
            | Q(case__customer__name__icontains=search)
            | Q(case__customer__phone__icontains=search)
            | Q(case__customer__email__icontains=search)
        )
    return queryset


def order_payments(queryset, params):
    allowed = {"expected_date", "-expected_date", "created_at", "-created_at", "amount", "-amount", "updated_at", "-updated_at"}
    ordering = (params.get("ordering") or params.get("sort") or "-created_at").strip()
    if ordering not in allowed:
        raise PaymentError("Unknown sort field.", code="invalid_ordering")
    field = ordering.lstrip("-")
    descending = ordering.startswith("-")
    from django.db.models import F

    expression = F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_last=True)
    return queryset.order_by(expression, "-id" if descending else "id")


def payment_summary(user) -> dict:
    queryset = accessible_payments(user)
    unpaid = queryset.filter(status__in=UNPAID_STATUSES)
    return {
        "expected": unpaid.aggregate(total=Sum("amount"))["total"] or Decimal("0"),
        "pending_approval": queryset.filter(status=PaymentStatus.PENDING_APPROVAL).aggregate(total=Sum("amount"))["total"] or Decimal("0"),
        "approved": queryset.filter(status=PaymentStatus.APPROVED).aggregate(total=Sum("amount"))["total"] or Decimal("0"),
        "deposits": queryset.filter(status=PaymentStatus.APPROVED, payment_type=PaymentType.DEPOSIT).aggregate(total=Sum("amount"))["total"] or Decimal("0"),
        "refunded": PaymentRefund.objects.filter(
            payment_id__in=queryset.values("pk"),
            status=RefundStatus.COMPLETED,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0"),
    }


def payment_filter_staff(user):
    return follow_up_filter_staff(user)


def payment_filter_properties(user):
    return follow_up_filter_properties(user)
