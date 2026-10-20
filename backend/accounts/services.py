from __future__ import annotations

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q

from accounts.catalog import (
    GROUP_MANAGER,
    GROUP_ROLES,
    GROUP_STAFF,
    PERMISSION_BY_API,
    PERMISSION_DEFINITIONS,
    ROLE_DEFAULT_PERMISSIONS,
    ROLE_GROUPS,
    ROLE_STAFF,
    ROLE_SUPERUSER,
)
from accounts.models import AccessControl, Property, UserPropertyAccess


_UNSET = object()


def ensure_application_permissions() -> list[Permission]:
    content_type, _ = ContentType.objects.get_or_create(
        app_label="accounts",
        model="accesscontrol",
        defaults={"app_label": "accounts", "model": "accesscontrol"},
    )
    if content_type.app_label != "accounts":
        content_type.app_label = "accounts"
        content_type.model = "accesscontrol"
        content_type.save(update_fields=["app_label", "model"])

    created = []
    for definition in PERMISSION_DEFINITIONS:
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=definition.django_codename,
            defaults={"name": definition.name},
        )
        if permission.name != definition.name:
            permission.name = definition.name
            permission.save(update_fields=["name"])
        created.append(permission)
    return created


def _permissions_for_api_names(api_names: tuple[str, ...] | list[str]) -> list[Permission]:
    django_codenames = [PERMISSION_BY_API[name].django_codename for name in api_names if name in PERMISSION_BY_API]
    return list(Permission.objects.filter(content_type__app_label="accounts", codename__in=django_codenames))


def ensure_role_groups() -> dict[str, Group]:
    ensure_application_permissions()
    groups = {}
    for role, group_name in ROLE_GROUPS.items():
        group, created = Group.objects.get_or_create(name=group_name)
        desired = _permissions_for_api_names(ROLE_DEFAULT_PERMISSIONS.get(role, ()))
        if created or not group.permissions.exists():
            group.permissions.set(desired)
        else:
            current = set(group.permissions.values_list("pk", flat=True))
            missing = [item for item in desired if item.pk not in current]
            if missing:
                group.permissions.add(*missing)
        groups[role] = group
    return groups


def initialize_access_control() -> None:
    AccessControl.objects.get_or_create(pk=1)
    ensure_role_groups()
    from accounts.roles import ensure_builtin_roles

    ensure_builtin_roles()


def get_role_group(role: str) -> Group | None:
    from accounts.models import Role

    record = Role.objects.filter(code=role).select_related("group").first()
    if record and record.group_id:
        return record.group
    group_name = ROLE_GROUPS.get(role)
    if not group_name:
        return None
    return Group.objects.filter(name=group_name).first()


def assign_role(user: User, role: str | None) -> None:
    from accounts.models import Role

    role_group_ids = list(Role.objects.exclude(group=None).values_list("group_id", flat=True))
    role_group_names = set(ROLE_GROUPS.values())
    current = user.groups.filter(Q(name__in=role_group_names) | Q(pk__in=role_group_ids))
    user.groups.remove(*current)
    user.user_permissions.clear()

    if not role or role == ROLE_SUPERUSER:
        return

    group = get_role_group(role)
    if group is None:
        raise ValueError("Unknown role.")
    user.groups.add(group)


def set_individual_permissions(user: User, api_names: list[str]) -> None:
    """Legacy helper. Writes Django user_permissions but does not grant CRM access.

    Effective permissions come from the user's assigned role. This remains so
    existing rows are preserved; authorization ignores the table.
    """

    unknown = [name for name in api_names if name not in PERMISSION_BY_API]
    if unknown:
        raise ValueError("Unknown permission.")

    permissions = _permissions_for_api_names(api_names)
    user.user_permissions.set(permissions)


def resolve_requested_role(user: User) -> str | None:
    if user.is_superuser:
        return ROLE_SUPERUSER
    for group in user.groups.all():
        role = GROUP_ROLES.get(group.name)
        if role:
            return role
    return None


