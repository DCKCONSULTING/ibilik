from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction

from accounts.authorization import get_role
from accounts.catalog import ROLE_STAFF
from accounts.models import Property, PropertyStaffAssignment


def catalog_roles() -> list[dict]:
    from accounts.serializers import serialize_roles

    return serialize_roles()


def catalog_role_ids() -> set[str]:
    return {item["id"] for item in catalog_roles()}


def serialize_role_ref(role_code: str | None) -> dict | None:
    if not role_code:
        return None
    for item in catalog_roles():
        if item["id"] == role_code or item["code"] == role_code:
            return {"id": item["id"], "name": item["name"], "code": item["code"]}
    return {"id": role_code, "name": role_code, "code": role_code}


def parse_role_code(value) -> str:
    if value in (None, ""):
        return ""
    text = str(value).strip()
    valid = catalog_role_ids()
    if text not in valid:
        raise ValueError("Role is not supported.")
    return text


def default_role_for_user(user: User) -> str:
    role = get_role(user)
    if role and role in catalog_role_ids():
        return role
    return ROLE_STAFF


def assignment_for(property_obj: Property, user: User, *, actor: User | None = None) -> PropertyStaffAssignment:
    assignment = PropertyStaffAssignment.objects.filter(property=property_obj, user=user).first()
    if assignment:
        return assignment
    return PropertyStaffAssignment.objects.create(
        property=property_obj,
        user=user,
        role=default_role_for_user(user),
        is_active=user.is_active,
        assigned_by=actor,
    )


def validate_reports_to(property_obj: Property, user: User, manager: User | None) -> User | None:
    if manager is None:
        return None
    if manager.pk == user.pk:
        raise ValueError("A staff member cannot report to themselves.")
    if not property_obj.staff.filter(pk=manager.pk).exists():
        raise ValueError("The reporting manager must already be assigned to this property.")
    current = manager
    seen = set()
    while current is not None:
        if current.pk == user.pk:
            raise ValueError("This reporting line would create a circular hierarchy.")
        if current.pk in seen:
            raise ValueError("This reporting line would create a circular hierarchy.")
        seen.add(current.pk)
        next_assignment = PropertyStaffAssignment.objects.filter(property=property_obj, user=current).first()
        current = None if next_assignment is None else next_assignment.reports_to
    return manager


def parse_reports_to_id(value):
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("A valid reports_to_id is required.")
    return value


@transaction.atomic
def assign_property_staff(
    property_obj: Property,
    user: User,
    *,
    role: str | None = None,
    reports_to_id=None,
    actor: User | None = None,
) -> PropertyStaffAssignment:
    property_obj.staff.add(user)
    assignment = assignment_for(property_obj, user, actor=actor)
    if role is not None:
        assignment.role = parse_role_code(role) or default_role_for_user(user)
    manager = None
    if reports_to_id is not None:
        manager_id = parse_reports_to_id(reports_to_id)
        if manager_id is not None:
            manager = User.objects.filter(pk=manager_id).first()
            if manager is None:
                raise ValueError("Reporting manager not found.")
        assignment.reports_to = validate_reports_to(property_obj, user, manager)
    if actor is not None and assignment.assigned_by_id is None:
        assignment.assigned_by = actor
    assignment.save()
    return assignment


@transaction.atomic
def update_property_staff(property_obj: Property, user: User, payload: dict, *, actor: User | None = None) -> PropertyStaffAssignment:
    if not property_obj.staff.filter(pk=user.pk).exists():
        raise ValueError("This user is not assigned to the property.")
    assignment = assignment_for(property_obj, user, actor=actor)
    if "role" in payload:
        assignment.role = parse_role_code(payload.get("role")) or default_role_for_user(user)
    if "reports_to_id" in payload:
        manager_id = parse_reports_to_id(payload.get("reports_to_id"))
        manager = None
        if manager_id is not None:
            manager = User.objects.filter(pk=manager_id).first()
            if manager is None:
                raise ValueError("Reporting manager not found.")
        assignment.reports_to = validate_reports_to(property_obj, user, manager)
    if "is_active" in payload:
        if not isinstance(payload.get("is_active"), bool):
            raise ValueError("is_active must be a boolean.")
        assignment.is_active = payload["is_active"]
    assignment.save()
    return assignment


@transaction.atomic
def remove_property_staff(property_obj: Property, user: User) -> None:
    PropertyStaffAssignment.objects.filter(property=property_obj, reports_to=user).update(reports_to=None)
    PropertyStaffAssignment.objects.filter(property=property_obj, user=user).delete()
    property_obj.staff.remove(user)


def serialize_staff_member(user: User, assignment: PropertyStaffAssignment | None, *, manager_assignment: PropertyStaffAssignment | None = None) -> dict:
    from accounts.serializers import display_name
    role_code = assignment.role if assignment and assignment.role else default_role_for_user(user)
    reports_to = None
    if assignment and assignment.reports_to_id and manager_assignment is not None:
        manager = assignment.reports_to
        reports_to = {
            "id": manager.pk,
            "name": display_name(manager),
            "role": serialize_role_ref(manager_assignment.role or default_role_for_user(manager)),
        }
    return {
        "id": user.pk,
        "username": user.username,
        "display_name": display_name(user),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "is_active": user.is_active if assignment is None else assignment.is_active and user.is_active,
        "role": serialize_role_ref(role_code),
        "reports_to": reports_to,
        "assigned_at": assignment.assigned_at.isoformat() if assignment and assignment.assigned_at else None,
    }


def list_property_staff(property_obj: Property) -> list[PropertyStaffAssignment]:
    assigned = list(property_obj.staff.order_by("first_name", "last_name", "username"))
    assignments = {
        item.user_id: item
        for item in PropertyStaffAssignment.objects.filter(property=property_obj, user__in=assigned).select_related(
            "user", "reports_to"
        )
    }
    synced = []
    for user in assigned:
        assignment = assignments.get(user.pk)
        if assignment is None:
            assignment = assignment_for(property_obj, user)
        synced.append(assignment)
    return synced


def serialize_property_staff_collection(property_obj: Property) -> list[dict]:
    assignments = list_property_staff(property_obj)
    by_user = {item.user_id: item for item in assignments}
    return [
        serialize_staff_member(
            item.user,
            item,
            manager_assignment=by_user.get(item.reports_to_id) if item.reports_to_id else None,
        )
        for item in assignments
    ]


def build_staff_hierarchy(results: list[dict]) -> list[dict]:
    by_id = {item["id"]: item for item in results}
    children: dict[int, list[int]] = {item["id"]: [] for item in results}
    roots = []
    for item in results:
        manager_id = item["reports_to"]["id"] if item.get("reports_to") else None
        if manager_id in by_id:
            children[manager_id].append(item["id"])
        else:
            roots.append(item["id"])

    def node(user_id: int) -> dict:
        item = by_id[user_id]
        return {
            **item,
            "reports": [node(child_id) for child_id in children[user_id]],
        }

    return [node(user_id) for user_id in roots]
