from __future__ import annotations

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.http import enforce_property_query, json_error, parse_json_body, require_permission
from crm.pagination import paginate_queryset
from match.access import accessible_requests, can_access_request
from match.errors import MatchError
from match.models import MatchRequest
from match.assignment import assign_request_automatically, get_match_settings, staff_workload_rows
from match.permissions import ASSIGN, VIEW_MATCH
from match.serializers import (
    serialize_priorities,
    serialize_request,
    serialize_settings,
    serialize_staff_option,
    serialize_statuses,
    serialize_types,
    serialize_workload_row,
)
from match.services import (
    add_note,
    assign_request,
    assignable_staff,
    create_request,
    delete_request,
    filter_properties,
    filter_requests,
    filter_staff,
    order_requests,
    reassign_request,
    request_queryset,
    request_summary,
    unassign_request,
    update_match_settings,
    update_request,
)


def _json(payload, *, status=200):
    return JsonResponse(payload, status=status, encoder=DjangoJSONEncoder)


def _handle_error(exc: Exception) -> JsonResponse:
    if isinstance(exc, MatchError):
        status = 403 if exc.code in {"permission_denied", "assignment_forbidden", "property_forbidden"} else 400
        return json_error(str(exc), status, code=exc.code)
    if isinstance(exc, ValueError):
        return json_error(str(exc), 400, code="invalid_payload")
    raise exc


def _load_request(user, request_id: int, *, detailed: bool = False) -> MatchRequest | JsonResponse:
    queryset = request_queryset()
    if detailed:
        queryset = queryset.prefetch_related("notes__created_by", "history__actor")
    item = queryset.filter(pk=request_id).first()
    if item is None:
        return json_error("Request not found.", 404, code="not_found")
    if not can_access_request(user, item):
        return json_error("You do not have access to this request.", 403, code="property_forbidden")
    return item


def _list_payload(request: HttpRequest, queryset):
    scoped = accessible_requests(request.user, queryset)
    filtered = order_requests(filter_requests(scoped, request.GET), request.GET)
    page = paginate_queryset(request, filtered, default_size=25, max_size=100)
    summary = request_summary(scoped)
    return {
        "resource": "match-requests",
        "count": page["count"],
        "page": page["page"],
        "page_size": page["page_size"],
        "has_next": page["has_next"],
        "summary": summary,
        "new_unassigned_count": summary["new_unassigned_count"],
        "statuses": serialize_statuses(),
        "types": serialize_types(),
        "priorities": serialize_priorities(),
        "staff": [serialize_staff_option(user) for user in filter_staff(request.user)],
        "properties": [{"id": item.pk, "name": item.name} for item in filter_properties(request.user)],
        "results": [serialize_request(item) for item in page["results"]],
    }


@require_http_methods(["GET", "POST"])
@require_permission(VIEW_MATCH)
@enforce_property_query
def request_collection_view(request: HttpRequest) -> JsonResponse:
    if request.method == "POST":
        try:
            payload = parse_json_body(request)
            item = create_request(actor=request.user, payload=payload)
        except (MatchError, ValueError) as exc:
            return _handle_error(exc)
        return _json(serialize_request(item, include_detail=True), status=201)
    try:
        return _json(_list_payload(request, request_queryset()))
    except (MatchError, ValueError) as exc:
        return _handle_error(exc)


@require_http_methods(["GET"])
@require_permission(VIEW_MATCH)
def request_summary_view(request: HttpRequest) -> JsonResponse:
    scoped = accessible_requests(request.user, request_queryset())
    summary = request_summary(scoped)
    return _json({"resource": "match-summary", **summary})


@require_http_methods(["GET", "PATCH", "DELETE"])
@require_permission(VIEW_MATCH)
def request_detail_view(request: HttpRequest, request_id: int) -> JsonResponse:
    item = _load_request(request.user, request_id, detailed=True)
    if isinstance(item, JsonResponse):
        return item
    if request.method == "GET":
        payload = serialize_request(item, include_detail=True)
        payload["assignable_staff"] = [serialize_staff_option(user) for user in assignable_staff(request.user, request=item)]
        return _json(payload)
    if request.method == "DELETE":
        try:
            delete_request(item, actor=request.user)
        except MatchError as exc:
            return _handle_error(exc)
        return _json({"ok": True})
    try:
        payload = parse_json_body(request)
        item = update_request(item, payload, actor=request.user)
    except (MatchError, ValueError) as exc:
        return _handle_error(exc)
    item = request_queryset().prefetch_related("notes__created_by", "history__actor").get(pk=item.pk)
    return _json(serialize_request(item, include_detail=True))


