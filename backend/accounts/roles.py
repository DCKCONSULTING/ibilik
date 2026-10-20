from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models import Q

from accounts.authorization import (
    assigned_property_ids,
    has_global_property_access,
    is_superuser,
    user_has_permission,
)
from accounts.catalog import (
    ROLE_DEFAULT_PERMISSIONS,
    ROLE_DISPLAY_NAMES,
    ROLE_GROUPS,
    ROLE_LEVELS,
    ROLE_MANAGER,
    ROLE_STAFF,
    ROLE_SUPERUSER,
    ROLE_TOP_MANAGER,
)
from accounts.models import Role, UserPropertyAccess


BUILTIN_ROLE_DEFS = (
    {
        "code": ROLE_SUPERUSER,
        "name": ROLE_DISPLAY_NAMES[ROLE_SUPERUSER],
        "description": "System administrator. Full system access. Protected Django superuser.",
        "level": 0,
        "parent_code": None,
        "is_system_role": True,
        "is_builtin": True,
        "all_properties": True,
        "can_manage_lower_users": True,
        "can_assign_property_staff": True,
    },
    {
        "code": ROLE_TOP_MANAGER,
        "name": ROLE_DISPLAY_NAMES[ROLE_TOP_MANAGER],
        "description": "All properties. Manage lower-level managers and staff.",
        "level": 1,
        "parent_code": ROLE_SUPERUSER,
        "is_system_role": False,
        "is_builtin": True,
        "all_properties": True,
        "can_manage_lower_users": True,
        "can_assign_property_staff": True,
    },
    {
        "code": ROLE_MANAGER,
        "name": ROLE_DISPLAY_NAMES[ROLE_MANAGER],
        "description": "Assigned properties. Manage staff within permitted scope.",
        "level": 2,
        "parent_code": ROLE_TOP_MANAGER,
        "is_system_role": False,
        "is_builtin": True,
        "all_properties": False,
        "can_manage_lower_users": True,
        "can_assign_property_staff": True,
    },
    {
        "code": ROLE_STAFF,
        "name": ROLE_DISPLAY_NAMES[ROLE_STAFF],
        "description": "Assigned properties. Limited CRM access.",
        "level": 3,
        "parent_code": ROLE_MANAGER,
        "is_system_role": False,
        "is_builtin": True,
        "all_properties": False,
        "can_manage_lower_users": False,
        "can_assign_property_staff": False,
    },
)


def known_role_codes() -> set[str]:
    codes = {ROLE_SUPERUSER, *ROLE_GROUPS.keys()}
    codes.update(Role.objects.values_list("code", flat=True))
    return codes


def get_role_record(code: str | None) -> Role | None:
    if not code:
        return None
    return Role.objects.filter(code=code).first()


def role_level(code: str | None) -> int:
    if not code:
        return 99
    record = get_role_record(code)
    if record is not None:
        return record.level
    return ROLE_LEVELS.get(code, 99)


def role_allows_all_properties(code: str | None) -> bool:
    if code == ROLE_SUPERUSER:
        return True
    record = get_role_record(code)
    return bool(record and record.all_properties)


def role_can_manage_lower_users(code: str | None) -> bool:
    if code == ROLE_SUPERUSER:
        return True
    record = get_role_record(code)
    return bool(record and record.can_manage_lower_users)


def default_property_mode_for_role(code: str | None) -> str:
    if role_allows_all_properties(code):
        return UserPropertyAccess.Mode.GLOBAL
    return UserPropertyAccess.Mode.ASSIGNED


def can_assign_role(actor: User, role_code: str | None) -> bool:
    if role_code in (None, ""):
        return False
    if role_code not in known_role_codes():
        return False
    if is_superuser(actor):
        return True
    if role_code == ROLE_SUPERUSER:
        return False
    actor_level = role_level(get_actor_role(actor))
    if role_level(role_code) <= actor_level:
        return False
    if user_has_permission(actor, "users.manage_roles"):
        return True
    if role_can_manage_lower_users(get_actor_role(actor)) and user_has_permission(actor, "users.manage_user"):
        return True
    if user_has_permission(actor, "properties.manage_staff") and role_code == ROLE_STAFF:
        return True
    return False


def get_actor_role(actor: User) -> str | None:
    from accounts.authorization import get_role

    return get_role(actor)


