from __future__ import annotations

from datetime import datetime, timezone

from django.db import transaction
from django.db.models import Max, Q
from django.utils.dateparse import parse_datetime

from accounts.models import Property
from crm.adapters.base import get_adapter
from crm.matching import match_or_create_customer, normalize_email, normalize_identifier, normalize_phone
from crm.models import (
    Channel,
    Conversation,
    ConversationStatus,
    Customer,
    CustomerStatus,
    IdentifierType,
    Message,
    MessageDirection,
    MessageStatus,
    SenderType,
)
from crm.sanitization import sanitize_payload


class IngestError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_payload"):
        super().__init__(message)
        self.code = code


def parse_timestamp(value) -> datetime:
    if value in (None, ""):
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if isinstance(value, str):
        if value.isdigit():
            return parse_timestamp(int(value))
        parsed = parse_datetime(value)
        if parsed is None:
            raise IngestError("Invalid timestamp.", code="invalid_timestamp")
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    raise IngestError("Invalid timestamp.", code="invalid_timestamp")


def preview_text(content: str) -> str:
    text = " ".join((content or "").split())
    return text[:500]


def available_reply_channels(customer: Customer) -> list[str]:
    channels = []
    for channel in (Channel.WHATSAPP, Channel.FACEBOOK):
        adapter = get_adapter(channel)
        if adapter.can_send_to(customer):
            channels.append(channel)
    return channels


def resolve_property(property_id) -> Property | None:
    if property_id in (None, ""):
        return None
    try:
        property_pk = int(property_id)
    except (TypeError, ValueError) as exc:
        raise IngestError("property_id must be an integer.", code="invalid_property") from exc
    property_obj = Property.objects.filter(pk=property_pk).first()
    if property_obj is None:
        raise IngestError("Unknown property.", code="unknown_property")
    return property_obj


def get_existing_message(channel: str, external_message_id: str) -> Message | None:
    if not external_message_id:
        return None
    return (
        Message.objects.select_related("conversation", "conversation__customer", "conversation__property")
        .filter(channel=channel, external_message_id=external_message_id)
        .first()
    )


def _resolve_conversation(
    *,
    customer: Customer,
    channel: str,
    property_obj: Property | None,
    external_conversation_id: str,
    subject: str,
) -> Conversation:
    if external_conversation_id:
        existing = Conversation.objects.filter(
            channel=channel,
            external_conversation_id=external_conversation_id,
        ).first()
        if existing:
            if existing.customer_id != customer.pk:
                raise IngestError("Conversation already belongs to another customer.", code="conversation_conflict")
            if property_obj and existing.property_id is None:
                existing.property = property_obj
                existing.save(update_fields=["property", "updated_at"])
            return existing

    query = Conversation.objects.filter(
        customer=customer,
        channel=channel,
        status=ConversationStatus.OPEN,
    )
    if property_obj is not None:
        query = query.filter(property=property_obj)
    else:
        query = query.filter(property__isnull=True)
    existing = query.order_by("-last_message_at", "-id").first()
    if existing:
        if external_conversation_id and not existing.external_conversation_id:
            existing.external_conversation_id = external_conversation_id
            existing.save(update_fields=["external_conversation_id", "updated_at"])
        return existing

    return Conversation.objects.create(
        customer=customer,
        property=property_obj,
        channel=channel,
        external_conversation_id=external_conversation_id,
        subject=subject,
        status=ConversationStatus.OPEN,
    )


