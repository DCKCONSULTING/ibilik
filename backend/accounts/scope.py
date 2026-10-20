"""Reusable authority, property, and ownership scope for iBilik CRM.

This module does not invent a second role system. It reads the existing Role
catalog, Property.staff assignments, UserPropertyAccess, and
PropertyStaffAssignment.reports_to relationships.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Q, QuerySet

from accounts.authorization import (
    accessible_properties,
    assigned_property_ids,
    can_access_property,
    get_role,
    has_global_property_access,
    is_superuser,
    user_has_permission,
)
from accounts.roles import get_role_record, role_can_manage_lower_users, role_level


class ScopeError(Exception):
    def __init__(self, message: str, *, code: str = "property_forbidden", status: int = 403):
        super().__init__(message)
        self.code = code
        self.status = status


def get_user_authority_scope(user) -> dict:
    role = get_role(user)
    record = get_role_record(role)
    global_access = has_global_property_access(user)
    property_ids = [] if global_access else assigned_property_ids(user)
    return {
        "role": role,
        "level": role_level(role),
        "all_properties": global_access,
        "can_manage_lower_users": role_can_manage_lower_users(role),
        "can_view_team_workload": can_view_team_workload(user),
        "property_ids": property_ids,
        "subordinate_ids": sorted(get_subordinate_user_ids(user)),
    }


def get_visible_properties(user, queryset: QuerySet | None = None):
    return accessible_properties(user, queryset)


def get_user_property_scope(user):
    return get_visible_properties(user)


def can_view_team_workload(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if is_superuser(user):
        return True
    if role_can_manage_lower_users(get_role(user)):
        return True
    return user_has_permission(user, "users.view_user") or user_has_permission(user, "match.view_all_requests")


def _direct_report_ids(manager_id: int, property_ids: list[int] | None) -> set[int]:
    from accounts.models import PropertyStaffAssignment

    queryset = PropertyStaffAssignment.objects.filter(is_active=True, reports_to_id=manager_id)
    if property_ids:
        queryset = queryset.filter(property_id__in=property_ids)
    return set(queryset.values_list("user_id", flat=True))


def get_subordinate_user_ids(user) -> set[int]:
    if not getattr(user, "is_authenticated", False) or not getattr(user, "pk", None):
        return set()
    if is_superuser(user):
        return set(User.objects.exclude(pk=user.pk).values_list("pk", flat=True))

    actor_level = role_level(get_role(user))
    global_access = has_global_property_access(user)
    property_ids = None if global_access else assigned_property_ids(user)

    found: set[int] = set()
    frontier = {user.pk}
    seen = {user.pk}
    while frontier:
        current = frontier.pop()
        reports = _direct_report_ids(current, property_ids)
        new = reports - seen
        found.update(new)
        seen.update(new)
        frontier.update(new)

    candidates = User.objects.filter(is_active=True).exclude(pk=user.pk).exclude(is_superuser=True)
    if not global_access:
        if not property_ids:
            return found
        candidates = candidates.filter(assigned_properties__id__in=property_ids).distinct()

    for candidate in candidates.prefetch_related("groups"):
        if role_level(get_role(candidate)) > actor_level:
            found.add(candidate.pk)
    return found


def get_visible_user_ids(user) -> set[int] | None:
    """Return visible user IDs, or None when every user is visible."""

    if not getattr(user, "is_authenticated", False):
        return set()
    if is_superuser(user):
        return None
    visible = {user.pk} | get_subordinate_user_ids(user)
    return visible


def get_visible_users(user, queryset: QuerySet | None = None):
    qs = queryset if queryset is not None else User.objects.all()
    if not getattr(user, "is_authenticated", False):
        return qs.none()
    if is_superuser(user):
        return qs
    visible = get_visible_user_ids(user)
    if visible is None:
        return qs
    return qs.filter(pk__in=visible).distinct()


def owned_or_team_q(user, *, owner_field: str = "assigned_to") -> Q:
    if is_superuser(user):
        return Q()
    if can_view_team_workload(user):
        visible = get_visible_user_ids(user)
        if visible is None:
            return Q()
        return Q(**{f"{owner_field}_id__in": visible}) | Q(**{f"{owner_field}__isnull": True}) | Q(created_by=user)
    return Q(**{owner_field: user}) | Q(created_by=user)


def can_view_owned_record(user, *, owner_id: int | None, created_by_id: int | None = None) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if is_superuser(user):
        return True
    if owner_id == user.pk or created_by_id == user.pk:
        return True
    if not can_view_team_workload(user):
        return False
    visible = get_visible_user_ids(user)
    if visible is None:
        return True
    if owner_id is None:
        return True
    return owner_id in visible


def require_visible_property(user, property_id):
    if property_id in (None, "", "all"):
        return None
    from accounts.models import Property

    try:
        pk = int(property_id)
    except (TypeError, ValueError) as exc:
        raise ScopeError("property must be an integer.", code="invalid_property", status=400) from exc
    property_obj = Property.objects.filter(pk=pk).first()
    if property_obj is None:
        raise ScopeError("Unknown property.", code="unknown_property", status=404)
    if not can_access_property(user, property_obj):
        raise ScopeError("You do not have access to this property.", code="property_forbidden", status=403)
    return property_obj


def serialize_session_scope(user) -> dict:
    assigned = []
    assigned_manager = getattr(user, "assigned_properties", None)
    if assigned_manager is not None:
        assigned = [{"id": item.pk, "name": item.name} for item in assigned_manager.all().order_by("name", "id")]
    visible = [{"id": item.pk, "name": item.name} for item in get_visible_properties(user).order_by("name", "id")]
    global_access = has_global_property_access(user)
    return {
        "assigned_properties": assigned,
        "visible_properties": visible,
        "property_scope": "all_authorized" if global_access else "assigned",
        "property_scope_label": "All authorized properties" if global_access else None,
    }
