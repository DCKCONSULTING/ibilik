from __future__ import annotations

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.http import enforce_property_query, json_error, parse_json_body, require_permission
from cases.access import accessible_cases, accessible_follow_ups, can_access_case, can_access_follow_up
from cases.models import Case, CaseFollowUp
from cases.permissions import (
    ADD_CASE,
    ADD_PIPELINE,
    CHANGE_CASE,
    CHANGE_PIPELINE,
    DELETE_CASE,
    DELETE_PIPELINE,
    VIEW_CASE,
    VIEW_PIPELINE,
)
from cases.serializers import (
    serialize_activity,
    serialize_case,
    serialize_follow_up,
    serialize_follow_up_sources,
    serialize_follow_up_types,
    serialize_pipeline_stages,
    serialize_user_summary,
)
from cases.calendar import list_calendar_events
from cases.services import (
    CaseError,
    cancel_follow_up,
    complete_follow_up,
    create_case,
    create_follow_up,
    create_global_follow_up,
    filter_cases,
    filter_follow_ups,
    follow_up_filter_properties,
    follow_up_filter_staff,
    follow_up_queryset,
    order_follow_ups,
    pipeline_summary,
    update_case,
    update_case_stage,
    update_follow_up,
)
from cases.workflow import perform_workflow_action
from crm.pagination import paginate_queryset


def _json(payload, *, status=200):
    return JsonResponse(payload, status=status, encoder=DjangoJSONEncoder)


def _case_queryset(*, detailed: bool = False):
    queryset = Case.objects.select_related(
        "customer",
        "property",
        "location",
        "assigned_to",
        "created_by",
        "originating_conversation",
    ).prefetch_related(
        "follow_ups__assigned_to",
        "conversations",
    )
    if detailed:
        queryset = queryset.prefetch_related("customer__identities", "activities__actor")
    return queryset


def _not_found():
    return json_error("Case not found.", 404, code="not_found")


def _forbidden():
    return json_error("You do not have access to this case.", 403, code="property_forbidden")


@require_http_methods(["GET"])
@require_permission("calendar.view_calendar")
@enforce_property_query
def calendar_events_view(request: HttpRequest) -> JsonResponse:
    try:
        return _json(list_calendar_events(request.user, request.GET))
    except CaseError as exc:
        return _handle_error(exc)


def _handle_error(exc: Exception) -> JsonResponse:
    if isinstance(exc, CaseError):
        status = 403 if exc.code == "property_forbidden" else 404 if exc.code == "not_found" else 400
        return json_error(str(exc), status, code=exc.code)
    if isinstance(exc, ValueError):
        return json_error(str(exc), 400, code="invalid_json")
    raise exc


@require_http_methods(["GET", "POST"])
def case_collection_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return _list_cases(request)
    return _create_case(request)


@require_http_methods(["GET", "PATCH", "DELETE"])
def case_detail_view(request: HttpRequest, case_id: int) -> JsonResponse:
    if request.method == "GET":
        return _retrieve_case(request, case_id)
    if request.method == "PATCH":
        return _update_case(request, case_id)
    return _delete_case(request, case_id)


@require_http_methods(["PATCH"])
def case_stage_view(request: HttpRequest, case_id: int) -> JsonResponse:
    return _change_stage(request, case_id)


@require_http_methods(["POST"])
def case_action_view(request: HttpRequest, case_id: int) -> JsonResponse:
    return _perform_action(request, case_id)


@require_http_methods(["GET", "POST"])
def follow_up_collection_view(request: HttpRequest, case_id: int) -> JsonResponse:
    if request.method == "GET":
        return _list_follow_ups(request, case_id)
    return _create_follow_up(request, case_id)


@require_http_methods(["GET", "PATCH", "DELETE"])
def follow_up_detail_view(request: HttpRequest, case_id: int, follow_up_id: int) -> JsonResponse:
    if request.method == "GET":
        return _retrieve_follow_up(request, case_id, follow_up_id)
    if request.method == "PATCH":
        return _update_follow_up(request, case_id, follow_up_id)
    return _delete_follow_up(request, case_id, follow_up_id)


@require_http_methods(["POST"])
def follow_up_complete_view(request: HttpRequest, case_id: int, follow_up_id: int) -> JsonResponse:
    return _complete_follow_up(request, case_id, follow_up_id)


