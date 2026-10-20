from django.contrib import admin

from locations.models import CleaningTask, Location, LocationStatusHistory, MaintenanceIssue


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "location_type", "property", "status", "is_bookable", "active", "capacity", "base_rate")
    list_filter = ("location_type", "status", "is_bookable", "active", "property")
    search_fields = ("name", "code", "property__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(LocationStatusHistory)
class LocationStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("location", "previous_status", "new_status", "changed_by", "created_at")
    list_filter = ("new_status",)
    search_fields = ("location__name", "reason")


@admin.register(CleaningTask)
class CleaningTaskAdmin(admin.ModelAdmin):
    list_display = ("location", "status", "assigned_to", "started_at", "completed_at")
    list_filter = ("status",)


@admin.register(MaintenanceIssue)
class MaintenanceIssueAdmin(admin.ModelAdmin):
    list_display = ("title", "location", "property", "priority", "status", "assigned_to", "started_at", "resolved_at")
    list_filter = ("status", "priority", "property")
    search_fields = ("title", "location__name")
