from __future__ import annotations

import json
import urllib.error
import urllib.request

from django.conf import settings

from crm.adapters.base import ChannelAdapter, SendResult
from crm.models import Channel, Customer, CustomerChannelIdentity, IdentifierType


class FacebookAdapter(ChannelAdapter):
    channel = Channel.FACEBOOK
    can_receive_inbound = True
    can_send_outbound = True

    def is_configured(self) -> bool:
        provider = getattr(settings, "FACEBOOK_PROVIDER", "meta")
        if provider == "test":
            return True
        return bool(settings.FACEBOOK_ACCESS_TOKEN)

    def _facebook_identity(self, customer: Customer) -> CustomerChannelIdentity | None:
        return customer.identities.filter(
            channel=Channel.FACEBOOK,
            identifier_type=IdentifierType.FACEBOOK_PSID,
        ).first()

    def recipient_for(self, customer: Customer) -> str:
        identity = self._facebook_identity(customer)
        return identity.identifier if identity else ""

    def can_send_to(self, customer: Customer) -> bool:
        if not self.is_configured():
            return False
        return self._facebook_identity(customer) is not None

    def send(self, *, customer: Customer, recipient: str, content: str, conversation_id: int | None = None) -> SendResult:
        to = recipient or self.recipient_for(customer)
        if not to:
            return SendResult(status="failed", error_message="No Facebook Messenger recipient is available.", provider="facebook")
        if not self.is_configured():
            return SendResult(
                status="failed",
                error_message="Facebook Messenger delivery is not configured.",
                provider="facebook",
            )

        provider = getattr(settings, "FACEBOOK_PROVIDER", "meta")
        if provider == "test":
            return SendResult(
                status="sent",
                external_message_id=f"test-fb-{conversation_id or 'out'}-{to}",
                provider="test",
            )

        token = settings.FACEBOOK_ACCESS_TOKEN
        url = f"https://graph.facebook.com/v21.0/me/messages?access_token={token}"
        payload = {
            "recipient": {"id": to},
            "messaging_type": "RESPONSE",
            "message": {"text": content},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError:
            return SendResult(status="failed", error_message="Unable to send the Facebook message.", provider="meta")
        except urllib.error.URLError:
            return SendResult(status="failed", error_message="Unable to reach the Facebook provider.", provider="meta")

        return SendResult(status="sent", external_message_id=str(body.get("message_id") or ""), provider="meta")
