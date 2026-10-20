from __future__ import annotations

import json
from functools import wraps

from django.http import HttpRequest, JsonResponse

from accounts.authorization import user_has_permission


def json_error(message: str, status: int, *, code: str | None = None) -> JsonResponse:
    payload = {"message": message}
    if code:
        payload["code"] = code
    return JsonResponse(payload, status=status)


def parse_json_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JSON body.") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object.")
    return payload


def require_authenticated(view):
    @wraps(view)
    def wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return json_error("Authentication is required.", 401, code="unauthenticated")
        return view(request, *args, **kwargs)

    return wrapped


def enforce_property_query(view):
    @wraps(view)
    def wrapped(request: HttpRequest, *args, **kwargs):
        from accounts.scope import ScopeError, require_visible_property

        try:
            require_visible_property(request.user, request.GET.get("property"))
        except ScopeError as exc:
            return json_error(str(exc), exc.status, code=exc.code)
        return view(request, *args, **kwargs)

    return wrapped


def require_permission(*permissions: str):
    def decorator(view):
        @wraps(view)
        def wrapped(request: HttpRequest, *args, **kwargs):
            if not request.user.is_authenticated:
                return json_error("Authentication is required.", 401, code="unauthenticated")
            if request.user.is_superuser:
                return view(request, *args, **kwargs)
            if not any(user_has_permission(request.user, permission) for permission in permissions):
                return json_error(
                    "You do not have permission to perform this action.",
                    403,
                    code="permission_denied",
                )
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
