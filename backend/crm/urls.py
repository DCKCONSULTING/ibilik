from django.urls import path

from crm import integrations, views

urlpatterns = [
    path("customers/", views.customer_collection_view, name="customer-collection"),
    path("customers/<int:customer_id>/", views.customer_detail_view, name="customer-detail"),
    path("conversations/", views.conversation_collection_view, name="conversation-collection"),
    path("conversations/<int:conversation_id>/", views.conversation_detail_view, name="conversation-detail"),
    path("conversations/<int:conversation_id>/messages/", views.conversation_messages_view, name="conversation-messages"),
    path("conversations/<int:conversation_id>/read/", views.conversation_read_view, name="conversation-read"),
    path("inbox/", views.conversation_collection_view, name="inbox"),
    path("integrations/website/messages/", integrations.website_messages_view, name="website-messages"),
    path("integrations/whatsapp/webhook/", integrations.whatsapp_webhook_view, name="whatsapp-webhook"),
    path("integrations/whatsapp/messages/", integrations.whatsapp_messages_view, name="whatsapp-messages"),
    path("integrations/facebook/webhook/", integrations.facebook_webhook_view, name="facebook-webhook"),
    path("integrations/facebook/messages/", integrations.facebook_messages_view, name="facebook-messages"),
]
