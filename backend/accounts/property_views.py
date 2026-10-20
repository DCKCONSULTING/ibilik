from __future__ import annotations

from django.contrib.auth.models import User
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.http import json_error, parse_json_body, require_permission
from accounts.property_services import (
    assign_property_staff,
    create_property,
    get_accessible_property,
    properties_for_user,
    remove_property_staff,
    update_property,
)
from accounts.property_staff import (
    build_staff_hierarchy,
    catalog_roles,
    serialize_property_staff_collection,
    update_property_staff,
)
from accounts.serializers import serialize_property


@require_http_methods(["GET", "POST"])
def property_collection_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return _list_properties(request)
    return _create_property(request)


@require_http_methods(["GET", "PATCH"])
def property_detail_view(request: HttpRequest, property_id: int) -> JsonResponse:
    if request.method == "GET":
        return _retrieve_property(request, property_id)
    return _update_property(request, property_id)


@require_http_methods(["GET", "POST"])
def property_staff_collection_view(request: HttpRequest, property_id: int) -> JsonResponse:
    if request.method == "GET":
        return _list_property_staff(request, property_id)
    return _assign_property_staff(request, property_id)


@require_http_methods(["GET", "PATCH", "DELETE"])
def property_staff_detail_view(request: HttpRequest, property_id: int, user_id: int) -> JsonResponse:
    if request.method == "GET":
        return _retrieve_property_staff(request, property_id, user_id)
    if request.method == "PATCH":
        return _update_property_staff(request, property_id, user_id)
    return _remove_property_staff(request, property_id, user_id)


@require_permission("properties.view_property")
def _list_properties(request: HttpRequest) -> JsonResponse:
    properties = properties_for_user(request.user)
    return JsonResponse(
        {
            "resource": "properties",
            "results": [serialize_property(item) for item in properties],
        }
    )


@require_permission("properties.add_property")
def _create_property(request: HttpRequest) -> JsonResponse:
    try:
        payload = parse_json_body(request)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")

    try:
        extra = {
            key: payload[key]
            for key in payload
            if key not in {"name", "region", "city", "rate"}
        }
        property_obj = create_property(
            actor=request.user,
            name=payload.get("name"),
            region=payload.get("region"),
            city=payload.get("city"),
            rate=payload.get("rate", payload.get("base_rate")),
            **extra,
        )
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_property")

    return JsonResponse(serialize_property(property_obj, include_staff=True), status=201)


def _load_accessible_property(request: HttpRequest, property_id: int):
    try:
        property_obj = get_accessible_property(request.user, property_id)
    except PermissionError as exc:
        return None, json_error(str(exc), 403, code="property_forbidden")
    if property_obj is None:
        return None, json_error("Property not found.", 404, code="not_found")
    return property_obj, None


@require_permission("properties.view_property")
def _retrieve_property(request: HttpRequest, property_id: int) -> JsonResponse:
    property_obj, error = _load_accessible_property(request, property_id)
    if error:
        return error
    return JsonResponse(serialize_property(property_obj, include_staff=True, include_summary=True))


@require_permission("properties.change_property")
def _update_property(request: HttpRequest, property_id: int) -> JsonResponse:
    property_obj, error = _load_accessible_property(request, property_id)
    if error:
        return error

    try:
        payload = parse_json_body(request)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")

    try:
        property_obj = update_property(property_obj, payload)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_property")

    return JsonResponse(serialize_property(property_obj, include_staff=True, include_summary=True))


def _staff_payload(property_obj):
    results = serialize_property_staff_collection(property_obj)
    return {
        "results": results,
        "roles": catalog_roles(),
        "hierarchy": build_staff_hierarchy(results),
    }


@require_permission("properties.view_property")
def _list_property_staff(request: HttpRequest, property_id: int) -> JsonResponse:
    property_obj, error = _load_accessible_property(request, property_id)
    if error:
        return error
    return JsonResponse(_staff_payload(property_obj))


@require_permission("properties.manage_staff")
def _assign_property_staff(request: HttpRequest, property_id: int) -> JsonResponse:
    property_obj, error = _load_accessible_property(request, property_id)
    if error:
        return error

    try:
        payload = parse_json_body(request)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")

    user_id = payload.get("user_id")
    if not isinstance(user_id, int):
        return json_error("A valid user_id is required.", 400, code="invalid_user")

    target = User.objects.filter(pk=user_id).first()
    if target is None:
        return json_error("User not found.", 404, code="not_found")

    try:
        assign_property_staff(
            property_obj,
            target,
            role=payload.get("role"),
            reports_to_id=payload.get("reports_to_id"),
            actor=request.user,
        )
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_staff")
    return JsonResponse({"ok": True, **_staff_payload(property_obj)}, status=201)


def _load_assigned_staff_user(property_obj, user_id: int):
    target = User.objects.filter(pk=user_id).first()
    if target is None:
        return None, json_error("User not found.", 404, code="not_found")
    if not property_obj.staff.filter(pk=target.pk).exists():
        return None, json_error("This user is not assigned to the property.", 404, code="not_found")
    return target, None


@require_permission("properties.view_property")
def _retrieve_property_staff(request: HttpRequest, property_id: int, user_id: int) -> JsonResponse:
    property_obj, error = _load_accessible_property(request, property_id)
    if error:
        return error
    target, error = _load_assigned_staff_user(property_obj, user_id)
    if error:
        return error
    results = serialize_property_staff_collection(property_obj)
    member = next((item for item in results if item["id"] == target.pk), None)
    return JsonResponse(member)


@require_permission("properties.manage_staff")
def _update_property_staff(request: HttpRequest, property_id: int, user_id: int) -> JsonResponse:
    property_obj, error = _load_accessible_property(request, property_id)
    if error:
        return error
    target, error = _load_assigned_staff_user(property_obj, user_id)
    if error:
        return error
    try:
        payload = parse_json_body(request)
        update_property_staff(property_obj, target, payload, actor=request.user)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_staff")
    return JsonResponse({"ok": True, **_staff_payload(property_obj)})


@require_permission("properties.manage_staff")
def _remove_property_staff(request: HttpRequest, property_id: int, user_id: int) -> JsonResponse:
    property_obj, error = _load_accessible_property(request, property_id)
    if error:
        return error

    target = User.objects.filter(pk=user_id).first()
    if target is None:
        return json_error("User not found.", 404, code="not_found")

    remove_property_staff(property_obj, target)
    return JsonResponse({"ok": True})
