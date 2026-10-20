from django.conf import settings
from django.db import models


class Channel(models.TextChoices):
    WEBSITE = "website", "Website"
    WHATSAPP = "whatsapp", "WhatsApp"
    FACEBOOK = "facebook", "Facebook Messenger"


class IdentifierType(models.TextChoices):
    PHONE = "phone", "Phone"
    EMAIL = "email", "Email"
    FACEBOOK_PSID = "facebook_psid", "Facebook PSID"
    WEBSITE_EXTERNAL = "website_external", "Website external ID"
    EXTERNAL_ID = "external_id", "External ID"


class CustomerStatus(models.TextChoices):
    LEAD = "lead", "Lead"
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class ConversationStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"
    ARCHIVED = "archived", "Archived"


class MessageDirection(models.TextChoices):
    INBOUND = "inbound", "Inbound"
    OUTBOUND = "outbound", "Outbound"


class SenderType(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    STAFF = "staff", "Staff"
    BOT = "bot", "AI Bot"
    SYSTEM = "system", "System"


class MessageStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    READ = "read", "Read"
    FAILED = "failed", "Failed"
    RECEIVED = "received", "Received"


class Customer(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=CustomerStatus.choices,
        default=CustomerStatus.LEAD,
    )
    notes = models.TextField(blank=True, default="")
    property = models.ForeignKey(
        "accounts.Property",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="interested_customers",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_customers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        return self.name


class CustomerChannelIdentity(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="identities",
    )
    channel = models.CharField(max_length=16, choices=Channel.choices)
    identifier = models.CharField(max_length=255)
    identifier_type = models.CharField(max_length=32, choices=IdentifierType.choices)
    display_name = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "customer channel identity"
        verbose_name_plural = "customer channel identities"
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "identifier_type", "identifier"],
                name="uniq_customer_channel_identity",
            )
        ]
        indexes = [
            models.Index(fields=["identifier"]),
            models.Index(fields=["channel", "identifier"]),
        ]

    def __str__(self) -> str:
        return f"{self.channel}:{self.identifier_type}:{self.identifier}"


class Conversation(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    property = models.ForeignKey(
        "accounts.Property",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
    )
    channel = models.CharField(max_length=16, choices=Channel.choices)
    external_conversation_id = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=ConversationStatus.choices,
        default=ConversationStatus.OPEN,
    )
    subject = models.CharField(max_length=255, blank=True, default="")
    last_message_preview = models.CharField(max_length=500, blank=True, default="")
    last_message_at = models.DateTimeField(null=True, blank=True)
    unread_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at", "-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "external_conversation_id"],
                condition=~models.Q(external_conversation_id=""),
                name="uniq_conversation_external_id_per_channel",
            )
        ]
        indexes = [
            models.Index(fields=["channel"]),
            models.Index(fields=["status"]),
            models.Index(fields=["last_message_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.channel} conversation #{self.pk}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    channel = models.CharField(max_length=16, choices=Channel.choices)
    direction = models.CharField(max_length=16, choices=MessageDirection.choices)
    sender_type = models.CharField(max_length=16, choices=SenderType.choices)
    sender_name = models.CharField(max_length=255, blank=True, default="")
    sender_identifier = models.CharField(max_length=255, blank=True, default="")
    recipient_identifier = models.CharField(max_length=255, blank=True, default="")
    content = models.TextField(blank=True, default="")
    attachments = models.JSONField(default=list, blank=True)
    external_message_id = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=MessageStatus.choices,
        default=MessageStatus.RECEIVED,
    )
    error_message = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_messages",
    )
    received_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    raw_event = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "external_message_id"],
                condition=~models.Q(external_message_id=""),
                name="uniq_message_external_id_per_channel",
            )
        ]
        indexes = [
            models.Index(fields=["channel", "external_message_id"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["direction"]),
        ]

    def __str__(self) -> str:
        return f"{self.channel} {self.direction} #{self.pk}"