@require_http_methods(["POST"])
@require_permission(VIEW_MATCH)
def request_assign_view(request: HttpRequest, request_id: int) -> JsonResponse:
    item = _load_request(request.user, request_id, detailed=True)
    if isinstance(item, JsonResponse):
        return item
    try:
        payload = parse_json_body(request)
        item = assign_request(item, actor=request.user, assigned_to_id=payload.get("assigned_to_id"))
    except (MatchError, ValueError) as exc:
        return _handle_error(exc)
    item = request_queryset().prefetch_related("notes__created_by", "history__actor").get(pk=item.pk)
    return _json(serialize_request(item, include_detail=True))


@require_http_methods(["POST"])
@require_permission(VIEW_MATCH)
def request_reassign_view(request: HttpRequest, request_id: int) -> JsonResponse:
    item = _load_request(request.user, request_id, detailed=True)
    if isinstance(item, JsonResponse):
        return item
    try:
        payload = parse_json_body(request)
        item = reassign_request(item, actor=request.user, assigned_to_id=payload.get("assigned_to_id"))
    except (MatchError, ValueError) as exc:
        return _handle_error(exc)
    item = request_queryset().prefetch_related("notes__created_by", "history__actor").get(pk=item.pk)
    return _json(serialize_request(item, include_detail=True))


@require_http_methods(["POST"])
@require_permission(VIEW_MATCH)
def request_unassign_view(request: HttpRequest, request_id: int) -> JsonResponse:
    item = _load_request(request.user, request_id, detailed=True)
    if isinstance(item, JsonResponse):
        return item
    try:
        item = unassign_request(item, actor=request.user)
    except MatchError as exc:
        return _handle_error(exc)
    item = request_queryset().prefetch_related("notes__created_by", "history__actor").get(pk=item.pk)
    return _json(serialize_request(item, include_detail=True))


@require_http_methods(["POST"])
@require_permission(VIEW_MATCH)
def request_notes_view(request: HttpRequest, request_id: int) -> JsonResponse:
    item = _load_request(request.user, request_id, detailed=True)
    if isinstance(item, JsonResponse):
        return item
    try:
        payload = parse_json_body(request)
        add_note(item, payload.get("note") or payload.get("body") or "", actor=request.user)
    except (MatchError, ValueError) as exc:
        return _handle_error(exc)
    item = request_queryset().prefetch_related("notes__created_by", "history__actor").get(pk=item.pk)
    return _json(serialize_request(item, include_detail=True))


@require_http_methods(["GET"])
@require_permission(VIEW_MATCH)
def request_history_view(request: HttpRequest, request_id: int) -> JsonResponse:
    item = _load_request(request.user, request_id, detailed=True)
    if isinstance(item, JsonResponse):
        return item
    from match.serializers import serialize_history

    return _json(
        {
            "resource": "match-history",
            "count": item.history.count(),
            "results": [serialize_history(entry) for entry in item.history.select_related("actor")],
        }
    )


@require_http_methods(["POST"])
@require_permission(VIEW_MATCH)
def request_auto_assign_view(request: HttpRequest, request_id: int) -> JsonResponse:
    from accounts.authorization import is_superuser, user_has_permission

    if not (is_superuser(request.user) or user_has_permission(request.user, ASSIGN)):
        return json_error("You do not have permission to perform this action.", 403, code="permission_denied")
    item = _load_request(request.user, request_id, detailed=True)
    if isinstance(item, JsonResponse):
        return item
    try:
        item = assign_request_automatically(item, force=True, actor=request.user)
    except MatchError as exc:
        return _handle_error(exc)
    item = request_queryset().prefetch_related("notes__created_by", "history__actor").get(pk=item.pk)
    return _json(serialize_request(item, include_detail=True))


@require_http_methods(["GET"])
@require_permission(VIEW_MATCH)
def staff_workload_view(request: HttpRequest) -> JsonResponse:
    from accounts.authorization import can_access_property
    from accounts.models import Property

    property_obj = None
    property_id = request.GET.get("property")
    if property_id not in (None, "", "all"):
        try:
            property_obj = Property.objects.filter(pk=int(property_id)).first()
        except (TypeError, ValueError):
            return json_error("property must be an integer.", 400, code="invalid_property")
        if property_obj is None:
            return json_error("Unknown property.", 404, code="unknown_property")
        if not can_access_property(request.user, property_obj):
            return json_error("You do not have access to this property.", 403, code="property_forbidden")
    rows = staff_workload_rows(property_obj=property_obj)
    return _json(
        {
            "resource": "match-staff-workload",
            "count": len(rows),
            "property": None if property_obj is None else {"id": property_obj.pk, "name": property_obj.name},
            "results": [serialize_workload_row(row) for row in rows],
        }
    )


@require_http_methods(["GET", "PATCH"])
@require_permission(VIEW_MATCH)
def match_settings_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return _json({"resource": "match-settings", **serialize_settings(get_match_settings())})
    try:
        payload = parse_json_body(request)
        settings = update_match_settings(actor=request.user, payload=payload)
    except (MatchError, ValueError) as exc:
        return _handle_error(exc)
    return _json({"resource": "match-settings", **serialize_settings(settings)})
