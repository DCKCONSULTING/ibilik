from django.contrib import admin

from crm.models import Conversation, Customer, CustomerChannelIdentity, Message


class CustomerChannelIdentityInline(admin.TabularInline):
    model = CustomerChannelIdentity
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("name", "phone", "email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [CustomerChannelIdentityInline]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "channel", "property", "status", "unread_count", "last_message_at")
    list_filter = ("channel", "status")
    search_fields = ("customer__name", "customer__phone", "customer__email", "external_conversation_id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "channel", "direction", "sender_type", "status", "created_at")
    list_filter = ("channel", "direction", "sender_type", "status")
    search_fields = ("content", "external_message_id", "sender_name")
    readonly_fields = ("created_at", "updated_at", "raw_event")
