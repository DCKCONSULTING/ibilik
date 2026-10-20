from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import User

from accounts.authorization import (
    assigned_property_ids,
    get_effective_permissions,
    get_property_access_mode,
    get_role,
)
from accounts.catalog import APP_SECTIONS, PERMISSION_DEFINITIONS, ROLE_DEFAULT_PERMISSIONS, ROLE_GROUPS, permission_section, role_display_name


def display_name(user: User) -> str:
    full_name = user.get_full_name().strip()
    return full_name or user.username


def serialize_assigned_properties(user: User) -> list[dict]:
    properties = getattr(user, "assigned_properties", None)
    if properties is None:
        return []
    return [
        {"id": item.pk, "name": item.name}
        for item in properties.all().order_by("name", "id")
    ]


def serialize_current_user(user: User) -> dict:
    from accounts.roles import role_level
    from accounts.scope import serialize_session_scope

    role = get_role(user)
    permissions = get_effective_permissions(user)
    payload = {
        "id": user.pk,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "display_name": display_name(user),
        "email": user.email,
        "role": role,
        "role_name": role_display_name(role),
        "authority_level": role_level(role),
        "permissions": permissions,
        "effective_permissions": permissions,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "property_access": get_property_access_mode(user),
        "property_ids": assigned_property_ids(user),
    }
    payload.update(serialize_session_scope(user))
    return payload


def serialize_reporting_managers(user: User) -> list[dict]:
    assignments = user.property_staff_assignments.select_related("reports_to").filter(reports_to__isnull=False)
    seen: dict[int, dict] = {}
    for item in assignments:
        manager = item.reports_to
        if manager is None or manager.pk in seen:
            continue
        seen[manager.pk] = {
            "id": manager.pk,
            "name": display_name(manager),
            "username": manager.username,
        }
    return list(seen.values())


def serialize_managed_user(user: User) -> dict:
    from accounts.roles import get_role_record

    payload = serialize_current_user(user)
    role = payload.get("role")
    record = get_role_record(role)
    payload["role_detail"] = {
        "id": role,
        "code": role,
        "name": payload.get("role_name"),
        "authority_level": payload.get("authority_level"),
        "all_properties": bool(record.all_properties) if record is not None else payload.get("property_access") == "GLOBAL",
    }
    payload["individual_permissions"] = []
    payload["assigned_properties"] = serialize_assigned_properties(user)
    payload["reporting_managers"] = serialize_reporting_managers(user)
    payload["permissions_source"] = "role"
    return payload


def format_rate(value: Decimal) -> str:
    return f"{value:.2f}"


def format_time(value) -> str | None:
    if value is None:
        return None
    return value.strftime("%H:%M")


def format_decimal(value) -> str | None:
    if value is None:
        return None
    return f"{value:.6f}".rstrip("0").rstrip(".")


def serialize_property_staff(user: User) -> dict:
    return {
        "id": user.pk,
        "username": user.username,
        "display_name": display_name(user),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_active": user.is_active,
    }


