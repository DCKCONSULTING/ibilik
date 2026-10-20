from __future__ import annotations

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.http import enforce_property_query, json_error, require_permission
from cases.serializers import serialize_user_summary
from crm.pagination import paginate_queryset
from quotes.access import can_access_quote
from quotes.errors import QuoteError
from quotes.models import Quote
from quotes.serializers import serialize_quote, serialize_statuses
from quotes.services import (
    accessible_quote_queryset,
    filter_quotes,
    order_quotes,
    quote_filter_properties,
    quote_filter_staff,
    quote_queryset,
)

VIEW = "quotes.view_quote"


def _json(payload, *, status=200):
    return JsonResponse(payload, status=status, encoder=DjangoJSONEncoder)


def _handle_error(exc: Exception) -> JsonResponse:
    if isinstance(exc, QuoteError):
        return json_error(str(exc), 400, code=exc.code)
    raise exc


def _load_quote(user, quote_id: int) -> Quote | JsonResponse:
    quote = quote_queryset().filter(pk=quote_id).first()
    if quote is None:
        return json_error("Quote not found.", 404, code="not_found")
    if not can_access_quote(user, quote):
        return json_error("You do not have access to this quotation.", 403, code="property_forbidden")
    return quote


@require_http_methods(["GET"])
@require_permission(VIEW)
@enforce_property_query
def quote_collection_view(request: HttpRequest) -> JsonResponse:
    try:
        queryset = order_quotes(filter_quotes(accessible_quote_queryset(request.user), request.GET), request.GET)
    except QuoteError as exc:
        return _handle_error(exc)
    page = paginate_queryset(request, queryset, default_size=25, max_size=100)
    return _json(
        {
            "resource": "quotes",
            "count": page["count"],
            "page": page["page"],
            "page_size": page["page_size"],
            "has_next": page["has_next"],
            "statuses": serialize_statuses(),
            "staff": [serialize_user_summary(user) for user in quote_filter_staff(request.user)],
            "properties": [{"id": item.pk, "name": item.name} for item in quote_filter_properties(request.user)],
            "results": [serialize_quote(item) for item in page["results"]],
        }
    )


@require_http_methods(["GET"])
@require_permission(VIEW)
def quote_detail_view(request: HttpRequest, quote_id: int) -> JsonResponse:
    quote = _load_quote(request.user, quote_id)
    if isinstance(quote, JsonResponse):
        return quote
    return _json(serialize_quote(quote, include_detail=True))
