from crm.adapters.base import ChannelAdapter, SendResult, get_adapter
from crm.adapters.facebook import FacebookAdapter
from crm.adapters.website import WebsiteAdapter
from crm.adapters.whatsapp import WhatsAppAdapter

__all__ = [
    "ChannelAdapter",
    "FacebookAdapter",
    "SendResult",
    "WebsiteAdapter",
    "WhatsAppAdapter",
    "get_adapter",
]
