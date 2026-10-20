from __future__ import annotations

import hashlib
import hmac

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

from accounts.http import json_error


def _header(request: HttpRequest, name: str) -> str:
    return request.headers.get(name) or request.META.get(f"HTTP_{name.upper().replace('-', '_')}", "") or ""


def require_ingest_api_key(request: HttpRequest, *, setting_name: str = "WEBSITE_INGEST_API_KEY") -> JsonResponse | None:
    expected = getattr(settings, setting_name, "") or ""
    provided = _header(request, "X-API-Key") or _header(request, "Authorization").removeprefix("Bearer ").strip()
    if not expected:
        return json_error("Ingest API key is not configured.", 503, code="ingest_not_configured")
    if not provided or not hmac.compare_digest(provided, expected):
        return json_error("Invalid ingest credentials.", 401, code="invalid_api_key")
    return None


def verify_meta_signature(request: HttpRequest, secret: str) -> bool:
    if not secret:
        return False
    header = _header(request, "X-Hub-Signature-256")
    if not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:], expected)


def meta_subscribe_response(request: HttpRequest, verify_token: str) -> HttpResponse | JsonResponse:
    mode = request.GET.get("hub.mode") or request.GET.get("hub_mode")
    token = request.GET.get("hub.verify_token") or request.GET.get("hub_verify_token")
    challenge = request.GET.get("hub.challenge") or request.GET.get("hub_challenge")
    if mode != "subscribe":
        return json_error("Invalid webhook verification request.", 403, code="invalid_verify")
    if not verify_token or token != verify_token:
        return json_error("Webhook verify token rejected.", 403, code="invalid_verify_token")
    return HttpResponse(challenge or "", content_type="text/plain")


def sign_payload(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
