from __future__ import annotations

from django.contrib.auth.models import User
from django.http import HttpRequest, JsonResponse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.authorization import user_has_permission
from accounts.http import json_error, parse_json_body, require_permission
from accounts.property_services import get_accessible_property
from cases.models import Case
from locations.access import can_access_location
from locations.errors import LocationError
from locations.location_state import (
    check_in_location,
    check_out_location,
    complete_cleaning,
    next_reservation,
    resolve_maintenance,
    set_operational_status,
    start_cleaning,
    start_maintenance,
)
from locations.models import Location, MaintenanceIssue
from locations.serializers import serialize_location, serialize_occupancies, serialize_statuses, serialize_types
from locations.services import (
    create_location,
    deactivate_location,
    delete_location,
    filter_locations,
    locations_for_property,
    apply_occupancy_filter,
    prefetch_stay_cases,
    update_location,
)

VIEW = "properties.view_property"
VIEW_LOCATION = "locations.view_location"
CHANGE = "properties.change_property"
CHECK_IN = "locations.check_in"
CHECK_OUT = "locations.check_out"
CLEANING = "locations.manage_cleaning"
MAINTENANCE = "locations.manage_maintenance"
STATUS = "locations.change_status"
OVERRIDE = "locations.override_check_in"

CONFLICT_CODES = {
    "duplicate_code",
    "location_in_use",
    "stay_conflict",
    "already_checked_in",
    "already_checked_out",
    "status_blocked",
    "location_not_ready",
    "location_inactive",
    "reservation_ineligible",
    "reservation_mismatch",
    "no_active_stay",
    "no_maintenance",
    "payment_required",
}


def _load_accessible_property(request: HttpRequest, property_id: int):
    try:
        property_obj = get_accessible_property(request.user, property_id)
    except PermissionError as exc:
        return None, json_error(str(exc), 403, code="property_forbidden")
    if property_obj is None:
        return None, json_error("Property not found.", 404, code="not_found")
    return property_obj, None


def _load_accessible_location(request: HttpRequest, location_id: int):
    location = Location.objects.select_related("property").filter(pk=location_id).first()
    if location is None:
        return None, json_error("Location not found.", 404, code="not_found")
    if not can_access_location(request.user, location):
        return None, json_error("You do not have access to this property.", 403, code="property_forbidden")
    return location, None


def _handle_error(exc: LocationError) -> JsonResponse:
    status = 409 if exc.code in CONFLICT_CODES else 400
    return json_error(str(exc), status, code=exc.code)


def _detail(location: Location) -> dict:
    location = Location.objects.select_related("property").get(pk=location.pk)
    return serialize_location(location, include_detail=True)


def _optional_user(value):
    if value in (None, ""):
        return None
    try:
        user_id = int(value)
    except (TypeError, ValueError) as exc:
        raise LocationError("Assigned staff must be a user id.", code="invalid_user") from exc
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        raise LocationError("Assigned staff was not found.", code="invalid_user")
    return user


def _optional_datetime(value):
    if value in (None, ""):
        return None
    parsed = parse_datetime(str(value))
    if parsed is None:
        raise LocationError("Datetime is invalid.", code="invalid_datetime")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _load_case(payload: dict, *, required: bool = False):
    case_id = payload.get("case_id") or payload.get("reservation_id")
    if case_id in (None, ""):
        if required:
            raise LocationError("Reservation is required.", code="invalid_reservation")
        return None
    try:
        case_id = int(case_id)
    except (TypeError, ValueError) as exc:
        raise LocationError("Reservation is required.", code="invalid_reservation") from exc
    case = Case.objects.select_related("customer", "property", "location").filter(pk=case_id).first()
    if case is None:
        raise LocationError("Reservation not found.", code="invalid_reservation")
    return case


def _can_override(request: HttpRequest) -> bool:
    return request.user.is_superuser or user_has_permission(request.user, OVERRIDE)


@require_http_methods(["GET", "POST"])
def property_location_collection_view(request: HttpRequest, property_id: int) -> JsonResponse:
    if request.method == "GET":
        return _list_locations(request, property_id)
    return _create_location(request, property_id)


@require_http_methods(["GET", "PATCH", "DELETE"])
def location_detail_view(request: HttpRequest, location_id: int) -> JsonResponse:
    if request.method == "GET":
        return _retrieve_location(request, location_id)
    if request.method == "PATCH":
        return _update_location(request, location_id)
    return _delete_location(request, location_id)