def can_manage_target_user(actor: User, target: User) -> bool:
    if is_superuser(actor):
        return True
    if target.is_superuser:
        return False
    if actor.pk == target.pk:
        return False
    if role_level(get_actor_role(target)) <= role_level(get_actor_role(actor)):
        return False
    if not (
        user_has_permission(actor, "users.manage_user")
        or user_has_permission(actor, "properties.manage_staff")
        or user_has_permission(actor, "users.manage_roles")
    ):
        return False
    if has_global_property_access(actor):
        return True
    actor_ids = set(assigned_property_ids(actor))
    if not actor_ids:
        return True
    target_ids = set(target.assigned_properties.values_list("id", flat=True))
    return bool(actor_ids.intersection(target_ids))


def visible_users(actor: User, queryset):
    from accounts.scope import get_visible_users

    return get_visible_users(actor, queryset)


def validate_parent(role: Role | None, parent: Role | None) -> Role | None:
    if parent is None:
        return None
    if role is not None and parent.pk == role.pk:
        raise ValueError("A role cannot be its own parent.")
    current = parent
    seen = set()
    while current is not None:
        if role is not None and current.pk == role.pk:
            raise ValueError("This parent would create a circular role hierarchy.")
        if current.pk in seen:
            raise ValueError("This parent would create a circular role hierarchy.")
        seen.add(current.pk)
        current = current.parent
    if role is not None and parent.level >= role.level:
        raise ValueError("A parent role must be a higher level.")
    return parent


@transaction.atomic
def ensure_builtin_roles() -> list[Role]:
    created = {}
    for item in BUILTIN_ROLE_DEFS:
        defaults = {
            "name": item["name"],
            "description": item["description"],
            "level": item["level"],
            "is_system_role": item["is_system_role"],
            "is_builtin": item["is_builtin"],
            "all_properties": item["all_properties"],
            "can_manage_lower_users": item["can_manage_lower_users"],
            "can_assign_property_staff": item["can_assign_property_staff"],
        }
        role, was_created = Role.objects.get_or_create(code=item["code"], defaults=defaults)
        if not was_created and role.code == ROLE_SUPERUSER and role.name == "Superuser":
            role.name = item["name"]
            role.save(update_fields=["name"])
        group_name = ROLE_GROUPS.get(item["code"])
        if group_name:
            group = Group.objects.filter(name=group_name).first()
            if group is not None and role.group_id != group.pk:
                role.group = group
                role.save(update_fields=["group"])
        created[item["code"]] = role

    for item in BUILTIN_ROLE_DEFS:
        role = created[item["code"]]
        parent_code = item["parent_code"]
        if parent_code and role.parent_id != created[parent_code].pk:
            role.parent = created[parent_code]
            role.save(update_fields=["parent"])
    return list(created.values())


def group_permission_codenames(group: Group | None) -> list[str]:
    from accounts.catalog import api_permission_from_django

    if group is None:
        return []
    names = []
    for permission in group.permissions.select_related("content_type"):
        django_perm = f"{permission.content_type.app_label}.{permission.codename}"
        api_codename = api_permission_from_django(django_perm)
        if api_codename:
            names.append(api_codename)
    return sorted(names)


def set_role_permissions(role: Role, api_names: list[str]) -> None:
    from accounts.services import _permissions_for_api_names
    from accounts.catalog import PERMISSION_BY_API

    if role.is_system_role or role.code == ROLE_SUPERUSER:
        raise PermissionError("The System Admin role cannot be modified.")
    unknown = [name for name in api_names if name not in PERMISSION_BY_API]
    if unknown:
        raise ValueError("Unknown permission.")
    if role.group is None:
        raise ValueError("This role has no permission group.")
    role.group.permissions.set(_permissions_for_api_names(api_names))


def actor_can_grant_permissions(actor: User, api_names: list[str]) -> bool:
    if is_superuser(actor):
        return True
    return all(user_has_permission(actor, name) for name in api_names)


