from django.contrib import admin

from pipeline.models import Opportunity


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "customer", "property", "stage", "value", "assigned_to", "updated_at")
    list_filter = ("stage",)
    search_fields = ("title", "customer__name", "property__name")
    readonly_fields = ("created_at", "updated_at")