@require_http_methods(["POST"])
def location_deactivate_view(request: HttpRequest, location_id: int) -> JsonResponse:
    return _deactivate_location(request, location_id)


@require_http_methods(["POST"])
def location_check_in_view(request: HttpRequest, location_id: int) -> JsonResponse:
    return _check_in(request, location_id)


@require_http_methods(["POST"])
def location_check_out_view(request: HttpRequest, location_id: int) -> JsonResponse:
    return _check_out(request, location_id)


@require_http_methods(["POST"])
def location_status_view(request: HttpRequest, location_id: int) -> JsonResponse:
    return _change_status(request, location_id)


@require_http_methods(["POST"])
def location_cleaning_start_view(request: HttpRequest, location_id: int) -> JsonResponse:
    return _start_cleaning(request, location_id)


@require_http_methods(["POST"])
def location_cleaning_complete_view(request: HttpRequest, location_id: int) -> JsonResponse:
    return _complete_cleaning(request, location_id)


@require_http_methods(["POST"])
def location_maintenance_start_view(request: HttpRequest, location_id: int) -> JsonResponse:
    return _start_maintenance(request, location_id)


@require_http_methods(["POST"])
def location_maintenance_resolve_view(request: HttpRequest, location_id: int, issue_id: int | None = None) -> JsonResponse:
    return _resolve_maintenance(request, location_id, issue_id)


@require_permission(VIEW, VIEW_LOCATION)
def _list_locations(request: HttpRequest, property_id: int) -> JsonResponse:
    property_obj, error = _load_accessible_property(request, property_id)
    if error:
        return error
    try:
        queryset = prefetch_stay_cases(
            apply_occupancy_filter(filter_locations(locations_for_property(property_obj), request.GET), request.GET.get("occupancy"))
        )
    except LocationError as exc:
        return _handle_error(exc)
    return JsonResponse(
        {
            "resource": "locations",
            "property": {"id": property_obj.pk, "name": property_obj.name},
            "types": serialize_types(),
            "statuses": serialize_statuses(),
            "occupancies": serialize_occupancies(),
            "results": [serialize_location(item) for item in queryset],
        }
    )


@require_permission(CHANGE)
def _create_location(request: HttpRequest, property_id: int) -> JsonResponse:
    property_obj, error = _load_accessible_property(request, property_id)
    if error:
        return error
    try:
        payload = parse_json_body(request)
        location = create_location(property_obj, payload)
    except ValueError as exc:
        if isinstance(exc, LocationError):
            return _handle_error(exc)
        return json_error(str(exc), 400, code="invalid_json")
    return JsonResponse(_detail(location), status=201)


@require_permission(VIEW, VIEW_LOCATION)
def _retrieve_location(request: HttpRequest, location_id: int) -> JsonResponse:
    location, error = _load_accessible_location(request, location_id)
    if error:
        return error
    return JsonResponse(_detail(location))


@require_permission(CHANGE)
def _update_location(request: HttpRequest, location_id: int) -> JsonResponse:
    location, error = _load_accessible_location(request, location_id)
    if error:
        return error
    try:
        payload = parse_json_body(request)
        location = update_location(location, payload, actor=request.user)
    except ValueError as exc:
        if isinstance(exc, LocationError):
            return _handle_error(exc)
        return json_error(str(exc), 400, code="invalid_json")
    return JsonResponse(_detail(location))


@require_permission(CHANGE, STATUS)
def _deactivate_location(request: HttpRequest, location_id: int) -> JsonResponse:
    location, error = _load_accessible_location(request, location_id)
    if error:
        return error
    location = deactivate_location(location, actor=request.user)
    return JsonResponse(_detail(location))


@require_permission(CHANGE)
def _delete_location(request: HttpRequest, location_id: int) -> JsonResponse:
    location, error = _load_accessible_location(request, location_id)
    if error:
        return error
    try:
        delete_location(location)
    except LocationError as exc:
        return _handle_error(exc)
    return JsonResponse({"ok": True})