@transaction.atomic
def create_user(
    *,
    username: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    is_active: bool = True,
    role: str | None = ROLE_STAFF,
    individual_permissions: list[str] | None = None,
    property_access: str | None = None,
    property_ids: list[int] | None = None,
    reports_to_id: int | None = None,
    actor: User | None = None,
) -> User:
    # individual_permissions is a legacy argument. Role membership is the
    # only source of CRM permissions; the value is intentionally ignored.
    _ = individual_permissions
    if role == ROLE_SUPERUSER and (actor is None or not actor.is_superuser):
        raise PermissionError("Only a superuser can create another superuser.")
    if actor is not None:
        validate_actor_assignment_scope(actor, property_access=property_access, property_ids=property_ids)

    user = User(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        is_active=is_active,
        is_staff=role == ROLE_SUPERUSER,
        is_superuser=role == ROLE_SUPERUSER,
    )
    user.set_password(password)
    user.save()

    if role and role != ROLE_SUPERUSER:
        assign_role(user, role)
    else:
        user.user_permissions.clear()
    from accounts.roles import default_property_mode_for_role

    forced_mode = default_property_mode_for_role(role)
    apply_property_access(
        user,
        actor=actor or user,
        mode=forced_mode if forced_mode == UserPropertyAccess.Mode.GLOBAL else (property_access or forced_mode),
        property_ids=property_ids,
        allow_self_change=True,
    )
    if reports_to_id is not None:
        apply_reporting_manager(user, reports_to_id=reports_to_id)
    return user


@transaction.atomic
def update_user(
    user: User,
    *,
    actor: User,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    is_active: bool | None = None,
    role: str | None = None,
    individual_permissions: list[str] | None = None,
    password: str | None = None,
    property_access: str | None = None,
    property_ids: list[int] | None = None,
    reports_to_id: int | None | object = _UNSET,
) -> User:
    _ = individual_permissions
    if user.is_superuser and not actor.is_superuser:
        raise PermissionError("Only a superuser can change another superuser.")

    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    if email is not None:
        user.email = email
    if is_active is not None:
        if user.pk == actor.pk and is_active is False:
            raise PermissionError("You cannot deactivate your own account.")
        user.is_active = is_active

    if role is not None:
        if role == ROLE_SUPERUSER and not actor.is_superuser:
            raise PermissionError("Only a superuser can grant superuser access.")
        if user.pk == actor.pk and role != resolve_requested_role(actor) and not actor.is_superuser:
            raise PermissionError("You cannot change your own role.")
        user.is_superuser = role == ROLE_SUPERUSER
        user.is_staff = user.is_superuser or user.is_staff
        if role == ROLE_SUPERUSER:
            assign_role(user, None)
        else:
            assign_role(user, role)
        from accounts.roles import default_property_mode_for_role

        forced_mode = default_property_mode_for_role(role)
        if forced_mode == UserPropertyAccess.Mode.GLOBAL:
            property_access = forced_mode
        elif property_access is None:
            property_access = forced_mode

    if password:
        user.set_password(password)

    user.save()

    if property_access is not None or property_ids is not None:
        validate_actor_assignment_scope(actor, property_access=property_access, property_ids=property_ids)
        apply_property_access(
            user,
            actor=actor,
            mode=UserPropertyAccess.Mode.GLOBAL if user.is_superuser else property_access,
            property_ids=property_ids,
        )

    if reports_to_id is not _UNSET:
        apply_reporting_manager(user, reports_to_id=reports_to_id if isinstance(reports_to_id, int) else None)

    return user


