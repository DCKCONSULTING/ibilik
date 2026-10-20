from __future__ import annotations

from django.db.models import Prefetch
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.authorization import can_access_property
from accounts.http import enforce_property_query, json_error, parse_json_body, require_permission
from accounts.models import Property
from crm.access import accessible_conversations, accessible_customers, can_access_conversation, can_access_customer
from crm.models import Conversation, Customer, Message
from crm.pagination import paginate_queryset
from crm.serializers import serialize_conversation, serialize_customer, serialize_message
from crm.services import (
    IngestError,
    create_customer,
    filter_conversations,
    filter_customers,
    mark_conversation_read,
    send_outbound_message,
    update_customer,
)


def _customer_queryset():
    return Customer.objects.select_related("property").prefetch_related(
        "identities",
        Prefetch("conversations", queryset=Conversation.objects.select_related("property")),
    )


def _conversation_queryset():
    return Conversation.objects.select_related("customer", "customer__property", "property").prefetch_related(
        "customer__identities",
        Prefetch("customer__conversations", queryset=Conversation.objects.select_related("property")),
    )


@require_http_methods(["GET", "POST"])
def customer_collection_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return _list_customers(request)
    return _create_customer(request)


@require_http_methods(["GET", "PATCH"])
def customer_detail_view(request: HttpRequest, customer_id: int) -> JsonResponse:
    if request.method == "GET":
        return _retrieve_customer(request, customer_id)
    return _update_customer(request, customer_id)


@require_permission("customers.view_customer")
@enforce_property_query
def _list_customers(request: HttpRequest) -> JsonResponse:
    try:
        queryset = filter_customers(accessible_customers(request.user, _customer_queryset()), request.GET)
    except IngestError as exc:
        return json_error(str(exc), 400, code=exc.code)
    page = paginate_queryset(request, queryset.order_by("-updated_at", "-id"))
    return JsonResponse(
        {
            "resource": "customers",
            "count": page["count"],
            "page": page["page"],
            "page_size": page["page_size"],
            "has_next": page["has_next"],
            "results": [serialize_customer(item) for item in page["results"]],
        }
    )


@require_permission("customers.add_customer")
def _create_customer(request: HttpRequest) -> JsonResponse:
    try:
        payload = parse_json_body(request)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")

    property_id = payload.get("property_id")
    if property_id not in (None, ""):
        try:
            property_obj = Property.objects.filter(pk=int(property_id)).first()
        except (TypeError, ValueError):
            return json_error("property_id must be an integer.", 400, code="invalid_property")
        if property_obj is None:
            return json_error("Unknown property.", 400, code="unknown_property")
        if not can_access_property(request.user, property_obj):
            return json_error("You do not have access to this property.", 403, code="property_forbidden")

    try:
        customer = create_customer(
            actor=request.user,
            name=payload.get("name"),
            email=payload.get("email") or "",
            phone=payload.get("phone") or "",
            status=payload.get("status") or "lead",
            notes=payload.get("notes") or "",
            property_id=property_id,
        )
    except IngestError as exc:
        return json_error(str(exc), 400, code=exc.code)
    return JsonResponse(serialize_customer(customer, include_timeline=True), status=201)


@require_permission("customers.view_customer")
def _retrieve_customer(request: HttpRequest, customer_id: int) -> JsonResponse:
    customer = _customer_queryset().filter(pk=customer_id).first()
    if customer is None:
        return json_error("Customer not found.", 404, code="not_found")
    if not can_access_customer(request.user, customer):
        return json_error("You do not have access to this customer.", 403, code="property_forbidden")
    return JsonResponse(serialize_customer(customer, include_timeline=True))


@require_permission("customers.change_customer")
def _update_customer(request: HttpRequest, customer_id: int) -> JsonResponse:
    customer = _customer_queryset().filter(pk=customer_id).first()
    if customer is None:
        return json_error("Customer not found.", 404, code="not_found")
    if not can_access_customer(request.user, customer):
        return json_error("You do not have access to this customer.", 403, code="property_forbidden")
    try:
        payload = parse_json_body(request)
        customer = update_customer(customer, payload)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")
    except IngestError as exc:
        return json_error(str(exc), 400, code=exc.code)
    return JsonResponse(serialize_customer(_customer_queryset().get(pk=customer.pk), include_timeline=True))


