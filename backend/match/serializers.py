from __future__ import annotations

from accounts.authorization import get_role
from accounts.catalog import role_display_name
from accounts.serializers import display_name, serialize_assigned_properties
from cases.serializers import isoformat, serialize_user_summary
from match.models import (
    MatchAssignmentMethod,
    MatchRequest,
    MatchRequestHistory,
    MatchRequestNote,
    MatchRequestPriority,
    MatchRequestStatus,
    MatchRequestType,
    MatchSettings,
)


def serialize_choice(choices) -> list[dict]:
    return [{"id": value, "label": label} for value, label in choices]


def serialize_staff_option(user) -> dict | None:
    if user is None:
        return None
    role = get_role(user)
    name = display_name(user)
    payload = {
        "id": user.pk,
        "username": user.username,
        "name": name,
        "display_name": name,
        "role": role,
        "role_name": role_display_name(role),
        "is_active": bool(user.is_active),
        "assigned_properties": serialize_assigned_properties(user),
    }
    return payload


def serialize_related_record(request: MatchRequest) -> dict | None:
    if request.related_payment_id and request.related_payment:
        payment = request.related_payment
        return {
            "kind": "payment",
            "id": payment.pk,
            "number": payment.payment_number,
            "label": payment.payment_number,
            "title": payment.get_status_display(),
        }
    if request.related_quote_id and request.related_quote:
        quote = request.related_quote
        return {
            "kind": "quote",
            "id": quote.pk,
            "number": quote.quote_number,
            "label": quote.quote_number,
            "title": quote.get_status_display(),
        }
    if request.related_case_id and request.related_case:
        case = request.related_case
        kind = "booking" if case.check_in else "case"
        return {
            "kind": kind,
            "id": case.pk,
            "number": case.case_number,
            "label": case.case_number,
            "title": case.title,
        }
    return None


def serialize_note(note: MatchRequestNote) -> dict:
    return {
        "id": note.pk,
        "body": note.body,
        "created_by": serialize_user_summary(note.created_by),
        "created_at": isoformat(note.created_at),
    }


def serialize_history(entry: MatchRequestHistory) -> dict:
    return {
        "id": entry.pk,
        "action": entry.action,
        "action_label": entry.get_action_display(),
        "previous_value": entry.previous_value,
        "new_value": entry.new_value,
        "actor": serialize_user_summary(entry.actor),
        "created_at": isoformat(entry.created_at),
    }


def serialize_request(request: MatchRequest, *, include_detail: bool = False) -> dict:
    customer = request.customer
    property_obj = request.property
    location = request.location
    assigned = serialize_staff_option(request.assigned_to)
    payload = {
        "id": request.pk,
        "request_number": request.request_number,
        "request_type": request.request_type,
        "request_type_label": request.get_request_type_display(),
        "source_module": request.source_module,
        "source_ref": request.source_ref,
        "subject": request.subject,
        "description": request.description,
        "priority": request.priority,
        "priority_label": request.get_priority_display(),
        "status": request.status,
        "status_label": request.get_status_display(),
        "customer": None
        if customer is None
        else {
            "id": customer.pk,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "status": customer.status,
        },
        "property": None if property_obj is None else {"id": property_obj.pk, "name": property_obj.name},
        "location": None
        if location is None
        else {
            "id": location.pk,
            "name": location.name,
            "code": location.code,
        },
        "related_record": serialize_related_record(request),
        "related_case": None
        if request.related_case_id is None or request.related_case is None
        else {
            "id": request.related_case.pk,
            "case_number": request.related_case.case_number,
            "title": request.related_case.title,
            "stage": request.related_case.stage,
        },
        "related_quote": None
        if request.related_quote_id is None or request.related_quote is None
        else {
            "id": request.related_quote.pk,
            "quote_number": request.related_quote.quote_number,
            "status": request.related_quote.status,
        },
        "related_payment": None
        if request.related_payment_id is None or request.related_payment is None
        else {
            "id": request.related_payment.pk,
            "payment_number": request.related_payment.payment_number,
            "status": request.related_payment.status,
            "amount": str(request.related_payment.amount),
            "currency": request.related_payment.currency,
        },
        "assigned_to": assigned,
        "assigned_by": serialize_staff_option(request.assigned_by),
        "assigned_at": isoformat(request.assigned_at),
        "assignment_method": request.assignment_method or None,
        "assignment_method_label": (
            MatchAssignmentMethod(request.assignment_method).label if request.assignment_method else None
        ),
        "workload_at_assignment": request.workload_at_assignment,
        "unassigned_reason": request.unassigned_reason or None,
        "due_at": isoformat(request.due_at),
        "is_overdue": request.is_overdue(),
        "internal_notes": request.internal_notes,
        "resolution_notes": request.resolution_notes,
        "created_by": serialize_user_summary(request.created_by),
        "created_at": isoformat(request.created_at),
        "updated_at": isoformat(request.updated_at),
    }
    if include_detail:
        from match.assignment import active_workload

        payload["notes"] = [serialize_note(item) for item in request.notes.select_related("created_by")]
        payload["history"] = [serialize_history(item) for item in request.history.select_related("actor")[:80]]
        payload["assigned_to_workload"] = active_workload(request.assigned_to_id) if request.assigned_to_id else None
    return payload


def serialize_statuses():
    return serialize_choice(MatchRequestStatus.choices)


def serialize_priorities():
    return serialize_choice(MatchRequestPriority.choices)


def serialize_types():
    return serialize_choice(MatchRequestType.choices)


def serialize_settings(settings: MatchSettings) -> dict:
    return {
        "auto_assign_enabled": settings.auto_assign_enabled,
        "property_staff_only": settings.property_staff_only,
        "org_wide_when_no_property": settings.org_wide_when_no_property,
        "assignment_mode": settings.assignment_mode,
        "assignment_mode_label": "Lowest active workload",
        "updated_at": isoformat(settings.updated_at),
    }


def serialize_workload_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "name": row["name"],
        "display_name": row["display_name"],
        "active_requests": row["active_requests"],
        "last_assigned_at": isoformat(row["last_assigned_at"]),
        "eligible": row["eligible"],
        "assigned_properties": row["assigned_properties"],
    }