@require_http_methods(["GET"])
def activity_collection_view(request: HttpRequest, case_id: int) -> JsonResponse:
    return _list_activities(request, case_id)


@require_permission(VIEW_CASE, VIEW_PIPELINE)
@enforce_property_query
def _list_cases(request: HttpRequest) -> JsonResponse:
    try:
        queryset = filter_cases(accessible_cases(request.user, _case_queryset()), request.GET)
    except CaseError as exc:
        return _handle_error(exc)
    summary = pipeline_summary(queryset)
    page = paginate_queryset(request, queryset.order_by("-updated_at", "-id"), default_size=100, max_size=200)
    resource = "cases" if request.path.startswith("/api/cases") else "pipeline"
    return _json(
        {
            "resource": resource,
            "count": page["count"],
            "page": page["page"],
            "page_size": page["page_size"],
            "has_next": page["has_next"],
            "stages": serialize_pipeline_stages(),
            "follow_up_types": serialize_follow_up_types(),
            "stage_counts": summary["stage_counts"],
            "total_value": summary["total_value"],
            "open_value": summary["open_value"],
            "results": [serialize_case(item) for item in page["results"]],
        }
    )


@require_permission(ADD_CASE, ADD_PIPELINE)
def _create_case(request: HttpRequest) -> JsonResponse:
    try:
        payload = parse_json_body(request)
        case = create_case(actor=request.user, payload=payload)
    except (ValueError, CaseError) as exc:
        return _handle_error(exc)
    return _json(serialize_case(_case_queryset().get(pk=case.pk)), status=201)


@require_permission(VIEW_CASE, VIEW_PIPELINE)
def _retrieve_case(request: HttpRequest, case_id: int) -> JsonResponse:
    case = _case_queryset(detailed=True).filter(pk=case_id).first()
    if case is None:
        return _not_found()
    if not can_access_case(request.user, case):
        return _forbidden()
    return _json(serialize_case(case, include_detail=True))


@require_permission(CHANGE_CASE, CHANGE_PIPELINE)
def _update_case(request: HttpRequest, case_id: int) -> JsonResponse:
    case = _case_queryset().filter(pk=case_id).first()
    if case is None:
        return _not_found()
    if not can_access_case(request.user, case):
        return _forbidden()
    try:
        payload = parse_json_body(request)
        case = update_case(case, payload, actor=request.user)
    except (ValueError, CaseError) as exc:
        return _handle_error(exc)
    return _json(serialize_case(_case_queryset(detailed=True).get(pk=case.pk), include_detail=True))


@require_permission(CHANGE_CASE, CHANGE_PIPELINE)
def _change_stage(request: HttpRequest, case_id: int) -> JsonResponse:
    case = _case_queryset().filter(pk=case_id).first()
    if case is None:
        return _not_found()
    if not can_access_case(request.user, case):
        return _forbidden()
    try:
        payload = parse_json_body(request)
        case = update_case_stage(case, payload.get("stage"))
    except (ValueError, CaseError) as exc:
        return _handle_error(exc)
    return _json(serialize_case(_case_queryset().get(pk=case.pk)))


@require_permission(CHANGE_CASE, CHANGE_PIPELINE)
def _perform_action(request: HttpRequest, case_id: int) -> JsonResponse:
    case = _case_queryset().filter(pk=case_id).first()
    if case is None:
        return _not_found()
    if not can_access_case(request.user, case):
        return _forbidden()
    try:
        payload = parse_json_body(request)
        case = perform_workflow_action(case, payload, actor=request.user)
    except (ValueError, CaseError) as exc:
        return _handle_error(exc)
    return _json(serialize_case(_case_queryset(detailed=True).get(pk=case.pk), include_detail=True))


@require_permission(DELETE_CASE, DELETE_PIPELINE)
def _delete_case(request: HttpRequest, case_id: int) -> JsonResponse:
    case = Case.objects.filter(pk=case_id).first()
    if case is None:
        return _not_found()
    if not can_access_case(request.user, case):
        return _forbidden()
    case.delete()
    return JsonResponse({"ok": True})


def _load_case(request: HttpRequest, case_id: int) -> Case | JsonResponse:
    case = _case_queryset().filter(pk=case_id).first()
    if case is None:
        return _not_found()
    if not can_access_case(request.user, case):
        return _forbidden()
    return case