@transaction.atomic
def ingest_inbound_message(
    *,
    channel: str,
    content: str,
    name: str = "",
    email: str = "",
    phone: str = "",
    sender_identifier: str = "",
    recipient_identifier: str = "",
    sender_type: str = SenderType.CUSTOMER,
    sender_name: str = "",
    external_message_id: str = "",
    external_conversation_id: str = "",
    timestamp=None,
    attachments: list | None = None,
    property_id=None,
    raw_event=None,
    identities: list[dict] | None = None,
    source_reference: str = "",
) -> tuple[Message, bool]:
    if channel not in Channel.values:
        raise IngestError("Unknown channel.", code="invalid_channel")
    if sender_type not in SenderType.values:
        sender_type = SenderType.CUSTOMER

    existing = get_existing_message(channel, external_message_id)
    if existing:
        return existing, True

    content = (content or "").strip()
    attachments = attachments or []
    if not content and not attachments:
        raise IngestError("Message content is required.", code="invalid_message")

    occurred_at = parse_timestamp(timestamp)
    property_obj = resolve_property(property_id)
    email = normalize_email(email)
    phone = normalize_phone(phone)
    name = (name or sender_name or "").strip()
    identities = list(identities or [])

    customer = match_or_create_customer(
        name=name,
        email=email,
        phone=phone,
        identities=identities,
    )
    if customer.status == CustomerStatus.LEAD:
        customer.status = CustomerStatus.ACTIVE
        customer.save(update_fields=["status", "updated_at"])

    subject = preview_text(content) or f"{channel} conversation"
    conversation = _resolve_conversation(
        customer=customer,
        channel=channel,
        property_obj=property_obj,
        external_conversation_id=normalize_identifier(external_conversation_id),
        subject=subject,
    )

    message = Message.objects.create(
        conversation=conversation,
        channel=channel,
        direction=MessageDirection.INBOUND,
        sender_type=sender_type,
        sender_name=sender_name or name or customer.name,
        sender_identifier=sender_identifier or phone or email,
        recipient_identifier=recipient_identifier,
        content=content,
        attachments=attachments,
        external_message_id=external_message_id,
        status=MessageStatus.RECEIVED,
        received_at=occurred_at,
        raw_event=sanitize_payload(raw_event) if raw_event is not None else None,
    )

    conversation.last_message_preview = preview_text(content) or "Attachment"
    conversation.last_message_at = occurred_at
    conversation.unread_count = conversation.unread_count + 1
    if source_reference and not conversation.subject:
        conversation.subject = source_reference
    conversation.save(update_fields=["last_message_preview", "last_message_at", "unread_count", "subject", "updated_at"])
    from cases.services import attach_inbound_message_to_case

    attach_inbound_message_to_case(message)
    return message, False


@transaction.atomic
def send_outbound_message(
    *,
    conversation: Conversation,
    actor,
    content: str,
    channel: str,
) -> Message:
    content = (content or "").strip()
    if not content:
        raise IngestError("Message content is required.", code="invalid_message")
    if channel not in Channel.values:
        raise IngestError("Unknown channel.", code="invalid_channel")

    customer = conversation.customer
    adapter = get_adapter(channel)
    if not adapter.can_send_outbound:
        raise IngestError("This channel cannot receive outbound replies.", code="channel_unavailable")
    if not adapter.can_send_to(customer):
        raise IngestError("This customer cannot be reached on the selected channel.", code="channel_unavailable")

    recipient = adapter.recipient_for(customer) if hasattr(adapter, "recipient_for") else ""
    result = adapter.send(
        customer=customer,
        recipient=recipient,
        content=content,
        conversation_id=conversation.pk,
    )
    now = datetime.now(timezone.utc)
    message = Message.objects.create(
        conversation=conversation,
        channel=channel,
        direction=MessageDirection.OUTBOUND,
        sender_type=SenderType.STAFF,
        sender_name=getattr(actor, "get_full_name", lambda: "")() or getattr(actor, "username", "Staff"),
        sender_identifier=getattr(actor, "username", ""),
        recipient_identifier=recipient,
        content=content,
        status=result.status if result.status in MessageStatus.values else MessageStatus.FAILED,
        error_message=result.error_message,
        external_message_id=result.external_message_id,
        created_by=actor,
        sent_at=now if result.status != MessageStatus.FAILED else None,
    )
    conversation.last_message_preview = preview_text(content)
    conversation.last_message_at = now
    conversation.save(update_fields=["last_message_preview", "last_message_at", "updated_at"])
    return message


def mark_conversation_read(conversation: Conversation) -> Conversation:
    if conversation.unread_count:
        conversation.unread_count = 0
        conversation.save(update_fields=["unread_count", "updated_at"])
    return conversation


