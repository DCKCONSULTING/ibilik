from __future__ import annotations

from django.db.models import Q, QuerySet

from accounts.authorization import (
    assigned_property_ids,
    has_global_property_access,
    is_superuser,
    user_has_permission,
)
from match.models import MatchRequest
from match.permissions import VIEW_ALL, VIEW_ASSIGNED, VIEW_MATCH


def can_view_all_requests(user) -> bool:
    if is_superuser(user):
        return True
    return user_has_permission(user, VIEW_ALL)


def can_view_assigned_requests(user) -> bool:
    if is_superuser(user):
        return True
    return user_has_permission(user, VIEW_ASSIGNED) or user_has_permission(user, VIEW_MATCH)


def accessible_requests(user, queryset: QuerySet | None = None) -> QuerySet:
    qs = queryset if queryset is not None else MatchRequest.objects.all()
    if not getattr(user, "is_authenticated", False):
        return qs.none()
    if is_superuser(user):
        return qs
    if not user_has_permission(user, VIEW_MATCH):
        return qs.none()

    if can_view_all_requests(user):
        if has_global_property_access(user):
            return qs
        property_ids = assigned_property_ids(user)
        return qs.filter(Q(property_id__in=property_ids) | Q(assigned_to=user))

    if can_view_assigned_requests(user):
        return qs.filter(assigned_to=user)

    return qs.none()


def can_access_request(user, request: MatchRequest | None) -> bool:
    if request is None or not getattr(user, "is_authenticated", False):
        return False
    if is_superuser(user):
        return True
    if not user_has_permission(user, VIEW_MATCH):
        return False
    if can_view_all_requests(user):
        if has_global_property_access(user):
            return True
        if request.assigned_to_id == user.pk:
            return True
        if request.property_id is None:
            return False
        return request.property_id in assigned_property_ids(user)
    if can_view_assigned_requests(user):
        return request.assigned_to_id == user.pk
    return False