def serialize_property(property_obj, *, include_staff: bool = False, include_summary: bool = False) -> dict:
    staff_manager = property_obj.staff
    payload = {
        "id": property_obj.pk,
        "name": property_obj.name,
        "code": property_obj.code,
        "property_type": property_obj.property_type,
        "property_type_label": property_obj.get_property_type_display(),
        "description": property_obj.description,
        "country": property_obj.country,
        "region": property_obj.region,
        "city": property_obj.city,
        "address_line1": property_obj.address_line1,
        "address_line2": property_obj.address_line2,
        "postal_code": property_obj.postal_code,
        "latitude": format_decimal(property_obj.latitude),
        "longitude": format_decimal(property_obj.longitude),
        "phone": property_obj.phone,
        "email": property_obj.email,
        "website": property_obj.website,
        "currency": property_obj.currency,
        "rate": format_rate(property_obj.rate),
        "base_rate": format_rate(property_obj.rate),
        "status": property_obj.status,
        "status_label": property_obj.get_status_display(),
        "check_in_time": format_time(property_obj.check_in_time),
        "check_out_time": format_time(property_obj.check_out_time),
        "timezone": property_obj.timezone,
        "star_rating": property_obj.star_rating,
        "amenities": list(property_obj.amenities or []),
        "staff_count": (
            getattr(property_obj, "staff_count", None)
            if getattr(property_obj, "staff_count", None) is not None
            else staff_manager.count()
        ),
        "location_count": (
            getattr(property_obj, "location_count", None)
            if getattr(property_obj, "location_count", None) is not None
            else property_obj.locations.count()
        ),
        "created_at": property_obj.created_at.isoformat() if property_obj.created_at else None,
        "updated_at": property_obj.updated_at.isoformat() if property_obj.updated_at else None,
    }
    if include_staff:
        from accounts.property_staff import serialize_property_staff_collection

        payload["staff"] = serialize_property_staff_collection(property_obj)
    if include_summary:
        from accounts.property_services import property_summary

        payload["summary"] = property_summary(property_obj)
    return payload


def get_individual_permissions(user: User) -> list[str]:
    """Legacy Django user_permissions reader. Not used for CRM authorization."""
    from accounts.catalog import api_permission_from_django

    api_perms = []
    for permission in user.user_permissions.select_related("content_type"):
        django_perm = f"{permission.content_type.app_label}.{permission.codename}"
        api_codename = api_permission_from_django(django_perm)
        if api_codename:
            api_perms.append(api_codename)
    return sorted(api_perms)


def serialize_role(role: str, group_name: str | None) -> dict:
    return {
        "id": role,
        "name": role_display_name(role) if role == "SUPERUSER" else (group_name or role_display_name(role)),
        "code": role,
        "permissions": list(ROLE_DEFAULT_PERMISSIONS.get(role, ())),
        "is_system_role": role == "SUPERUSER",
        "level": 0 if role == "SUPERUSER" else None,
        "description": "",
        "is_active": True,
        "protected": role == "SUPERUSER",
    }


def serialize_role_record(role, *, actor=None) -> dict:
    from accounts.roles import can_assign_role, group_permission_codenames
    from django.contrib.auth.models import User

    if role.code == "SUPERUSER":
        permissions = []
        user_count = User.objects.filter(is_superuser=True).count()
    else:
        permissions = group_permission_codenames(role.group)
        user_count = role.group.user_set.count() if role.group_id else 0
    payload = {
        "id": role.code,
        "name": role.name,
        "code": role.code,
        "description": role.description,
        "level": role.level,
        "parent": role.parent.code if role.parent_id else None,
        "is_system_role": role.is_system_role,
        "is_builtin": role.is_builtin,
        "is_active": role.is_active,
        "protected": role.is_system_role,
        "all_properties": role.all_properties,
        "can_manage_lower_users": role.can_manage_lower_users,
        "can_assign_property_staff": role.can_assign_property_staff,
        "permissions": permissions,
        "user_count": user_count,
    }
    if actor is not None:
        payload["assignable"] = can_assign_role(actor, role.code)
    return payload


def serialize_roles(actor=None) -> list[dict]:
    from accounts.models import Role
    from accounts.roles import ensure_builtin_roles

    if not Role.objects.exists():
        ensure_builtin_roles()
    records = list(Role.objects.select_related("parent", "group").order_by("level", "name", "id"))
    if records:
        return [serialize_role_record(item, actor=actor) for item in records]
    roles = [serialize_role("SUPERUSER", "System Admin")]
    for role, group_name in ROLE_GROUPS.items():
        roles.append(serialize_role(role, group_name))
    return roles


def serialize_app_sections() -> list[dict]:
    return [{"id": item["id"], "name": item["name"]} for item in APP_SECTIONS]


def serialize_permissions() -> list[dict]:
    return [
        {
            "codename": item.api_codename,
            "name": item.name,
            "module": item.module,
            "section": permission_section(item.api_codename, item.module),
        }
        for item in PERMISSION_DEFINITIONS
    ]