@transaction.atomic
def update_role(role: Role, payload: dict, *, actor: User) -> Role:
    if role.is_system_role or role.code == ROLE_SUPERUSER:
        raise PermissionError("The System Admin role cannot be modified.")
    if not is_superuser(actor) and not user_has_permission(actor, "users.manage_roles"):
        raise PermissionError("You do not have permission to manage roles.")

    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("Role name is required.")
        role.name = name
    if "description" in payload:
        role.description = str(payload.get("description") or "")
    if "is_active" in payload:
        if not isinstance(payload.get("is_active"), bool):
            raise ValueError("is_active must be a boolean.")
        role.is_active = payload["is_active"]
    if "all_properties" in payload:
        if not isinstance(payload.get("all_properties"), bool):
            raise ValueError("all_properties must be a boolean.")
        role.all_properties = payload["all_properties"]
    if "can_manage_lower_users" in payload:
        if not isinstance(payload.get("can_manage_lower_users"), bool):
            raise ValueError("can_manage_lower_users must be a boolean.")
        role.can_manage_lower_users = payload["can_manage_lower_users"]
    if "can_assign_property_staff" in payload:
        if not isinstance(payload.get("can_assign_property_staff"), bool):
            raise ValueError("can_assign_property_staff must be a boolean.")
        role.can_assign_property_staff = payload["can_assign_property_staff"]
    if "level" in payload and not role.is_builtin:
        if not isinstance(payload.get("level"), int) or payload["level"] < 1:
            raise ValueError("Level must be a positive integer.")
        role.level = payload["level"]
    if "parent" in payload or "parent_code" in payload:
        parent_code = payload.get("parent_code", payload.get("parent"))
        parent = None if parent_code in (None, "") else Role.objects.filter(code=parent_code).first()
        if parent_code not in (None, "") and parent is None:
            raise ValueError("Parent role not found.")
        role.parent = validate_parent(role, parent)
    if "permissions" in payload:
        permissions = payload.get("permissions")
        if not isinstance(permissions, list) or any(not isinstance(item, str) for item in permissions):
            raise ValueError("Permissions must be a list of permission names.")
        if not actor_can_grant_permissions(actor, permissions):
            raise PermissionError("You cannot grant permissions beyond your own authority.")
        set_role_permissions(role, permissions)
    role.save()
    return role


@transaction.atomic
def create_role(payload: dict, *, actor: User) -> Role:
    if not is_superuser(actor) and not user_has_permission(actor, "users.manage_roles"):
        raise PermissionError("You do not have permission to manage roles.")
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Role name is required.")
    code = str(payload.get("code") or name).strip().upper().replace(" ", "_")
    if Role.objects.filter(code=code).exists() or code == ROLE_SUPERUSER:
        raise ValueError("A role with that code already exists.")
    level = payload.get("level")
    if not isinstance(level, int) or level < 1:
        raise ValueError("Level must be a positive integer.")
    parent_code = payload.get("parent_code", payload.get("parent"))
    parent = None if parent_code in (None, "") else Role.objects.filter(code=parent_code).first()
    if parent_code not in (None, "") and parent is None:
        raise ValueError("Parent role not found.")
    permissions = payload.get("permissions") or []
    if not isinstance(permissions, list) or any(not isinstance(item, str) for item in permissions):
        raise ValueError("Permissions must be a list of permission names.")
    if not actor_can_grant_permissions(actor, permissions):
        raise PermissionError("You cannot grant permissions beyond your own authority.")

    group, _ = Group.objects.get_or_create(name=name)
    role = Role(
        code=code,
        name=name,
        description=str(payload.get("description") or ""),
        level=level,
        is_system_role=False,
        is_builtin=False,
        is_active=bool(payload.get("is_active", True)),
        all_properties=bool(payload.get("all_properties", False)),
        can_manage_lower_users=bool(payload.get("can_manage_lower_users", False)),
        can_assign_property_staff=bool(payload.get("can_assign_property_staff", False)),
        group=group,
    )
    role.parent = validate_parent(role, parent)
    role.save()
    set_role_permissions(role, permissions)
    return role


@transaction.atomic
def deactivate_role(role: Role, *, actor: User) -> None:
    if not is_superuser(actor) and not user_has_permission(actor, "users.manage_roles"):
        raise PermissionError("You do not have permission to manage roles.")
    if role.is_system_role or role.is_builtin or role.code == ROLE_SUPERUSER:
        raise PermissionError("Built-in roles cannot be deleted.")
    role.is_active = False
    role.save(update_fields=["is_active"])
