from __future__ import annotations

import json
import urllib.error
import urllib.request

from django.conf import settings

from crm.adapters.base import ChannelAdapter, SendResult
from crm.matching import normalize_phone
from crm.models import Channel, Customer, CustomerChannelIdentity, IdentifierType


class WhatsAppAdapter(ChannelAdapter):
    channel = Channel.WHATSAPP
    can_receive_inbound = True
    can_send_outbound = True

    def is_configured(self) -> bool:
        provider = getattr(settings, "WHATSAPP_PROVIDER", "meta")
        if provider == "test":
            return True
        return bool(settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)

    def _whatsapp_identity(self, customer: Customer) -> CustomerChannelIdentity | None:
        return customer.identities.filter(
            channel=Channel.WHATSAPP,
            identifier_type=IdentifierType.PHONE,
        ).first()

    def recipient_for(self, customer: Customer) -> str:
        identity = self._whatsapp_identity(customer)
        if identity:
            return identity.identifier
        return normalize_phone(customer.phone)

    def can_send_to(self, customer: Customer) -> bool:
        if not self.is_configured():
            return False
        if self._whatsapp_identity(customer) is not None:
            return True
        return bool(normalize_phone(customer.phone))

    def send(self, *, customer: Customer, recipient: str, content: str, conversation_id: int | None = None) -> SendResult:
        to = normalize_phone(recipient) or self.recipient_for(customer)
        if not to:
            return SendResult(status="failed", error_message="No WhatsApp recipient is available.", provider="whatsapp")
        if not self.is_configured():
            return SendResult(
                status="failed",
                error_message="WhatsApp delivery is not configured.",
                provider="whatsapp",
            )

        provider = getattr(settings, "WHATSAPP_PROVIDER", "meta")
        if provider == "test":
            return SendResult(
                status="sent",
                external_message_id=f"test-wa-{conversation_id or 'out'}-{to}",
                provider="test",
            )

        phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        token = settings.WHATSAPP_ACCESS_TOKEN
        url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to.lstrip("+"),
            "type": "text",
            "text": {"body": content},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            return SendResult(status="failed", error_message="Unable to send the WhatsApp message.", provider="meta")
        except urllib.error.URLError:
            return SendResult(status="failed", error_message="Unable to reach the WhatsApp provider.", provider="meta")

        messages = body.get("messages") or []
        external_id = ""
        if messages and isinstance(messages[0], dict):
            external_id = str(messages[0].get("id") or "")
        return SendResult(status="sent", external_message_id=external_id, provider="meta")
