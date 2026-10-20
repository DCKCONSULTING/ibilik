from django.db import models


class BedType(models.TextChoices):
    KING = "king", "King"
    QUEEN = "queen", "Queen"
    TWIN = "twin", "Twin"
    DOUBLE = "double", "Double"
    SINGLE = "single", "Single"
    SOFA = "sofa", "Sofa"
    OTHER = "other", "Other"


class LocationType(models.TextChoices):
    """Controlled resource type. New types can be added without a schema change."""

    ROOM = "room", "Room"
    TABLE = "table", "Table"
    MEETING_ROOM = "meeting_room", "Meeting Room"
    VILLA = "villa", "Villa"
    APARTMENT = "apartment", "Apartment"
    SUITE = "suite", "Suite"
    PARKING = "parking", "Parking"
    DESK = "desk", "Desk"
    OTHER = "other", "Other"


class LocationStatus(models.TextChoices):
    """Staff-controlled operational status. Occupancy is never stored here."""

    AVAILABLE = "available", "Available"
    DIRTY = "dirty", "Dirty"
    CLEANING = "cleaning", "Cleaning"
    MAINTENANCE = "maintenance", "Maintenance"
    OUT_OF_ORDER = "out_of_order", "Out of order"
    INSPECTION = "inspection", "Inspection"
    INACTIVE = "inactive", "Inactive"


class CleaningStatus(models.TextChoices):
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class MaintenanceStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In progress"
    RESOLVED = "resolved", "Resolved"
    CANCELLED = "cancelled", "Cancelled"


class MaintenancePriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class Location(models.Model):
    """Generic physical resource belonging to exactly one Property.

    A location can be a room, table, villa, parking space, or any other
    assignable resource. Business logic should treat locations generically
    and only branch on ``location_type`` for presentation or type-specific
    rules.
    """

    property = models.ForeignKey(
        "accounts.Property",
        on_delete=models.CASCADE,
        related_name="locations",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=32, blank=True, default="")
    location_type = models.CharField(
        max_length=32,
        choices=LocationType.choices,
        default=LocationType.ROOM,
    )
    description = models.TextField(blank=True, default="")
    capacity = models.PositiveIntegerField(null=True, blank=True)
    max_adults = models.PositiveIntegerField(null=True, blank=True)
    max_children = models.PositiveIntegerField(null=True, blank=True)
    floor = models.CharField(max_length=16, blank=True, default="")
    bed_type = models.CharField(max_length=16, choices=BedType.choices, blank=True, default="")
    bed_count = models.PositiveIntegerField(null=True, blank=True)
    base_rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=LocationStatus.choices,
        default=LocationStatus.AVAILABLE,
    )
    is_bookable = models.BooleanField(default=True)
    amenities = models.JSONField(default=list, blank=True)
    size_sqm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "location"
        verbose_name_plural = "locations"
        ordering = ["name", "id"]
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["property", "code"],
                condition=~models.Q(code=""),
                name="uniq_location_property_code",
            )
        ]
        indexes = [
            models.Index(fields=["property"]),
            models.Index(fields=["location_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["active"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.property})"


class LocationStatusHistory(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="status_history")
    previous_status = models.CharField(max_length=16, blank=True, default="")
    new_status = models.CharField(max_length=16)
    reason = models.CharField(max_length=255, blank=True, default="")
    changed_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="location_status_changes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class CleaningTask(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="cleaning_tasks")
    assigned_to = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_cleaning_tasks",
    )
    created_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_cleaning_tasks",
    )
    status = models.CharField(max_length=16, choices=CleaningStatus.choices, default=CleaningStatus.IN_PROGRESS)
    notes = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class MaintenanceIssue(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="maintenance_issues")
    property = models.ForeignKey(
        "accounts.Property",
        on_delete=models.CASCADE,
        related_name="maintenance_issues",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    priority = models.CharField(max_length=16, choices=MaintenancePriority.choices, default=MaintenancePriority.MEDIUM)
    status = models.CharField(max_length=16, choices=MaintenanceStatus.choices, default=MaintenanceStatus.OPEN)
    assigned_to = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_maintenance_issues",
    )
    created_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_maintenance_issues",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    expected_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
