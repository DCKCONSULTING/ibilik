"""Permission-gated CRM resource endpoints.

These endpoints enforce authentication and authorization now so later
business features can reuse the same checks. They do not implement CRM
domain logic.
"""

from __future__ import annotations

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from accounts.http import enforce_property_query, json_error, require_permission


@require_GET
@require_permission("dashboard.view_dashboard")
@enforce_property_query
def dashboard_view(request: HttpRequest) -> JsonResponse:
    from accounts.dashboard import DashboardError, build_dashboard

    try:
        payload = build_dashboard(request.user, request.GET)
    except DashboardError as exc:
        return json_error(str(exc), getattr(exc, "status", 400), code=exc.code)
    return JsonResponse(payload, encoder=DjangoJSONEncoder)


@require_GET
@require_permission("availability.view_availability")
@enforce_property_query
def availability_view(request: HttpRequest) -> JsonResponse:
    from crm.pagination import paginate_queryset
    from locations.access import accessible_locations
    from locations.errors import LocationError
    from locations.serializers import serialize_location, serialize_occupancies, serialize_statuses, serialize_types
    from locations.services import (
        availability_filter_properties,
        availability_floors,
        filter_availability,
        prefetch_stay_cases,
    )

    queryset = accessible_locations(request.user).select_related("property")
    try:
        queryset = prefetch_stay_cases(filter_availability(queryset, request.GET))
    except LocationError as exc:
        return json_error(str(exc), 400, code=exc.code)
    page = paginate_queryset(request, queryset, default_size=50, max_size=200)
    return JsonResponse(
        {
            "resource": "availability",
            "count": page["count"],
            "page": page["page"],
            "page_size": page["page_size"],
            "has_next": page["has_next"],
            "types": serialize_types(),
            "statuses": serialize_statuses(),
            "occupancies": serialize_occupancies(),
            "properties": [{"id": item.pk, "name": item.name} for item in availability_filter_properties(request.user)],
            "floors": availability_floors(accessible_locations(request.user)),
            "results": [serialize_location(item) for item in page["results"]],
        },
        encoder=DjangoJSONEncoder,
    )


@require_GET
@require_permission("quotes.view_quote")
def quotes_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"resource": "quotes", "results": []})


@require_POST
@require_permission("quotes.approve_quote")
def quotes_approve_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"resource": "quotes", "approved": True})


@require_POST
@require_permission("bookings.cancel_booking")
def bookings_cancel_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"resource": "bookings", "cancelled": True})


@require_GET
@require_permission("payments.view_payment")
def payments_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"resource": "payments", "results": []})


@require_GET
@require_permission("calendar.view_calendar")
def calendar_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"resource": "calendar", "results": []})


@require_GET
@require_permission("reports.view_report")
def reports_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"resource": "reports", "results": []})


@require_GET
@require_permission("settings.change_setting")
def settings_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"resource": "settings", "results": []})
