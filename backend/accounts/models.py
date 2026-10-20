from datetime import time

from django.conf import settings
from django.db import models


class AccessControl(models.Model):
    """Marker model that owns iBilik CRM application permissions.

    Authorization still uses Django's user/group permission tables. This
    model exists so those permissions have a stable content type.
    """

    class Meta:
        verbose_name = "access control"
        verbose_name_plural = "access controls"
        default_permissions = ()
        permissions = []


class PropertyType(models.TextChoices):
    HOTEL = "hotel", "Hotel"
    RESORT = "resort", "Resort"
    BOUTIQUE_HOTEL = "boutique_hotel", "Boutique Hotel"
    BUSINESS_HOTEL = "business_hotel", "Business Hotel"
    VILLA = "villa", "Villa"
    APARTMENT = "apartment", "Apartment"
    HOSTEL = "hostel", "Hostel"
    GUESTHOUSE = "guesthouse", "Guesthouse"


class PropertyStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class Property(models.Model):
    """Hotel/property managed through iBilik CRM.

    Future CRM records (customers, inquiries, quotes, bookings, payments,
    availability, conversations, calendar events) should foreign-key this
    model rather than storing property identifiers as text or JSON.
    """

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=32, blank=True, default="")
    property_type = models.CharField(
        max_length=32,
        choices=PropertyType.choices,
        default=PropertyType.HOTEL,
    )
    description = models.TextField(blank=True, default="")
    country = models.CharField(max_length=64, default="Malaysia")
    region = models.CharField(max_length=128)
    city = models.CharField(max_length=128)
    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    postal_code = models.CharField(max_length=16, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    website = models.CharField(max_length=255, blank=True, default="")
    currency = models.CharField(max_length=8, default="MYR")
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=16,
        choices=PropertyStatus.choices,
        default=PropertyStatus.ACTIVE,
    )
    check_in_time = models.TimeField(default=time(15, 0))
    check_out_time = models.TimeField(default=time(12, 0))
    timezone = models.CharField(max_length=64, default="Asia/Kuala_Lumpur")
    star_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    amenities = models.JSONField(default=list, blank=True)
    staff = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="assigned_properties",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "property"
        verbose_name_plural = "properties"
        ordering = ["name", "id"]
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=~models.Q(code=""),
                name="uniq_property_code",
            )
        ]

    def __str__(self) -> str:
        return self.name


class PropertyStaffAssignment(models.Model):
    """Property-scoped staff assignment, role, and reporting manager.

    Property access still uses Property.staff. This record stores the
    organizational role (from the /api/roles catalog) and reporting line
    for one user at one property. It does not change the user's global
    permission group by itself.
    """

    property = models.ForeignKey(
        "accounts.Property",
        on_delete=models.CASCADE,
        related_name="staff_assignments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="property_staff_assignments",
    )
    role = models.CharField(max_length=32, blank=True, default="")
    reports_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="property_direct_reports",
    )
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="property_staff_assigned",
    )

    class Meta:
        verbose_name = "property staff assignment"
        verbose_name_plural = "property staff assignments"
        ordering = ["user__first_name", "user__last_name", "user__username", "id"]
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=["property", "user"], name="uniq_property_staff_assignment"),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.property}"


class UserPropertyAccess(models.Model):
    """Per-user property access mode. Independent of role/permissions."""

    class Mode(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned properties"
        GLOBAL = "GLOBAL", "All properties"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="property_access_profile",
    )
    mode = models.CharField(
        max_length=16,
        choices=Mode.choices,
        default=Mode.ASSIGNED,
    )

    class Meta:
        verbose_name = "user property access"
        verbose_name_plural = "user property access"
        default_permissions = ()

    def __str__(self) -> str:
        return f"{self.user} ({self.mode})"


class Role(models.Model):
    """Business role metadata layered on Django groups.

    SUPERUSER is stored for display and hierarchy only. It is not a
    Django group. ``User.is_superuser`` remains the authorization source.
    """

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    description = models.TextField(blank=True, default="")
    level = models.PositiveSmallIntegerField()
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    is_system_role = models.BooleanField(default=False)
    is_builtin = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    all_properties = models.BooleanField(default=False)
    can_manage_lower_users = models.BooleanField(default=False)
    can_assign_property_staff = models.BooleanField(default=False)
    group = models.OneToOneField(
        "auth.Group",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crm_role",
    )

    class Meta:
        verbose_name = "role"
        verbose_name_plural = "roles"
        ordering = ["level", "name", "id"]
        default_permissions = ()

    def __str__(self) -> str:
        return self.name
