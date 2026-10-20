from __future__ import annotations

from django.db.models import Q, QuerySet

from accounts.authorization import assigned_property_ids, has_global_property_access, is_superuser
from crm.models import Conversation, Customer, Message


def accessible_conversations(user, queryset: QuerySet | None = None) -> QuerySet:
    qs = queryset if queryset is not None else Conversation.objects.all()
    if not getattr(user, "is_authenticated", False):
        return qs.none()
    if is_superuser(user) or has_global_property_access(user):
        return qs
    property_ids = assigned_property_ids(user)
    return qs.filter(property_id__in=property_ids)


def can_access_conversation(user, conversation: Conversation | None) -> bool:
    if conversation is None or not getattr(user, "is_authenticated", False):
        return False
    if is_superuser(user) or has_global_property_access(user):
        return True
    if conversation.property_id is None:
        return False
    return conversation.property_id in assigned_property_ids(user)


def accessible_customers(user, queryset: QuerySet | None = None) -> QuerySet:
    qs = queryset if queryset is not None else Customer.objects.all()
    if not getattr(user, "is_authenticated", False):
        return qs.none()
    if is_superuser(user) or has_global_property_access(user):
        return qs
    property_ids = assigned_property_ids(user)
    return qs.filter(
        Q(conversations__property_id__in=property_ids)
        | Q(property_id__in=property_ids)
        | Q(created_by=user, conversations__isnull=True)
    ).distinct()


def can_access_customer(user, customer: Customer | None) -> bool:
    if customer is None or not getattr(user, "is_authenticated", False):
        return False
    if is_superuser(user) or has_global_property_access(user):
        return True
    if customer.created_by_id == user.pk and not customer.conversations.exists():
        return True
    property_ids = assigned_property_ids(user)
    if customer.property_id in property_ids:
        return True
    return customer.conversations.filter(property_id__in=property_ids).exists()


def accessible_messages(user, queryset: QuerySet | None = None) -> QuerySet:
    qs = queryset if queryset is not None else Message.objects.all()
    conversation_ids = accessible_conversations(user).values_list("id", flat=True)
    return qs.filter(conversation_id__in=conversation_ids)
