from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User

from accounts.models import AccessControl, Property, PropertyStaffAssignment, Role, UserPropertyAccess


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class IbilikUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_active", "is_staff", "is_superuser", "last_login")
    list_filter = ("is_active", "is_staff", "is_superuser", "groups")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("username",)
    filter_horizontal = ("groups",)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "usable_password", "password1", "password2"),
            },
        ),
    )


@admin.register(Group)
class IbilikGroupAdmin(GroupAdmin):
    list_display = ("name",)


@admin.register(AccessControl)
class AccessControlAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "property_type", "city", "country", "status", "currency", "rate", "created_at")
    list_filter = ("property_type", "status", "country", "region", "city")
    search_fields = ("name", "code", "region", "city", "address_line1")
    filter_horizontal = ("staff",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(PropertyStaffAssignment)
class PropertyStaffAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "property", "role", "reports_to", "is_active", "assigned_at")
    list_filter = ("role", "is_active", "property")
    search_fields = ("user__username", "user__first_name", "user__last_name", "property__name")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "level", "parent", "is_system_role", "is_active", "all_properties")
    list_filter = ("is_system_role", "is_builtin", "is_active", "all_properties")
    search_fields = ("name", "code")
    readonly_fields = ("code",)


@admin.register(UserPropertyAccess)
class UserPropertyAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "mode")
    list_filter = ("mode",)
    search_fields = ("user__username", "user__first_name", "user__last_name")
