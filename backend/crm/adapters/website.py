from __future__ import annotations

from crm.adapters.base import ChannelAdapter, SendResult
from crm.models import Channel, Customer


class WebsiteAdapter(ChannelAdapter):
    channel = Channel.WEBSITE
    can_receive_inbound = True
    can_send_outbound = False

    def is_configured(self) -> bool:
        return True

    def can_send_to(self, customer: Customer) -> bool:
        return False

    def send(self, *, customer: Customer, recipient: str, content: str, conversation_id: int | None = None) -> SendResult:
        return SendResult(
            status="failed",
            error_message="Website forms cannot receive outbound replies.",
            provider="website",
        )
