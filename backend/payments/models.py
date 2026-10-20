from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class PaymentType(models.TextChoices):
    DEPOSIT = "deposit", "Deposit"
    PAYMENT = "payment", "Payment"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    BANK_TRANSFER = "bank_transfer", "Bank Transfer"
    CREDIT_CARD = "credit_card", "Credit Card"
    DEBIT_CARD = "debit_card", "Debit Card"
    ONLINE = "online", "Online Payment"
    OTHER = "other", "Other"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROOF_SUBMITTED = "proof_submitted", "Proof Submitted"
    PENDING_APPROVAL = "pending_approval", "Pending Approval"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class RefundStatus(models.TextChoices):
    REQUESTED = "requested", "Refund Requested"
    PENDING_APPROVAL = "pending_approval", "Pending Approval"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    COMPLETED = "completed", "Refunded"
    CANCELLED = "cancelled", "Cancelled"


def payment_attachment_path(instance, filename):
    return f"payments/{instance.payment_id}/{filename}"


class Payment(models.Model):
    sequence = models.PositiveIntegerField(unique=True)
    payment_number = models.CharField(max_length=32, unique=True)
    case = models.ForeignKey("cases.Case", on_delete=models.CASCADE, related_name="case_payments")
    payment_type = models.CharField(max_length=16, choices=PaymentType.choices, default=PaymentType.PAYMENT)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    currency = models.CharField(max_length=8, default="MYR")
    payment_method = models.CharField(max_length=24, choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER)
    status = models.CharField(max_length=24, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    expected_date = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    idempotency_key = models.CharField(max_length=64, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_payments",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_payments",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rejected_payments",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expected_date", "-id"]
        indexes = [
            models.Index(fields=["payment_number"]),
            models.Index(fields=["case"]),
            models.Index(fields=["status"]),
            models.Index(fields=["payment_type"]),
            models.Index(fields=["expected_date"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payment_amount_positive"),
            models.UniqueConstraint(
                fields=["case", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_payment_case_idempotency",
            ),
        ]

    def __str__(self) -> str:
        return self.payment_number

    def is_overdue(self) -> bool:
        if self.status in {PaymentStatus.APPROVED, PaymentStatus.CANCELLED, PaymentStatus.REJECTED}:
            return False
        if self.expected_date is None:
            return False
        return self.expected_date < timezone.now()

    def calendar_status(self) -> str:
        if self.status == PaymentStatus.APPROVED:
            return "received"
        if self.status in {PaymentStatus.CANCELLED, PaymentStatus.REJECTED}:
            return self.status
        if self.is_overdue():
            return "overdue"
        return "expected"


class PaymentAttachment(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=payment_attachment_path)
    original_name = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=128, blank=True, default="")
    description = models.CharField(max_length=255, blank=True, default="")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_attachments",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at", "-id"]

    def __str__(self) -> str:
        return self.original_name or f"Attachment {self.pk}"


class PaymentRefund(models.Model):
    sequence = models.PositiveIntegerField(unique=True)
    refund_number = models.CharField(max_length=32, unique=True)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=24, choices=RefundStatus.choices, default=RefundStatus.REQUESTED)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requested_refunds",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_refunds",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rejected_refunds",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_refunds",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [
            models.Index(fields=["refund_number"]),
            models.Index(fields=["payment"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="refund_amount_positive"),
        ]

    def __str__(self) -> str:
        return self.refund_number


class ChargeKind(models.TextChoices):
    CHARGE = "charge", "Charge"
    PENALTY = "penalty", "Penalty"
    DISCOUNT = "discount", "Discount"
    TAX = "tax", "Tax"
    ADJUSTMENT = "adjustment", "Adjustment"


class ChargeStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    VOIDED = "voided", "Voided"


class ChargeCategory(models.TextChoices):
    EXTRA_BED = "extra_bed", "Extra bed"
    FOOD_BEVERAGE = "food_beverage", "Food and beverage"
    LAUNDRY = "laundry", "Laundry"
    ROOM_SERVICE = "room_service", "Room service"
    LATE_CHECKOUT = "late_checkout", "Late checkout"
    ADDITIONAL_GUEST = "additional_guest", "Additional guest"
    DAMAGE = "damage", "Damage charge"
    CANCELLATION = "cancellation", "Cancellation fee"
    NO_SHOW = "no_show", "No-show fee"
    LOST_KEY = "lost_key", "Lost key"
    EXTRA_CLEANING = "extra_cleaning", "Extra cleaning"
    OTHER = "other", "Other"


class CaseCharge(models.Model):
    case = models.ForeignKey("cases.Case", on_delete=models.CASCADE, related_name="case_charges")
    kind = models.CharField(max_length=16, choices=ChargeKind.choices, default=ChargeKind.CHARGE)
    category = models.CharField(max_length=32, choices=ChargeCategory.choices, default=ChargeCategory.OTHER)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default="MYR")
    reason = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=ChargeStatus.choices, default=ChargeStatus.ACTIVE)
    occurred_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=64, blank=True, default="")
    original_charge = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reversals",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_case_charges",
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="voided_case_charges",
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["case"]),
            models.Index(fields=["kind"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["case", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_case_charge_idempotency",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.amount}"
