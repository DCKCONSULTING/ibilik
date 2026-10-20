from __future__ import annotations

from locations.location_state import OCCUPANCY_LABELS, location_state
from locations.models import Location, LocationStatus, LocationType


def serialize_type(item: LocationType) -> dict:
    return {"id": item.value, "label": item.label}


def serialize_status(item: LocationStatus) -> dict:
    return {"id": item.value, "label": item.label}


def serialize_types() -> list[dict]:
    return [serialize_type(item) for item in LocationType]


def serialize_statuses() -> list[dict]:
    return [serialize_status(item) for item in LocationStatus]


def serialize_occupancies():
    return [
        {"id": "free", "label": OCCUPANCY_LABELS["free"]},
        {"id": "in_house", "label": OCCUPANCY_LABELS["in_house"]},
        {"id": "reserved", "label": OCCUPANCY_LABELS["reserved"]},
    ]


def serialize_property_ref(property_obj) -> dict:
    return {
        "id": property_obj.pk,
        "name": property_obj.name,
    }


def serialize_user_ref(user) -> dict | None:
    if user is None:
        return None
    name = (f"{user.first_name} {user.last_name}").strip() or user.username
    return {"id": user.pk, "username": user.username, "name": name, "display_name": name}


def serialize_case_ref(case, *, include_balance: bool = False) -> dict:
    customer = case.customer
    payload = {
        "id": case.pk,
        "case_number": case.case_number,
        "title": case.title,
        "stage": case.stage,
        "check_in": case.check_in.isoformat() if case.check_in else None,
        "check_out": case.check_out.isoformat() if case.check_out else None,
        "actual_check_in": case.actual_check_in.isoformat() if getattr(case, "actual_check_in", None) else None,
        "actual_check_out": case.actual_check_out.isoformat() if getattr(case, "actual_check_out", None) else None,
        "customer": {
            "id": customer.pk,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
        },
    }
    if include_balance:
        from payments.ledger import case_balance

        balance = case_balance(case)
        payload["outstanding"] = str(balance["outstanding"])
        payload["account_status"] = balance["account_status"]
        payload["account_status_label"] = balance["account_status_label"]
    return payload


def serialize_operational_info(location: Location, *, include_balance: bool = False) -> dict:
    state = location_state(location)
    current = state["current_stay"]
    upcoming = state["next_reservation"]
    primary = current or upcoming
    return {
        "occupancy": state["occupancy"],
        "occupancy_label": state["occupancy_label"],
        "is_free": state["is_free"],
        "is_bookable_now": state["is_bookable_now"],
        "allowed_actions": state["allowed_actions"],
        "current_booking": None if current is None else serialize_case_ref(current, include_balance=include_balance),
        "upcoming_booking": None if upcoming is None else serialize_case_ref(upcoming, include_balance=include_balance),
        "case": None if primary is None else serialize_case_ref(primary, include_balance=include_balance),
        "customer": None if primary is None else serialize_case_ref(primary)["customer"],
    }


def serialize_status_history(item) -> dict:
    return {
        "id": item.pk,
        "previous_status": item.previous_status,
        "new_status": item.new_status,
        "reason": item.reason,
        "changed_by": serialize_user_ref(item.changed_by),
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def serialize_cleaning(item) -> dict:
    return {
        "id": item.pk,
        "status": item.status,
        "status_label": item.get_status_display(),
        "notes": item.notes,
        "assigned_to": serialize_user_ref(item.assigned_to),
        "created_by": serialize_user_ref(item.created_by),
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def serialize_maintenance(item) -> dict:
    return {
        "id": item.pk,
        "title": item.title,
        "description": item.description,
        "priority": item.priority,
        "priority_label": item.get_priority_display(),
        "status": item.status,
        "status_label": item.get_status_display(),
        "notes": item.notes,
        "assigned_to": serialize_user_ref(item.assigned_to),
        "created_by": serialize_user_ref(item.created_by),
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "expected_at": item.expected_at.isoformat() if item.expected_at else None,
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def serialize_location(location: Location, *, include_detail: bool = False) -> dict:
    payload = {
        "id": location.pk,
        "property": serialize_property_ref(location.property),
        "property_id": location.property_id,
        "name": location.name,
        "code": location.code,
        "type": location.location_type,
        "type_label": location.get_location_type_display(),
        "description": location.description,
        "capacity": location.capacity,
        "max_adults": location.max_adults,
        "max_children": location.max_children,
        "floor": location.floor,
        "bed_type": location.bed_type,
        "bed_type_label": location.get_bed_type_display() if location.bed_type else "",
        "bed_count": location.bed_count,
        "base_rate": None if location.base_rate is None else f"{location.base_rate:.2f}",
        "currency": location.currency or location.property.currency,
        "status": location.status,
        "status_label": location.get_status_display(),
        "is_bookable": location.is_bookable,
        "amenities": list(location.amenities or []),
        "size_sqm": None if location.size_sqm is None else f"{location.size_sqm:.2f}",
        "active": location.active,
        "created_at": location.created_at.isoformat() if location.created_at else None,
        "updated_at": location.updated_at.isoformat() if location.updated_at else None,
    }
    payload.update(serialize_operational_info(location, include_balance=include_detail))
    if include_detail:
        payload["status_history"] = [serialize_status_history(item) for item in location.status_history.select_related("changed_by")[:40]]
        payload["cleaning_tasks"] = [serialize_cleaning(item) for item in location.cleaning_tasks.select_related("assigned_to", "created_by")[:20]]
        payload["maintenance_issues"] = [
            serialize_maintenance(item) for item in location.maintenance_issues.select_related("assigned_to", "created_by")[:20]
        ]
        payload["open_maintenance"] = next((item for item in payload["maintenance_issues"] if item["status"] in {"open", "in_progress"}), None)
    return payload
