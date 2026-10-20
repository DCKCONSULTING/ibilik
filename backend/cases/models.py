from django.conf import settings
from django.db import models
from django.utils import timezone

from pipeline.models import FinanceStatus, PipelineStage


class FollowUpType(models.TextChoices):
    CALL_CUSTOMER = "call_customer", "Call Customer"
    SEND_QUOTE = "send_quote", "Send Quote"
    FOLLOW_UP = "follow_up", "Follow Up"
    REQUEST_INFORMATION = "request_information", "Request Information"
    CHECK_AVAILABILITY = "check_availability", "Check Availability"
    INTERNAL_REVIEW = "internal_review", "Internal Review"
    PAYMENT_FOLLOW_UP = "payment_follow_up", "Payment Follow Up"
    OTHER = "other", "Other"


class FollowUpStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class ActivityEvent(models.TextChoices):
    CREATED = "created", "Case created"
    ASSIGNED = "assigned", "Staff assigned"
    PROPERTY_CHANGED = "property_changed", "Property changed"
    STAGE_CHANGED = "stage_changed", "Stage changed"
    FOLLOW_UP_CREATED = "follow_up_created", "Follow-up created"
    FOLLOW_UP_COMPLETED = "follow_up_completed", "Follow-up completed"
    FOLLOW_UP_CANCELLED = "follow_up_cancelled", "Follow-up cancelled"
    FOLLOW_UP_REASSIGNED = "follow_up_reassigned", "Follow-up reassigned"
    FOLLOW_UP_RESCHEDULED = "follow_up_rescheduled", "Follow-up rescheduled"
    QUOTE_CREATED = "quote_created", "Quote created"
    APPROVED = "approved", "Approval performed"
    MOVED_TO_FINANCE = "moved_to_finance", "Moved to finance"
    NOTE_ADDED = "note_added", "Note added"
    CLOSED = "closed", "Case closed"
    REOPENED = "reopened", "Case reopened"
    PAYMENT_CREATED = "payment_created", "Payment created"
    PAYMENT_PROOF_UPLOADED = "payment_proof_uploaded", "Payment proof uploaded"
    PAYMENT_SUBMITTED = "payment_submitted", "Payment submitted for approval"
    PAYMENT_APPROVED = "payment_approved", "Payment approved"
    PAYMENT_REJECTED = "payment_rejected", "Payment rejected"
    PAYMENT_CANCELLED = "payment_cancelled", "Payment cancelled"
    PAYMENT_REMINDER_SENT = "payment_reminder_sent", "Payment reminder sent"
    REFUND_REQUESTED = "refund_requested", "Refund requested"
    REFUND_APPROVED = "refund_approved", "Refund approved"
    REFUND_REJECTED = "refund_rejected", "Refund rejected"
    REFUND_COMPLETED = "refund_completed", "Refund completed"
    CHARGE_CREATED = "charge_created", "Charge created"
    CHARGE_VOIDED = "charge_voided", "Charge voided"
    PENALTY_CREATED = "penalty_created", "Penalty created"


class Case(models.Model):
    sequence = models.PositiveIntegerField(unique=True)
    case_number = models.CharField(max_length=32, unique=True)
    customer = models.ForeignKey(
        "crm.Customer",
        on_delete=models.CASCADE,
        related_name="cases",
    )
    property = models.ForeignKey(
        "accounts.Property",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cases",
    )
    location = models.ForeignKey(
        "locations.Location",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cases",
    )
    originating_conversation = models.ForeignKey(
        "crm.Conversation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="originating_cases",
    )
    originating_message = models.ForeignKey(
        "crm.Message",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="originating_cases",
    )
    conversations = models.ManyToManyField(
        "crm.Conversation",
        through="CaseConversation",
        related_name="cases",
        blank=True,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    original_request = models.TextField(blank=True, default="")
    source = models.CharField(max_length=16, blank=True, default="")
    stage = models.CharField(
        max_length=16,
        choices=PipelineStage.choices,
        default=PipelineStage.NEW,
    )
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quote_notes = models.TextField(blank=True, default="")
    staff_notes = models.TextField(blank=True, default="")
    finance_status = models.CharField(
        max_length=16,
        choices=FinanceStatus.choices,
        default=FinanceStatus.NONE,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_cases",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_cases",
    )
    quoted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    finance_moved_at = models.DateTimeField(null=True, blank=True)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    actual_check_in = models.DateTimeField(null=True, blank=True)
    actual_check_out = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    external_key = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["external_key"],
                condition=~models.Q(external_key=""),
                name="uniq_case_external_key",
            )
        ]
        indexes = [
            models.Index(fields=["case_number"]),
            models.Index(fields=["customer"]),
            models.Index(fields=["property"]),
            models.Index(fields=["location"]),
            models.Index(fields=["stage"]),
            models.Index(fields=["assigned_to"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
            models.Index(fields=["check_in"]),
            models.Index(fields=["check_out"]),
        ]

    def __str__(self) -> str:
        return f"{self.case_number} {self.title}"


class CaseConversation(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="case_conversations")
    conversation = models.ForeignKey(
        "crm.Conversation",
        on_delete=models.CASCADE,
        related_name="case_links",
    )
    is_originating = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["case", "conversation"], name="uniq_case_conversation"),
        ]


class CaseFollowUp(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="follow_ups")
    follow_up_type = models.CharField(max_length=32, choices=FollowUpType.choices, default=FollowUpType.FOLLOW_UP)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="case_follow_ups",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=FollowUpStatus.choices, default=FollowUpStatus.PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_case_follow_ups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at", "id"]
        indexes = [
            models.Index(fields=["case"]),
            models.Index(fields=["assigned_to"]),
            models.Index(fields=["status"]),
            models.Index(fields=["due_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    def is_overdue(self) -> bool:
        if self.status != FollowUpStatus.PENDING or self.due_at is None:
            return False
        return self.due_at < timezone.now()


class CaseActivity(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="activities")
    event_type = models.CharField(max_length=32, choices=ActivityEvent.choices)
    message = models.CharField(max_length=500)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="case_activities",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["case"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return self.message