@require_permission(VIEW_CASE, VIEW_PIPELINE)
def _list_follow_ups(request: HttpRequest, case_id: int) -> JsonResponse:
    case = _load_case(request, case_id)
    if isinstance(case, JsonResponse):
        return case
    items = accessible_follow_ups(request.user, case.follow_ups.select_related("assigned_to", "created_by"))
    return _json({"results": [serialize_follow_up(item) for item in items]})


@require_permission(CHANGE_CASE, CHANGE_PIPELINE)
def _create_follow_up(request: HttpRequest, case_id: int) -> JsonResponse:
    case = _load_case(request, case_id)
    if isinstance(case, JsonResponse):
        return case
    try:
        payload = parse_json_body(request)
        follow_up = create_follow_up(case, payload, actor=request.user)
    except (ValueError, CaseError) as exc:
        return _handle_error(exc)
    return _json(serialize_follow_up(follow_up), status=201)


@require_permission(VIEW_CASE, VIEW_PIPELINE)
def _retrieve_follow_up(request: HttpRequest, case_id: int, follow_up_id: int) -> JsonResponse:
    follow_up = CaseFollowUp.objects.select_related("case", "assigned_to").filter(pk=follow_up_id, case_id=case_id).first()
    if follow_up is None:
        return json_error("Follow-up not found.", 404, code="not_found")
    if not can_access_follow_up(request.user, follow_up):
        return _forbidden()
    return _json(serialize_follow_up(follow_up))


@require_permission(CHANGE_CASE, CHANGE_PIPELINE)
def _update_follow_up(request: HttpRequest, case_id: int, follow_up_id: int) -> JsonResponse:
    follow_up = CaseFollowUp.objects.select_related("case", "assigned_to").filter(pk=follow_up_id, case_id=case_id).first()
    if follow_up is None:
        return json_error("Follow-up not found.", 404, code="not_found")
    if not can_access_follow_up(request.user, follow_up):
        return _forbidden()
    try:
        payload = parse_json_body(request)
        follow_up = update_follow_up(follow_up, payload, actor=request.user)
    except (ValueError, CaseError) as exc:
        return _handle_error(exc)
    return _json(serialize_follow_up(follow_up))


@require_permission(CHANGE_CASE, CHANGE_PIPELINE)
def _complete_follow_up(request: HttpRequest, case_id: int, follow_up_id: int) -> JsonResponse:
    follow_up = CaseFollowUp.objects.select_related("case", "assigned_to").filter(pk=follow_up_id, case_id=case_id).first()
    if follow_up is None:
        return json_error("Follow-up not found.", 404, code="not_found")
    if not can_access_follow_up(request.user, follow_up):
        return _forbidden()
    follow_up = complete_follow_up(follow_up, actor=request.user)
    return _json(serialize_follow_up(follow_up))


@require_permission(CHANGE_CASE, CHANGE_PIPELINE)
def _delete_follow_up(request: HttpRequest, case_id: int, follow_up_id: int) -> JsonResponse:
    follow_up = CaseFollowUp.objects.select_related("case").filter(pk=follow_up_id, case_id=case_id).first()
    if follow_up is None:
        return json_error("Follow-up not found.", 404, code="not_found")
    if not can_access_follow_up(request.user, follow_up):
        return _forbidden()
    cancel_follow_up(follow_up, actor=request.user)
    return JsonResponse({"ok": True})


@require_permission(VIEW_CASE, VIEW_PIPELINE)
def _list_activities(request: HttpRequest, case_id: int) -> JsonResponse:
    case = _load_case(request, case_id)
    if isinstance(case, JsonResponse):
        return case
    return _json({"results": [serialize_activity(item) for item in case.activities.select_related("actor")[:80]]})


# Pipeline URL aliases keep existing clients working.
opportunity_collection_view = case_collection_view
opportunity_detail_view = case_detail_view
opportunity_stage_view = case_stage_view
opportunity_action_view = case_action_view


def _global_follow_up(follow_up_id: int):
    return follow_up_queryset().filter(pk=follow_up_id).first()


@require_http_methods(["GET", "POST"])
def global_follow_up_collection_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return _list_global_follow_ups(request)
    return _create_global_follow_up(request)


@require_http_methods(["GET", "PATCH", "DELETE"])
def global_follow_up_detail_view(request: HttpRequest, follow_up_id: int) -> JsonResponse:
    if request.method == "GET":
        return _retrieve_global_follow_up(request, follow_up_id)
    if request.method == "PATCH":
        return _update_global_follow_up(request, follow_up_id)
    return _cancel_global_follow_up(request, follow_up_id)


