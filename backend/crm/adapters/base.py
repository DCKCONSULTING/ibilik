from __future__ import annotations

from dataclasses import dataclass

from crm.models import Channel, Customer


@dataclass
class SendResult:
    status: str
    external_message_id: str = ""
    error_message: str = ""
    provider: str = ""


class ChannelAdapter:
    channel = ""
    can_receive_inbound = True
    can_send_outbound = False

    def is_configured(self) -> bool:
        return False

    def can_send_to(self, customer: Customer) -> bool:
        return False

    def send(self, *, customer: Customer, recipient: str, content: str, conversation_id: int | None = None) -> SendResult:
        return SendResult(status="failed", error_message="This channel cannot send outbound messages.")


def get_adapter(channel: str) -> ChannelAdapter:
    from crm.adapters.facebook import FacebookAdapter
    from crm.adapters.website import WebsiteAdapter
    from crm.adapters.whatsapp import WhatsAppAdapter

    adapters = {
        Channel.WEBSITE: WebsiteAdapter,
        Channel.WHATSAPP: WhatsAppAdapter,
        Channel.FACEBOOK: FacebookAdapter,
    }
    adapter_cls = adapters.get(channel)
    if adapter_cls is None:
        raise ValueError("Unknown channel.")
    return adapter_cls()
