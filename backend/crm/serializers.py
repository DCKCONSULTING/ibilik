from __future__ import annotations

from crm.models import Customer, Message
from crm.services import available_reply_channels, customer_last_contact


def isoformat(value):
    return value.isoformat() if value else None


def serialize_identity(identity) -> dict:
    return {
        "id": identity.pk,
        "channel": identity.channel,
        "identifier": identity.identifier,
        "identifier_type": identity.identifier_type,
        "display_name": identity.display_name,
    }


def serialize_property_summary(property_obj) -> dict | None:
    if property_obj is None:
        return None
    return {
        "id": property_obj.pk,
        "name": property_obj.name,
    }


def serialize_customer_summary(customer: Customer) -> dict:
    channels = sorted(set(customer.identities.values_list("channel", flat=True)) | set(
        customer.conversations.values_list("channel", flat=True)
    ))
    properties = []
    seen = set()
    if customer.property_id:
        seen.add(customer.property_id)
        properties.append(serialize_property_summary(customer.property))
    for item in customer.conversations.select_related("property").all():
        if item.property_id and item.property_id not in seen:
            seen.add(item.property_id)
            properties.append(serialize_property_summary(item.property))
    return {
        "id": customer.pk,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "status": customer.status,
        "sources": channels,
        "properties": properties,
        "last_contact_at": isoformat(customer_last_contact(customer)),
        "reply_channels": available_reply_channels(customer),
    }


def serialize_customer(customer: Customer, *, include_timeline: bool = False) -> dict:
    payload = serialize_customer_summary(customer)
    payload.update(
        {
            "notes": customer.notes,
            "identities": [serialize_identity(item) for item in customer.identities.order_by("channel", "id")],
            "created_at": isoformat(customer.created_at),
            "updated_at": isoformat(customer.updated_at),
            "created_by_id": customer.created_by_id,
        }
    )
    if include_timeline:
        messages = (
            Message.objects.filter(conversation__customer=customer)
            .select_related("conversation", "created_by")
            .order_by("-created_at", "-id")[:50]
        )
        payload["timeline"] = [serialize_message(item) for item in reversed(list(messages))]
        payload["conversations"] = [
            serialize_conversation(item, include_customer=False)
            for item in customer.conversations.select_related("property", "customer").order_by("-last_message_at", "-id")
        ]
        from cases.serializers import serialize_case_summary

        payload["cases"] = [
            serialize_case_summary(item)
            for item in customer.cases.select_related("property", "assigned_to").order_by("-updated_at", "-id")
        ]
    return payload


def serialize_message(message: Message) -> dict:
    return {
        "id": message.pk,
        "conversation_id": message.conversation_id,
        "channel": message.channel,
        "direction": message.direction,
        "sender_type": message.sender_type,
        "sender_name": message.sender_name,
        "sender_identifier": message.sender_identifier,
        "recipient_identifier": message.recipient_identifier,
        "content": message.content,
        "attachments": message.attachments or [],
        "external_message_id": message.external_message_id,
        "status": message.status,
        "error_message": message.error_message,
        "created_by_id": message.created_by_id,
        "received_at": isoformat(message.received_at),
        "sent_at": isoformat(message.sent_at),
        "created_at": isoformat(message.created_at),
        "updated_at": isoformat(message.updated_at),
    }


def serialize_conversation(conversation, *, include_customer: bool = True) -> dict:
    payload = {
        "id": conversation.pk,
        "channel": conversation.channel,
        "external_conversation_id": conversation.external_conversation_id,
        "status": conversation.status,
        "subject": conversation.subject,
        "last_message_preview": conversation.last_message_preview,
        "last_message_at": isoformat(conversation.last_message_at),
        "last_message": {
            "content": conversation.last_message_preview,
            "created_at": isoformat(conversation.last_message_at),
        },
        "unread_count": conversation.unread_count,
        "is_unread": conversation.unread_count > 0,
        "property": serialize_property_summary(conversation.property),
        "reply_channels": available_reply_channels(conversation.customer),
        "created_at": isoformat(conversation.created_at),
        "updated_at": isoformat(conversation.updated_at),
    }
    if include_customer:
        payload["customer"] = serialize_customer_summary(conversation.customer)
    else:
        payload["customer_id"] = conversation.customer_id
    return payload


def serialize_ingest_result(message: Message, *, deduplicated: bool) -> dict:
    conversation = message.conversation
    return {
        "deduplicated": deduplicated,
        "customer": serialize_customer_summary(conversation.customer),
        "conversation": serialize_conversation(conversation),
        "message": serialize_message(message),
    }
