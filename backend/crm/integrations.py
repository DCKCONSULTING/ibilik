from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from accounts.http import json_error, parse_json_body
from crm.parsers import parse_normalized_facebook, parse_normalized_whatsapp, parse_website_payload
from crm.security import meta_subscribe_response, require_ingest_api_key, verify_meta_signature
from crm.serializers import serialize_ingest_result
from crm.services import IngestError, ingest_inbound_message


def _ingest_many(events: list[dict]) -> tuple[list[dict], bool]:
    results = []
    any_new = False
    for event in events:
        message, deduplicated = ingest_inbound_message(**event)
        results.append(serialize_ingest_result(message, deduplicated=deduplicated))
        if not deduplicated:
            any_new = True
    return results, any_new


@csrf_exempt
@require_http_methods(["POST"])
def website_messages_view(request: HttpRequest) -> JsonResponse:
    auth_error = require_ingest_api_key(request, setting_name="WEBSITE_INGEST_API_KEY")
    if auth_error:
        return auth_error
    try:
        payload = parse_json_body(request)
        event = parse_website_payload(payload)
        message, deduplicated = ingest_inbound_message(**event)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_payload")
    except IngestError as exc:
        return json_error(str(exc), 400, code=exc.code)
    return JsonResponse(serialize_ingest_result(message, deduplicated=deduplicated), status=200 if deduplicated else 201)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook_view(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        return meta_subscribe_response(request, settings.WHATSAPP_VERIFY_TOKEN)
    if not verify_meta_signature(request, settings.WHATSAPP_APP_SECRET):
        return json_error("Invalid WhatsApp webhook signature.", 403, code="invalid_signature")
    try:
        payload = parse_json_body(request)
        events = parse_normalized_whatsapp(payload)
        if not events:
            return JsonResponse({"ok": True, "results": []})
        results, any_new = _ingest_many(events)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_payload")
    except IngestError as exc:
        return json_error(str(exc), 400, code=exc.code)
    return JsonResponse({"ok": True, "results": results}, status=200 if not any_new else 201)


@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_messages_view(request: HttpRequest) -> JsonResponse:
    auth_error = require_ingest_api_key(request, setting_name="WHATSAPP_INGEST_API_KEY")
    if auth_error:
        return auth_error
    try:
        payload = parse_json_body(request)
        events = parse_normalized_whatsapp(payload)
        if not events:
            return json_error("No WhatsApp messages were found in the payload.", 400, code="invalid_payload")
        results, any_new = _ingest_many(events)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_payload")
    except IngestError as exc:
        return json_error(str(exc), 400, code=exc.code)
    body = results[0] if len(results) == 1 else {"results": results}
    return JsonResponse(body, status=200 if not any_new else 201)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def facebook_webhook_view(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        return meta_subscribe_response(request, settings.FACEBOOK_VERIFY_TOKEN)
    if not verify_meta_signature(request, settings.FACEBOOK_APP_SECRET):
        return json_error("Invalid Facebook webhook signature.", 403, code="invalid_signature")
    try:
        payload = parse_json_body(request)
        events = parse_normalized_facebook(payload)
        if not events:
            return JsonResponse({"ok": True, "results": []})
        results, any_new = _ingest_many(events)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_payload")
    except IngestError as exc:
        return json_error(str(exc), 400, code=exc.code)
    return JsonResponse({"ok": True, "results": results}, status=200 if not any_new else 201)


@csrf_exempt
@require_http_methods(["POST"])
def facebook_messages_view(request: HttpRequest) -> JsonResponse:
    auth_error = require_ingest_api_key(request, setting_name="FACEBOOK_INGEST_API_KEY")
    if auth_error:
        return auth_error
    try:
        payload = parse_json_body(request)
        events = parse_normalized_facebook(payload)
        if not events:
            return json_error("No Facebook messages were found in the payload.", 400, code="invalid_payload")
        results, any_new = _ingest_many(events)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_payload")
    except IngestError as exc:
        return json_error(str(exc), 400, code=exc.code)
    body = results[0] if len(results) == 1 else {"results": results}
    return JsonResponse(body, status=200 if not any_new else 201)