@require_http_methods(["POST"])
def global_follow_up_complete_view(request: HttpRequest, follow_up_id: int) -> JsonResponse:
    return _complete_global_follow_up(request, follow_up_id)


@require_permission(VIEW_CASE, VIEW_PIPELINE)
@enforce_property_query
def _list_global_follow_ups(request: HttpRequest) -> JsonResponse:
    try:
        queryset = order_follow_ups(
            filter_follow_ups(accessible_follow_ups(request.user, follow_up_queryset()), request.GET),
            request.GET,
        )
    except CaseError as exc:
        return _handle_error(exc)
    page = paginate_queryset(request, queryset, default_size=25, max_size=100)
    actionable_count = accessible_follow_ups(request.user).filter(status="pending").count()
    return _json(
        {
            "resource": "follow-ups",
            "count": page["count"],
            "page": page["page"],
            "page_size": page["page_size"],
            "has_next": page["has_next"],
            "actionable_count": actionable_count,
            "types": serialize_follow_up_types(),
            "stages": serialize_pipeline_stages(),
            "sources": serialize_follow_up_sources(),
            "staff": [serialize_user_summary(user) for user in follow_up_filter_staff(request.user)],
            "properties": [{"id": item.pk, "name": item.name} for item in follow_up_filter_properties(request.user)],
            "results": [serialize_follow_up(item, include_context=True) for item in page["results"]],
        }
    )


@require_permission(CHANGE_CASE, CHANGE_PIPELINE)
def _create_global_follow_up(request: HttpRequest) -> JsonResponse:
    try:
        payload = parse_json_body(request)
        follow_up = create_global_follow_up(actor=request.user, payload=payload)
    except (ValueError, CaseError) as exc:
        return _handle_error(exc)
    return _json(serialize_follow_up(follow_up_queryset().get(pk=follow_up.pk), include_context=True), status=201)


@require_permission(VIEW_CASE, VIEW_PIPELINE)
def _retrieve_global_follow_up(request: HttpRequest, follow_up_id: int) -> JsonResponse:
    follow_up = _global_follow_up(follow_up_id)
    if follow_up is None:
        return json_error("Follow-up not found.", 404, code="not_found")
    if not can_access_follow_up(request.user, follow_up):
        return _forbidden()
    return _json(serialize_follow_up(follow_up, include_context=True))


@require_permission(CHANGE_CASE, CHANGE_PIPELINE)
def _update_global_follow_up(request: HttpRequest, follow_up_id: int) -> JsonResponse:
    follow_up = _global_follow_up(follow_up_id)
    if follow_up is None:
        return json_error("Follow-up not found.", 404, code="not_found")
    if not can_access_follow_up(request.user, follow_up):
        return _forbidden()
    try:
        payload = parse_json_body(request)
        if "case_id" in payload:
            return json_error("The parent case cannot be changed from a follow-up.", 400, code="invalid_case")
        follow_up = update_follow_up(follow_up, payload, actor=request.user)
    except (ValueError, CaseError) as exc:
        return _handle_error(exc)
    return _json(serialize_follow_up(follow_up_queryset().get(pk=follow_up.pk), include_context=True))


@require_permission(CHANGE_CASE, CHANGE_PIPELINE)
def _complete_global_follow_up(request: HttpRequest, follow_up_id: int) -> JsonResponse:
    follow_up = _global_follow_up(follow_up_id)
    if follow_up is None:
        return json_error("Follow-up not found.", 404, code="not_found")
    if not can_access_follow_up(request.user, follow_up):
        return _forbidden()
    follow_up = complete_follow_up(follow_up, actor=request.user)
    return _json(serialize_follow_up(follow_up_queryset().get(pk=follow_up.pk), include_context=True))


@require_permission(CHANGE_CASE, CHANGE_PIPELINE)
def _cancel_global_follow_up(request: HttpRequest, follow_up_id: int) -> JsonResponse:
    follow_up = _global_follow_up(follow_up_id)
    if follow_up is None:
        return json_error("Follow-up not found.", 404, code="not_found")
    if not can_access_follow_up(request.user, follow_up):
        return _forbidden()
    cancel_follow_up(follow_up, actor=request.user)
    return JsonResponse({"ok": True})
