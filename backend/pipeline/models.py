from django.conf import settings
from django.db import models


class PipelineStage(models.TextChoices):
    NEW = "new", "New"
    QUALIFIED = "qualified", "Qualified"
    QUOTED = "quoted", "Quoted"
    NEGOTIATING = "negotiating", "Negotiating"
    WON = "won", "Won"
    LOST = "lost", "Lost"


PIPELINE_STAGE_ORDER = (
    PipelineStage.NEW,
    PipelineStage.QUALIFIED,
    PipelineStage.QUOTED,
    PipelineStage.NEGOTIATING,
    PipelineStage.WON,
    PipelineStage.LOST,
)

PIPELINE_STAGES = tuple(
    {"id": value, "label": label, "order": index}
    for index, (value, label) in enumerate(PipelineStage.choices, start=1)
)


class FinanceStatus(models.TextChoices):
    NONE = "none", "Not sent"
    SENT = "sent", "Sent to finance"


class Opportunity(models.Model):
    customer = models.ForeignKey(
        "crm.Customer",
        on_delete=models.CASCADE,
        related_name="opportunities",
    )
    property = models.ForeignKey(
        "accounts.Property",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opportunities",
    )
    conversation = models.ForeignKey(
        "crm.Conversation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opportunities",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
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
        related_name="assigned_opportunities",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_opportunities",
    )
    quoted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    finance_moved_at = models.DateTimeField(null=True, blank=True)
    external_key = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["external_key"],
                condition=~models.Q(external_key=""),
                name="uniq_pipeline_opportunity_external_key",
            )
        ]
        indexes = [
            models.Index(fields=["stage"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self) -> str:
        return self.title