@require_permission(CHECK_IN)
def _check_in(request: HttpRequest, location_id: int) -> JsonResponse:
    location, error = _load_accessible_location(request, location_id)
    if error:
        return error
    try:
        payload = parse_json_body(request)
        case = _load_case(payload) or next_reservation(location)
        override = bool(payload.get("override"))
        if override and not _can_override(request):
            return json_error("You do not have permission to override check-in.", 403, code="permission_denied")
        check_in_location(location, case, actor=request.user, override=override)
    except LocationError as exc:
        return _handle_error(exc)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")
    except Case.DoesNotExist:
        return json_error("Reservation not found.", 400, code="invalid_reservation")
    return JsonResponse(_detail(location))


@require_permission(CHECK_OUT)
def _check_out(request: HttpRequest, location_id: int) -> JsonResponse:
    location, error = _load_accessible_location(request, location_id)
    if error:
        return error
    try:
        payload = parse_json_body(request)
        case = _load_case(payload)
        override = bool(payload.get("override"))
        if override and not _can_override(request) and not user_has_permission(request.user, "payments.verify_payment"):
            return json_error("You do not have permission to override an outstanding balance.", 403, code="permission_denied")
        check_out_location(location, case, actor=request.user, override=override)
    except LocationError as exc:
        return _handle_error(exc)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")
    except Case.DoesNotExist:
        return json_error("Stay not found.", 400, code="no_active_stay")
    return JsonResponse(_detail(location))


@require_permission(STATUS, CHANGE)
def _change_status(request: HttpRequest, location_id: int) -> JsonResponse:
    location, error = _load_accessible_location(request, location_id)
    if error:
        return error
    try:
        payload = parse_json_body(request)
        status = str(payload.get("status") or "").strip()
        reason = str(payload.get("reason") or "").strip()
        set_operational_status(location, status, actor=request.user, reason=reason)
    except LocationError as exc:
        return _handle_error(exc)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")
    return JsonResponse(_detail(location))


@require_permission(CLEANING)
def _start_cleaning(request: HttpRequest, location_id: int) -> JsonResponse:
    location, error = _load_accessible_location(request, location_id)
    if error:
        return error
    try:
        payload = parse_json_body(request)
        start_cleaning(
            location,
            actor=request.user,
            assigned_to=_optional_user(payload.get("assigned_to")),
            notes=str(payload.get("notes") or "").strip(),
        )
    except LocationError as exc:
        return _handle_error(exc)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")
    return JsonResponse(_detail(location))


@require_permission(CLEANING)
def _complete_cleaning(request: HttpRequest, location_id: int) -> JsonResponse:
    location, error = _load_accessible_location(request, location_id)
    if error:
        return error
    try:
        payload = parse_json_body(request)
        complete_cleaning(location, actor=request.user, notes=str(payload.get("notes") or "").strip())
    except LocationError as exc:
        return _handle_error(exc)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")
    return JsonResponse(_detail(location))


@require_permission(MAINTENANCE)
def _start_maintenance(request: HttpRequest, location_id: int) -> JsonResponse:
    location, error = _load_accessible_location(request, location_id)
    if error:
        return error
    try:
        payload = parse_json_body(request)
        start_maintenance(
            location,
            actor=request.user,
            title=str(payload.get("title") or "").strip(),
            description=str(payload.get("description") or "").strip(),
            priority=str(payload.get("priority") or "medium").strip(),
            assigned_to=_optional_user(payload.get("assigned_to")),
            expected_at=_optional_datetime(payload.get("expected_at")),
            out_of_order=bool(payload.get("out_of_order")),
        )
    except LocationError as exc:
        return _handle_error(exc)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")
    return JsonResponse(_detail(location))


@require_permission(MAINTENANCE)
def _resolve_maintenance(request: HttpRequest, location_id: int, issue_id: int | None = None) -> JsonResponse:
    location, error = _load_accessible_location(request, location_id)
    if error:
        return error
    try:
        payload = parse_json_body(request)
        issue = None
        selected_id = issue_id or payload.get("issue_id")
        if selected_id not in (None, ""):
            issue = MaintenanceIssue.objects.filter(pk=int(selected_id), location=location).first()
            if issue is None:
                raise LocationError("Maintenance issue not found.", code="no_maintenance")
        resolve_maintenance(location, issue, actor=request.user, notes=str(payload.get("notes") or "").strip())
    except LocationError as exc:
        return _handle_error(exc)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, LocationError):
            return _handle_error(exc)
        return json_error(str(exc), 400, code="invalid_json")
    return JsonResponse(_detail(location))
