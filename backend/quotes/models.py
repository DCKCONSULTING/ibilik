from django.conf import settings
from django.db import models
from django.utils import timezone


class QuoteStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class Quote(models.Model):
    sequence = models.PositiveIntegerField(unique=True)
    quote_number = models.CharField(max_length=32, unique=True)
    case = models.ForeignKey("cases.Case", on_delete=models.CASCADE, related_name="case_quotes")
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, default="MYR")
    status = models.CharField(max_length=16, choices=QuoteStatus.choices, default=QuoteStatus.PENDING)
    valid_until = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_quotes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["quote_number"]),
            models.Index(fields=["case"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["valid_until"]),
        ]

    def __str__(self) -> str:
        return self.quote_number

    def is_expired(self) -> bool:
        if self.status != QuoteStatus.PENDING or self.valid_until is None:
            return False
        return self.valid_until < timezone.now()