def apply_property_access(
    user: User,
    *,
    actor: User,
    mode: str | None = None,
    property_ids: list[int] | None = None,
    allow_self_change: bool = False,
) -> UserPropertyAccess:
    if user.is_superuser:
        profile, _ = UserPropertyAccess.objects.update_or_create(
            user=user,
            defaults={"mode": UserPropertyAccess.Mode.GLOBAL},
        )
        return profile

    changing_self = actor.pk == user.pk
    if changing_self and not actor.is_superuser and not allow_self_change:
        profile, _ = UserPropertyAccess.objects.get_or_create(
            user=user,
            defaults={"mode": UserPropertyAccess.Mode.ASSIGNED},
        )
        current_ids = set(user.assigned_properties.values_list("id", flat=True))
        requested_ids = set(property_ids) if property_ids is not None else current_ids
        requested_mode = mode or profile.mode
        if requested_mode != profile.mode or requested_ids != current_ids:
            raise PermissionError("You cannot change your own property access.")
        return profile

    if mode is None:
        profile, _ = UserPropertyAccess.objects.get_or_create(
            user=user,
            defaults={"mode": UserPropertyAccess.Mode.ASSIGNED},
        )
    else:
        if mode not in UserPropertyAccess.Mode.values:
            raise ValueError("Unknown property access mode.")
        profile, _ = UserPropertyAccess.objects.update_or_create(
            user=user,
            defaults={"mode": mode},
        )

    if property_ids is not None and profile.mode == UserPropertyAccess.Mode.ASSIGNED:
        unique_ids = list(dict.fromkeys(property_ids))
        properties = list(Property.objects.filter(pk__in=unique_ids))
        if len(properties) != len(unique_ids):
            raise ValueError("Unknown property.")
        user.assigned_properties.set(properties)

    return profile


def validate_actor_assignment_scope(
    actor: User,
    *,
    property_access: str | None = None,
    property_ids: list[int] | None = None,
) -> None:
    from accounts.authorization import assigned_property_ids, has_global_property_access, is_superuser

    if is_superuser(actor) or has_global_property_access(actor):
        return
    if property_access == UserPropertyAccess.Mode.GLOBAL:
        raise PermissionError("You cannot grant all-properties access.")
    if property_ids is None:
        return
    allowed = set(assigned_property_ids(actor))
    extra = set(property_ids) - allowed
    if extra:
        raise PermissionError("You cannot assign properties outside your authorized scope.")


def apply_reporting_manager(user: User, *, reports_to_id: int | None) -> None:
    from accounts.property_staff import assign_property_staff

    manager_id = None if reports_to_id in (None, 0) else reports_to_id
    value = manager_id if manager_id is not None else ""
    for property_obj in user.assigned_properties.all():
        assign_property_staff(property_obj, user, reports_to_id=value)


def assign_limited_permissions(user: User, api_names: list[str], *, actor: User) -> None:
    """Give a user a dedicated role that owns only the listed permissions.

    Tests that previously wrote Django user_permissions should use this so
    effective access still comes from a role.
    """

    from accounts.models import Role
    from accounts.roles import create_role, set_role_permissions

    if not api_names:
        assign_role(user, None)
        return

    code = f"LIMITED_{user.pk}"
    existing = Role.objects.filter(code=code).first()
    if existing is None:
        create_role(
            {
                "name": f"Limited {user.username}",
                "code": code,
                "level": 9,
                "permissions": api_names,
            },
            actor=actor,
        )
    else:
        set_role_permissions(existing, api_names)
    assign_role(user, code)


def change_own_password(user: User, *, current_password: str, new_password: str) -> None:
    if not isinstance(current_password, str) or not current_password:
        raise ValueError("Current password is required.")
    if not user.check_password(current_password):
        raise ValueError("Current password is incorrect.")
    if not isinstance(new_password, str) or len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if current_password == new_password:
        raise ValueError("Choose a different password.")
    user.set_password(new_password)
    user.save(update_fields=["password"])


def deactivate_own_account(user: User) -> None:
    if user.is_superuser:
        raise PermissionError("System Admin accounts cannot be deactivated from settings.")
    user.is_active = False
    user.save(update_fields=["is_active"])