def create_customer(
    *,
    actor,
    name: str,
    email: str = "",
    phone: str = "",
    status: str = CustomerStatus.LEAD,
    notes: str = "",
    property_id=None,
) -> Customer:
    name = (name or "").strip()
    if not name:
        raise IngestError("Name is required.", code="invalid_name")
    email = normalize_email(email)
    phone = normalize_phone(phone)
    if status not in CustomerStatus.values:
        raise IngestError("Unknown customer status.", code="invalid_status")
    if email and Customer.objects.filter(email=email).exists():
        raise IngestError("A customer with that email already exists.", code="email_taken")
    if phone and Customer.objects.filter(phone=phone).exists():
        raise IngestError("A customer with that phone already exists.", code="phone_taken")

    identities = []
    if email:
        identities.append(
            {
                "channel": Channel.WEBSITE,
                "identifier": email,
                "identifier_type": IdentifierType.EMAIL,
                "display_name": name,
            }
        )
    if phone:
        identities.append(
            {
                "channel": Channel.WEBSITE,
                "identifier": phone,
                "identifier_type": IdentifierType.PHONE,
                "display_name": name,
            }
        )
    customer = match_or_create_customer(
        name=name,
        email=email,
        phone=phone,
        identities=identities,
        created_by=actor,
    )
    customer.notes = notes or ""
    customer.status = status
    customer.created_by = actor
    customer.property = resolve_property(property_id)
    customer.save(update_fields=["notes", "status", "created_by", "property", "updated_at"])
    return customer


def update_customer(customer: Customer, payload: dict) -> Customer:
    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise IngestError("Name is required.", code="invalid_name")
        customer.name = name
    if "email" in payload:
        email = normalize_email(payload.get("email"))
        if email and Customer.objects.exclude(pk=customer.pk).filter(email=email).exists():
            raise IngestError("A customer with that email already exists.", code="email_taken")
        customer.email = email
    if "phone" in payload:
        phone = normalize_phone(payload.get("phone"))
        if phone and Customer.objects.exclude(pk=customer.pk).filter(phone=phone).exists():
            raise IngestError("A customer with that phone already exists.", code="phone_taken")
        customer.phone = phone
    if "status" in payload:
        status = payload.get("status")
        if status not in CustomerStatus.values:
            raise IngestError("Unknown customer status.", code="invalid_status")
        customer.status = status
    if "notes" in payload:
        customer.notes = str(payload.get("notes") or "")
    customer.save()
    return customer


def filter_conversations(queryset, params):
    channel = params.get("channel")
    if channel:
        if channel not in Channel.values:
            raise IngestError("Unknown channel.", code="invalid_channel")
        queryset = queryset.filter(channel=channel)

    customer_id = params.get("customer")
    if customer_id:
        try:
            queryset = queryset.filter(customer_id=int(customer_id))
        except (TypeError, ValueError) as exc:
            raise IngestError("customer must be an integer.", code="invalid_customer") from exc

    property_id = params.get("property")
    if property_id:
        try:
            queryset = queryset.filter(property_id=int(property_id))
        except (TypeError, ValueError) as exc:
            raise IngestError("property must be an integer.", code="invalid_property") from exc

    status = params.get("status")
    if status:
        if status not in ConversationStatus.values:
            raise IngestError("Unknown conversation status.", code="invalid_status")
        queryset = queryset.filter(status=status)

    unread = params.get("unread")
    if unread in {"1", "true", "True"}:
        queryset = queryset.filter(unread_count__gt=0)

    search = (params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(customer__name__icontains=search)
            | Q(customer__email__icontains=search)
            | Q(customer__phone__icontains=search)
            | Q(last_message_preview__icontains=search)
            | Q(subject__icontains=search)
        )
    return queryset


def filter_customers(queryset, params):
    search = (params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search)
        )
    status = params.get("status")
    if status:
        if status not in CustomerStatus.values:
            raise IngestError("Unknown customer status.", code="invalid_status")
        queryset = queryset.filter(status=status)
    source = params.get("source") or params.get("channel")
    if source:
        if source not in Channel.values:
            raise IngestError("Unknown channel.", code="invalid_channel")
        queryset = queryset.filter(Q(identities__channel=source) | Q(conversations__channel=source)).distinct()
    property_id = params.get("property")
    if property_id:
        try:
            queryset = queryset.filter(conversations__property_id=int(property_id)).distinct()
        except (TypeError, ValueError) as exc:
            raise IngestError("property must be an integer.", code="invalid_property") from exc
    return queryset


def customer_last_contact(customer: Customer):
    return customer.conversations.aggregate(last=Max("last_message_at"))["last"]
