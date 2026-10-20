from __future__ import annotations

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.http import enforce_property_query, json_error, require_permission
from cases.serializers import serialize_user_summary
from crm.pagination import paginate_queryset

from bookings.access import can_access_booking
from bookings.errors import BookingError
from bookings.serializers import serialize_booking, serialize_stages, serialize_statuses
from bookings.services import (
    accessible_booking_queryset,
    booking_filter_locations,
    booking_filter_properties,
    booking_filter_staff,
    booking_queryset,
    filter_bookings,
    order_bookings,
)

VIEW = "bookings.view_booking"


def _json(payload, *, status=200):
    return JsonResponse(payload, status=status, encoder=DjangoJSONEncoder)


def _handle_error(exc: Exception) -> JsonResponse:
    if isinstance(exc, BookingError):
        return json_error(str(exc), 400, code=exc.code)
    raise exc


def _load_booking(user, booking_id: int):
    case = booking_queryset().filter(pk=booking_id, check_in__isnull=False).first()
    if case is None:
        return json_error("Booking not found.", 404, code="not_found")
    if not can_access_booking(user, case):
        return json_error("You do not have access to this booking.", 403, code="property_forbidden")
    return case


@require_http_methods(["GET"])
@require_permission(VIEW)
@enforce_property_query
def booking_collection_view(request: HttpRequest) -> JsonResponse:
    try:
        queryset = order_bookings(filter_bookings(accessible_booking_queryset(request.user), request.GET), request.GET)
    except BookingError as exc:
        return _handle_error(exc)
    page = paginate_queryset(request, queryset, default_size=25, max_size=100)
    return _json(
        {
            "resource": "bookings",
            "count": page["count"],
            "page": page["page"],
            "page_size": page["page_size"],
            "has_next": page["has_next"],
            "statuses": serialize_statuses(),
            "stages": serialize_stages(),
            "staff": [serialize_user_summary(user) for user in booking_filter_staff(request.user)],
            "properties": [{"id": item.pk, "name": item.name} for item in booking_filter_properties(request.user)],
            "locations": [
                {
                    "id": item.pk,
                    "name": item.name,
                    "code": item.code,
                    "type": item.location_type,
                    "type_label": item.get_location_type_display(),
                }
                for item in booking_filter_locations(request.user)
            ],
            "results": [serialize_booking(item) for item in page["results"]],
        }
    )


@require_http_methods(["GET"])
@require_permission(VIEW)
def booking_detail_view(request: HttpRequest, booking_id: int) -> JsonResponse:
    case = _load_booking(request.user, booking_id)
    if isinstance(case, JsonResponse):
        return case
    return _json(serialize_booking(case, include_detail=True))
