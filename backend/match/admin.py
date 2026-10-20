from django.contrib import admin

from match.models import MatchRequest, MatchRequestHistory, MatchRequestNote, MatchSettings


@admin.register(MatchRequest)
class MatchRequestAdmin(admin.ModelAdmin):
    list_display = ("request_number", "request_type", "status", "priority", "customer", "property", "assigned_to", "created_at")
    list_filter = ("request_type", "status", "priority")
    search_fields = ("request_number", "subject", "source_ref")


@admin.register(MatchRequestNote)
class MatchRequestNoteAdmin(admin.ModelAdmin):
    list_display = ("request", "created_by", "created_at")


@admin.register(MatchRequestHistory)
class MatchRequestHistoryAdmin(admin.ModelAdmin):
    list_display = ("request", "action", "actor", "created_at")
    list_filter = ("action",)


@admin.register(MatchSettings)
class MatchSettingsAdmin(admin.ModelAdmin):
    list_display = ("auto_assign_enabled", "property_staff_only", "org_wide_when_no_property", "assignment_mode")
