from django.conf import settings
from django.db import models
from django.utils import timezone


class MatchRequestType(models.TextChoices):
    BOOKING = "booking", "New booking request"
    QUOTE = "quote", "New quote request"
    PAYMENT = "payment", "Payment-related request"
    INQUIRY = "inquiry", "Customer inquiry"
    PROPERTY = "property", "Property/location request"
    CANCELLATION = "cancellation", "Cancellation request"
    MODIFICATION = "modification", "Modification request"
    OTHER = "other", "Other request"


class MatchRequestStatus(models.TextChoices):
    NEW = "new", "New"
    UNASSIGNED = "unassigned", "Unassigned"
    ASSIGNED = "assigned", "Assigned"
    IN_PROGRESS = "in_progress", "In Progress"
    WAITING = "waiting", "Waiting"
    RESOLVED = "resolved", "Resolved"
    CANCELLED = "cancelled", "Cancelled"


class MatchRequestPriority(models.TextChoices):
    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class MatchHistoryAction(models.TextChoices):
    CREATED = "created", "Request created"
    ASSIGNED = "assigned", "Request assigned"
    REASSIGNED = "reassigned", "Request reassigned"
    UNASSIGNED = "unassigned", "Request unassigned"
    AUTO_ASSIGNED = "auto_assigned", "Automatically assigned"
    AUTO_UNASSIGNED = "auto_unassigned", "Left unassigned"
    STATUS_CHANGED = "status_changed", "Status changed"
    PRIORITY_CHANGED = "priority_changed", "Priority changed"
    NOTE_ADDED = "note_added", "Note added"
    RESOLVED = "resolved", "Request resolved"
    CANCELLED = "cancelled", "Request cancelled"


class MatchAssignmentMethod(models.TextChoices):
    AUTOMATIC = "automatic", "Automatic"
    MANUAL = "manual", "Manual"
    REASSIGNED = "reassigned", "Reassigned"


OPEN_STATUSES = (
    MatchRequestStatus.NEW,
    MatchRequestStatus.UNASSIGNED,
    MatchRequestStatus.ASSIGNED,
    MatchRequestStatus.IN_PROGRESS,
    MatchRequestStatus.WAITING,
)

ACTIVE_WORKLOAD_STATUSES = (
    MatchRequestStatus.NEW,
    MatchRequestStatus.ASSIGNED,
    MatchRequestStatus.IN_PROGRESS,
    MatchRequestStatus.WAITING,
)


class MatchRequest(models.Model):
    sequence = models.PositiveIntegerField(unique=True)
    request_number = models.CharField(max_length=32, unique=True)
    request_type = models.CharField(
        max_length=24,
        choices=MatchRequestType.choices,
        default=MatchRequestType.OTHER,
    )
    source_module = models.CharField(max_length=32)
    source_ref = models.CharField(max_length=128)
    customer = models.ForeignKey(
        "crm.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="match_requests",
    )
    property = models.ForeignKey(
        "accounts.Property",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="match_requests",
    )
    location = models.ForeignKey(
        "locations.Location",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="match_requests",
    )
    related_case = models.ForeignKey(
        "cases.Case",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="match_requests",
    )
    related_quote = models.ForeignKey(
        "quotes.Quote",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="match_requests",
    )
    related_payment = models.ForeignKey(
        "payments.Payment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="match_requests",
    )
    subject = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    priority = models.CharField(
        max_length=16,
        choices=MatchRequestPriority.choices,
        default=MatchRequestPriority.NORMAL,
    )
    status = models.CharField(
        max_length=16,
        choices=MatchRequestStatus.choices,
        default=MatchRequestStatus.NEW,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_match_requests",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="match_requests_assigned",
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    assignment_method = models.CharField(
        max_length=16,
        choices=MatchAssignmentMethod.choices,
        blank=True,
        default="",
    )
    workload_at_assignment = models.PositiveIntegerField(null=True, blank=True)
    unassigned_reason = models.CharField(max_length=255, blank=True, default="")
    due_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_match_requests",
    )
    internal_notes = models.TextField(blank=True, default="")
    resolution_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=["source_module", "source_ref"], name="uniq_match_source_ref"),
        ]
        indexes = [
            models.Index(fields=["request_number"]),
            models.Index(fields=["request_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["assigned_to"]),
            models.Index(fields=["property"]),
            models.Index(fields=["customer"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["due_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.request_number} {self.subject}"

    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    def is_overdue(self) -> bool:
        if self.due_at is None or not self.is_open():
            return False
        return self.due_at < timezone.now()


class MatchRequestNote(models.Model):
    request = models.ForeignKey(MatchRequest, on_delete=models.CASCADE, related_name="notes")
    body = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="match_request_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        default_permissions = ()


class MatchRequestHistory(models.Model):
    request = models.ForeignKey(MatchRequest, on_delete=models.CASCADE, related_name="history")
    action = models.CharField(max_length=32, choices=MatchHistoryAction.choices)
    previous_value = models.CharField(max_length=255, blank=True, default="")
    new_value = models.CharField(max_length=255, blank=True, default="")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="match_request_history",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        default_permissions = ()


class MatchSettings(models.Model):
    """Account-wide Match assignment settings. Single-tenant singleton."""

    auto_assign_enabled = models.BooleanField(default=True)
    property_staff_only = models.BooleanField(default=True)
    org_wide_when_no_property = models.BooleanField(default=True)
    assignment_mode = models.CharField(max_length=32, default="lowest_workload")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "match settings"
        verbose_name_plural = "match settings"
        default_permissions = ()

    def __str__(self) -> str:
        return "Match assignment settings"

