"""Central authorization service for iBilik CRM.

Views must call this module instead of scattering role checks. Superusers
are unrestricted. Property access is resolved here so endpoints do not
duplicate object-level rules.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db.models import QuerySet

from accounts.catalog import (
    GROUP_ROLES,
    PERMISSION_BY_API,
    ROLE_GROUPS,
    ROLE_LEVELS,
    ROLE_SUPERUSER,
    api_permission_from_django,
)

UserLike = AbstractBaseUser | AnonymousUser
PROPERTY_ACCESS_GLOBAL = "GLOBAL"
PROPERTY_ACCESS_ASSIGNED = "ASSIGNED"


def is_superuser(user: UserLike) -> bool:
    return bool(getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False))


def get_role(user: UserLike) -> str | None:
    if not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "is_superuser", False):
        return ROLE_SUPERUSER

    group_names = set(user.groups.values_list("name", flat=True))
    if not group_names:
        return None

    from accounts.models import Role

    for role in Role.objects.filter(is_active=True).exclude(code=ROLE_SUPERUSER).select_related("group").order_by("level"):
        group_name = role.group.name if role.group_id else ROLE_GROUPS.get(role.code)
        if group_name and group_name in group_names:
            return role.code

    for role_code, group_name in sorted(ROLE_GROUPS.items(), key=lambda item: ROLE_LEVELS.get(item[0], 99)):
        if group_name in group_names:
            return role_code

    for name in group_names:
        role = GROUP_ROLES.get(name)
        if role:
            return role
    return None


def get_effective_permissions(user: UserLike) -> list[str]:
    """Return API permission names inherited from the user's assigned role.

    Superusers are unrestricted and return an empty list; callers must treat
    ``is_superuser`` as full authority. Django ``user_permissions`` are
    legacy and are not part of effective access.
    """

    if not getattr(user, "is_authenticated", False):
        return []
    if getattr(user, "is_superuser", False):
        return []

    role = get_role(user)
    if not role or role == ROLE_SUPERUSER:
        return []

    from django.contrib.auth.models import Group

    from accounts.catalog import ROLE_GROUPS
    from accounts.models import Role

    record = Role.objects.filter(code=role).select_related("group").first()
    group = record.group if record is not None and record.group_id else None
    if group is None:
        group_name = ROLE_GROUPS.get(role)
        group = Group.objects.filter(name=group_name).first() if group_name else None

    names = []
    if group is not None:
        for permission in group.permissions.select_related("content_type"):
            django_perm = f"{permission.content_type.app_label}.{permission.codename}"
            api_codename = api_permission_from_django(django_perm)
            if api_codename:
                names.append(api_codename)
    return sorted(names)


def user_has_permission(user: UserLike, api_codename: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True

    if api_codename not in PERMISSION_BY_API:
        return False
    return api_codename in get_effective_permissions(user)


def get_api_permissions(user: UserLike) -> list[str]:
    return get_effective_permissions(user)


def has_global_property_access(user: UserLike) -> bool:
    if is_superuser(user):
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    profile = getattr(user, "property_access_profile", None)
    if profile is not None and profile.mode == PROPERTY_ACCESS_GLOBAL:
        return True
    role = get_role(user)
    if role == ROLE_SUPERUSER:
        return True
    from accounts.models import Role

    return Role.objects.filter(code=role, all_properties=True, is_active=True).exists()


def get_property_access_mode(user: UserLike) -> str:
    if has_global_property_access(user):
        return PROPERTY_ACCESS_GLOBAL
    return PROPERTY_ACCESS_ASSIGNED


def can_access_property(user: UserLike, property_obj) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if is_superuser(user):
        return True
    if has_global_property_access(user):
        return True
    if property_obj is None:
        return False
    assigned = getattr(user, "assigned_properties", None)
    if assigned is None:
        return False
    return assigned.filter(pk=property_obj.pk).exists()


def accessible_properties(user: UserLike, queryset: QuerySet | None = None):
    from accounts.models import Property

    qs = queryset if queryset is not None else Property.objects.all()
    if not getattr(user, "is_authenticated", False):
        return qs.none()
    if is_superuser(user) or has_global_property_access(user):
        return qs
    return qs.filter(staff=user)


def assigned_property_ids(user: UserLike) -> list[int]:
    if not getattr(user, "is_authenticated", False):
        return []
    if has_global_property_access(user):
        return []
    assigned = getattr(user, "assigned_properties", None)
    if assigned is None:
        return []
    return list(assigned.values_list("id", flat=True))


def scope_queryset(user: UserLike, queryset, *, resource: str | None = None):
    """Return a queryset the user is allowed to see.

    Property querysets are always filtered through the centralized access
    rule. Superusers and GLOBAL users see every property, including ones
    created later.
    """

    model_name = getattr(getattr(queryset, "model", None), "__name__", None)
    if resource == "properties" or model_name == "Property":
        return accessible_properties(user, queryset)
    if resource == "locations" or model_name == "Location":
        from locations.access import accessible_locations

        return accessible_locations(user, queryset)
    if resource in {"conversations", "customers", "messages"} or model_name in {"Conversation", "Customer", "Message"}:
        from crm.access import accessible_conversations, accessible_customers, accessible_messages

        if resource == "conversations" or model_name == "Conversation":
            return accessible_conversations(user, queryset)
        if resource == "customers" or model_name == "Customer":
            return accessible_customers(user, queryset)
        return accessible_messages(user, queryset)
    if resource in {"pipeline", "opportunities", "cases"} or model_name in {"Opportunity", "Case", "CaseFollowUp"}:
        if model_name == "Opportunity":
            from pipeline.access import accessible_opportunities

            return accessible_opportunities(user, queryset)
        from cases.access import accessible_cases, accessible_follow_ups

        if model_name == "CaseFollowUp":
            return accessible_follow_ups(user, queryset)
        return accessible_cases(user, queryset)
    if resource in {"match", "match_requests"} or model_name in {"MatchRequest", "MatchRequestNote", "MatchRequestHistory"}:
        from match.access import accessible_requests

        if model_name == "MatchRequestNote":
            return queryset.filter(request_id__in=accessible_requests(user).values("pk"))
        if model_name == "MatchRequestHistory":
            return queryset.filter(request_id__in=accessible_requests(user).values("pk"))
        return accessible_requests(user, queryset)
    if is_superuser(user):
        return queryset
    return queryset


def can_manage_superuser(actor: UserLike) -> bool:
    return is_superuser(actor)
