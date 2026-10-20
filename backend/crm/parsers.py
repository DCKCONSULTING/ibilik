from __future__ import annotations

from crm.matching import normalize_email, normalize_phone
from crm.models import Channel, IdentifierType, SenderType


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def parse_attachments(value) -> list[dict]:
    if not value:
        return []
    if not isinstance(value, list):
        return []
    attachments = []
    for item in value:
        if not isinstance(item, dict):
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        attachments.append(
            {
                "type": str(item.get("type") or item.get("mime_type") or ""),
                "url": str(item.get("url") or payload.get("url") or ""),
                "mime_type": str(item.get("mime_type") or ""),
                "filename": str(item.get("filename") or item.get("name") or ""),
                "size": item.get("size"),
            }
        )
    return attachments


def parse_website_payload(payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    email = normalize_email(payload.get("email"))
    phone = normalize_phone(payload.get("phone"))
    content = str(payload.get("message") or payload.get("content") or "").strip()
    if not name:
        raise ValueError("Name is required.")
    if not content:
        raise ValueError("Message is required.")
    if not email and not phone:
        raise ValueError("A phone number or email address is required.")

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
    external_id = str(payload.get("external_id") or payload.get("external_message_id") or "")
    return {
        "channel": Channel.WEBSITE,
        "name": name,
        "email": email,
        "phone": phone,
        "content": content,
        "sender_identifier": email or phone,
        "external_message_id": external_id,
        "external_conversation_id": str(payload.get("external_conversation_id") or ""),
        "timestamp": payload.get("timestamp"),
        "property_id": payload.get("property_id"),
        "source_reference": str(payload.get("source_reference") or payload.get("source") or "website-form"),
        "identities": identities,
        "attachments": parse_attachments(payload.get("attachments")),
        "raw_event": payload,
    }


def parse_normalized_whatsapp(payload: dict) -> list[dict]:
    if payload.get("entry"):
        return parse_meta_whatsapp(payload)

    content = str(payload.get("content") or payload.get("message") or payload.get("text") or "").strip()
    sender = str(payload.get("from") or payload.get("sender") or payload.get("phone") or "")
    phone = normalize_phone(sender or payload.get("phone"))
    sender_type = str(payload.get("sender_type") or SenderType.CUSTOMER)
    if sender_type not in SenderType.values:
        sender_type = SenderType.CUSTOMER
    name = str(payload.get("name") or payload.get("profile_name") or "").strip()
    identities = []
    if phone:
        identities.append(
            {
                "channel": Channel.WHATSAPP,
                "identifier": phone,
                "identifier_type": IdentifierType.PHONE,
                "display_name": name,
            }
        )
    email = normalize_email(payload.get("email"))
    return [
        {
            "channel": Channel.WHATSAPP,
            "name": name,
            "email": email,
            "phone": phone,
            "content": content,
            "sender_identifier": phone,
            "recipient_identifier": str(payload.get("to") or payload.get("recipient") or ""),
            "sender_type": sender_type,
            "sender_name": name,
            "external_message_id": str(payload.get("external_message_id") or payload.get("id") or ""),
            "external_conversation_id": str(payload.get("external_conversation_id") or ""),
            "timestamp": payload.get("timestamp"),
            "property_id": payload.get("property_id"),
            "attachments": parse_attachments(payload.get("attachments")),
            "identities": identities,
            "raw_event": payload,
        }
    ]


def parse_meta_whatsapp(payload: dict) -> list[dict]:
    events = []
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            value = _as_dict(change.get("value") if isinstance(change, dict) else {})
            contacts = {
                str(item.get("wa_id") or ""): str(_as_dict(item.get("profile")).get("name") or "")
                for item in value.get("contacts") or []
                if isinstance(item, dict)
            }
            for message in value.get("messages") or []:
                if not isinstance(message, dict):
                    continue
                sender = str(message.get("from") or "")
                phone = normalize_phone(sender)
                name = contacts.get(sender) or contacts.get(phone.lstrip("+")) or ""
                text = ""
                if isinstance(message.get("text"), dict):
                    text = str(message["text"].get("body") or "")
                elif message.get("type") == "button" and isinstance(message.get("button"), dict):
                    text = str(message["button"].get("text") or "")
                attachments = []
                for media_key in ("image", "video", "audio", "document", "sticker"):
                    media = message.get(media_key)
                    if isinstance(media, dict):
                        attachments.append(
                            {
                                "type": media_key,
                                "url": str(media.get("link") or ""),
                                "mime_type": str(media.get("mime_type") or ""),
                                "filename": str(media.get("filename") or ""),
                                "id": str(media.get("id") or ""),
                            }
                        )
                sender_type = SenderType.CUSTOMER
                if str(message.get("sender_type") or "").lower() in {SenderType.BOT, "ai", "ai_bot"}:
                    sender_type = SenderType.BOT
                events.append(
                    {
                        "channel": Channel.WHATSAPP,
                        "name": name,
                        "phone": phone,
                        "content": text,
                        "sender_identifier": phone,
                        "recipient_identifier": str(_as_dict(value.get("metadata")).get("display_phone_number") or ""),
                        "sender_type": sender_type,
                        "sender_name": name,
                        "external_message_id": str(message.get("id") or ""),
                        "external_conversation_id": str(value.get("conversation_id") or entry.get("id") or ""),
                        "timestamp": message.get("timestamp"),
                        "attachments": attachments,
                        "identities": [
                            {
                                "channel": Channel.WHATSAPP,
                                "identifier": phone,
                                "identifier_type": IdentifierType.PHONE,
                                "display_name": name,
                            }
                        ]
                        if phone
                        else [],
                        "raw_event": {"entry_id": entry.get("id"), "message": message},
                    }
                )
    return events


def parse_normalized_facebook(payload: dict) -> list[dict]:
    if payload.get("object") == "page" or payload.get("entry"):
        return parse_meta_facebook(payload)

    sender_id = str(payload.get("sender_id") or payload.get("sender") or payload.get("psid") or "")
    content = str(payload.get("content") or payload.get("message") or payload.get("text") or "").strip()
    name = str(payload.get("name") or "").strip()
    phone = normalize_phone(payload.get("phone"))
    email = normalize_email(payload.get("email"))
    identities = []
    if sender_id:
        identities.append(
            {
                "channel": Channel.FACEBOOK,
                "identifier": sender_id,
                "identifier_type": IdentifierType.FACEBOOK_PSID,
                "display_name": name,
            }
        )
    if phone:
        identities.append(
            {
                "channel": Channel.FACEBOOK,
                "identifier": phone,
                "identifier_type": IdentifierType.PHONE,
                "display_name": name,
            }
        )
    if email:
        identities.append(
            {
                "channel": Channel.FACEBOOK,
                "identifier": email,
                "identifier_type": IdentifierType.EMAIL,
                "display_name": name,
            }
        )
    sender_type = str(payload.get("sender_type") or SenderType.CUSTOMER)
    if sender_type not in SenderType.values:
        sender_type = SenderType.CUSTOMER
    return [
        {
            "channel": Channel.FACEBOOK,
            "name": name,
            "email": email,
            "phone": phone,
            "content": content,
            "sender_identifier": sender_id,
            "recipient_identifier": str(payload.get("recipient_id") or payload.get("recipient") or ""),
            "sender_type": sender_type,
            "sender_name": name,
            "external_message_id": str(payload.get("external_message_id") or payload.get("id") or payload.get("mid") or ""),
            "external_conversation_id": str(payload.get("external_conversation_id") or sender_id),
            "timestamp": payload.get("timestamp"),
            "property_id": payload.get("property_id"),
            "attachments": parse_attachments(payload.get("attachments")),
            "identities": identities,
            "raw_event": payload,
        }
    ]


def parse_meta_facebook(payload: dict) -> list[dict]:
    events = []
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for item in entry.get("messaging") or []:
            if not isinstance(item, dict) or "message" not in item:
                continue
            message = _as_dict(item.get("message"))
            if message.get("is_echo"):
                continue
            sender_id = str(_as_dict(item.get("sender")).get("id") or "")
            recipient_id = str(_as_dict(item.get("recipient")).get("id") or "")
            attachments = []
            for attachment in message.get("attachments") or []:
                if not isinstance(attachment, dict):
                    continue
                payload_data = _as_dict(attachment.get("payload"))
                attachments.append(
                    {
                        "type": str(attachment.get("type") or ""),
                        "url": str(payload_data.get("url") or ""),
                    }
                )
            events.append(
                {
                    "channel": Channel.FACEBOOK,
                    "name": "",
                    "content": str(message.get("text") or ""),
                    "sender_identifier": sender_id,
                    "recipient_identifier": recipient_id,
                    "sender_type": SenderType.CUSTOMER,
                    "external_message_id": str(message.get("mid") or ""),
                    "external_conversation_id": sender_id,
                    "timestamp": item.get("timestamp"),
                    "attachments": attachments,
                    "identities": [
                        {
                            "channel": Channel.FACEBOOK,
                            "identifier": sender_id,
                            "identifier_type": IdentifierType.FACEBOOK_PSID,
                        }
                    ]
                    if sender_id
                    else [],
                    "raw_event": {"entry_id": entry.get("id"), "messaging": item},
                }
            )
    return events
