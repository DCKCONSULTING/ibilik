from django.contrib import admin

from cases.models import Case, CaseActivity, CaseFollowUp


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("case_number", "title", "customer", "property", "stage", "assigned_to", "updated_at")
    list_filter = ("stage", "source")
    search_fields = ("case_number", "title", "customer__name", "original_request")
    readonly_fields = ("case_number", "sequence", "original_request", "created_at", "updated_at")


@admin.register(CaseFollowUp)
class CaseFollowUpAdmin(admin.ModelAdmin):
    list_display = ("title", "case", "assigned_to", "due_at", "status")
    list_filter = ("status", "follow_up_type")


@admin.register(CaseActivity)
class CaseActivityAdmin(admin.ModelAdmin):
    list_display = ("created_at", "case", "event_type", "message", "actor")
    list_filter = ("event_type",)