@require_http_methods(["GET"])
@require_permission("inbox.view_inbox")
@enforce_property_query
def conversation_collection_view(request: HttpRequest) -> JsonResponse:
    try:
        queryset = filter_conversations(accessible_conversations(request.user, _conversation_queryset()), request.GET)
    except IngestError as exc:
        return json_error(str(exc), 400, code=exc.code)
    page = paginate_queryset(request, queryset)
    return JsonResponse(
        {
            "resource": "conversations",
            "count": page["count"],
            "page": page["page"],
            "page_size": page["page_size"],
            "has_next": page["has_next"],
            "results": [serialize_conversation(item) for item in page["results"]],
        }
    )


@require_http_methods(["GET"])
@require_permission("inbox.view_inbox")
def conversation_detail_view(request: HttpRequest, conversation_id: int) -> JsonResponse:
    conversation = _conversation_queryset().filter(pk=conversation_id).first()
    if conversation is None:
        return json_error("Conversation not found.", 404, code="not_found")
    if not can_access_conversation(request.user, conversation):
        return json_error("You do not have access to this conversation.", 403, code="property_forbidden")
    mark_conversation_read(conversation)
    return JsonResponse(serialize_conversation(conversation))


@require_http_methods(["GET", "POST"])
def conversation_messages_view(request: HttpRequest, conversation_id: int) -> JsonResponse:
    if request.method == "GET":
        return _list_messages(request, conversation_id)
    return _create_message(request, conversation_id)


@require_permission("inbox.view_inbox")
def _list_messages(request: HttpRequest, conversation_id: int) -> JsonResponse:
    conversation = Conversation.objects.filter(pk=conversation_id).first()
    if conversation is None:
        return json_error("Conversation not found.", 404, code="not_found")
    if not can_access_conversation(request.user, conversation):
        return json_error("You do not have access to this conversation.", 403, code="property_forbidden")

    queryset = Message.objects.filter(conversation=conversation).order_by("-created_at", "-id")
    channel = request.GET.get("channel")
    if channel:
        queryset = queryset.filter(channel=channel)
    page = paginate_queryset(request, queryset, default_size=50)
    page["results"] = list(reversed(page["results"]))
    mark_conversation_read(conversation)
    return JsonResponse(
        {
            "resource": "messages",
            "conversation_id": conversation.pk,
            "count": page["count"],
            "page": page["page"],
            "page_size": page["page_size"],
            "has_next": page["has_next"],
            "results": [serialize_message(item) for item in page["results"]],
        }
    )


@require_permission("inbox.send_message")
def _create_message(request: HttpRequest, conversation_id: int) -> JsonResponse:
    conversation = _conversation_queryset().filter(pk=conversation_id).first()
    if conversation is None:
        return json_error("Conversation not found.", 404, code="not_found")
    if not can_access_conversation(request.user, conversation):
        return json_error("You do not have access to this conversation.", 403, code="property_forbidden")
    try:
        payload = parse_json_body(request)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")
    try:
        message = send_outbound_message(
            conversation=conversation,
            actor=request.user,
            content=payload.get("content") or payload.get("message") or "",
            channel=str(payload.get("channel") or conversation.channel),
        )
    except IngestError as exc:
        status = 403 if exc.code in {"channel_unavailable", "property_forbidden"} else 400
        return json_error(str(exc), status, code=exc.code)
    return JsonResponse(serialize_message(message), status=201)


@require_http_methods(["POST"])
@require_permission("inbox.view_inbox")
def conversation_read_view(request: HttpRequest, conversation_id: int) -> JsonResponse:
    conversation = _conversation_queryset().filter(pk=conversation_id).first()
    if conversation is None:
        return json_error("Conversation not found.", 404, code="not_found")
    if not can_access_conversation(request.user, conversation):
        return json_error("You do not have access to this conversation.", 403, code="property_forbidden")
    mark_conversation_read(conversation)
    return JsonResponse(serialize_conversation(conversation))
