from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.authorization import user_has_permission
from accounts.http import json_error, parse_json_body, require_authenticated, require_permission
from accounts.models import Role, UserPropertyAccess
from accounts.roles import (
    can_assign_role,
    can_manage_target_user,
    create_role,
    deactivate_role,
    known_role_codes,
    update_role,
    visible_users,
)
from accounts.serializers import (
    serialize_app_sections,
    serialize_current_user,
    serialize_managed_user,
    serialize_permissions,
    serialize_role_record,
    serialize_roles,
)
from accounts.services import change_own_password, create_user, deactivate_own_account, update_user


def _user_queryset():
    return User.objects.all().prefetch_related(
        "groups",
        "assigned_properties",
        "property_staff_assignments__reports_to",
    ).select_related("property_access_profile")


GENERIC_LOGIN_ERROR = "Unable to sign in with the provided credentials."


@require_GET
@ensure_csrf_cookie
def csrf_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"csrfToken": get_token(request)})


@require_POST
@ensure_csrf_cookie
def login_view(request: HttpRequest) -> JsonResponse:
    try:
        payload = parse_json_body(request)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")

    username = str(payload.get("username") or "").strip()
    password = payload.get("password")

    if not username or not isinstance(password, str) or not password:
        return json_error(GENERIC_LOGIN_ERROR, 401, code="authentication_failed")

    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return json_error(GENERIC_LOGIN_ERROR, 401, code="authentication_failed")

    login(request, user)
    request.session.cycle_key()
    return JsonResponse({"user": serialize_current_user(user)})


@require_POST
@require_authenticated
def logout_view(request: HttpRequest) -> JsonResponse:
    logout(request)
    return JsonResponse({"ok": True})


@require_http_methods(["GET", "PATCH"])
@require_authenticated
def me_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return JsonResponse(serialize_current_user(request.user))
    return _update_me(request)


@require_POST
@require_authenticated
def me_password_view(request: HttpRequest) -> JsonResponse:
    try:
        payload = parse_json_body(request)
        change_own_password(
            request.user,
            current_password=str(payload.get("current_password") or ""),
            new_password=payload.get("password") if isinstance(payload.get("password"), str) else "",
        )
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_password")
    return JsonResponse({"ok": True})


@require_POST
@require_authenticated
def me_deactivate_view(request: HttpRequest) -> JsonResponse:
    try:
        deactivate_own_account(request.user)
    except PermissionError as exc:
        return json_error(str(exc), 403, code="permission_denied")
    logout(request)
    return JsonResponse({"ok": True})


def _update_me(request: HttpRequest) -> JsonResponse:
    try:
        payload = parse_json_body(request)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")

    if any(key in payload for key in ("role", "is_active", "property_access", "property_ids", "permissions", "individual_permissions", "is_superuser")):
        return json_error("You cannot change role, permissions, or access from account settings.", 403, code="permission_denied")

    email = payload.get("email")
    if email is not None and email != "" and "@" not in str(email):
        return json_error("Enter a valid email address.", 400, code="invalid_email")

    try:
        user = update_user(
            request.user,
            actor=request.user,
            first_name=payload.get("first_name"),
            last_name=payload.get("last_name"),
            email=payload.get("email"),
        )
    except (PermissionError, ValueError) as exc:
        status = 403 if isinstance(exc, PermissionError) else 400
        return json_error(str(exc), status, code="invalid_user")
    return JsonResponse(serialize_current_user(user))


@require_http_methods(["GET", "POST"])
def role_collection_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return _list_roles(request)
    return _create_role(request)


@require_http_methods(["GET", "PATCH", "DELETE"])
def role_detail_view(request: HttpRequest, role_code: str) -> JsonResponse:
    if request.method == "GET":
        return _retrieve_role(request, role_code)
    if request.method == "PATCH":
        return _update_role(request, role_code)
    return _delete_role(request, role_code)


@require_GET
@require_permission("users.view_user", "users.manage_roles", "properties.manage_staff")
def _list_roles(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"results": serialize_roles(actor=request.user), "sections": serialize_app_sections()})


@require_permission("users.manage_roles")
def _create_role(request: HttpRequest) -> JsonResponse:
    try:
        payload = parse_json_body(request)
        role = create_role(payload, actor=request.user)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_role")
    except PermissionError as exc:
        return json_error(str(exc), 403, code="permission_denied")
    return JsonResponse(serialize_role_record(role, actor=request.user), status=201)


def _load_role(role_code: str):
    role = Role.objects.filter(code=role_code).select_related("parent", "group").first()
    if role is None:
        return None, json_error("Role not found.", 404, code="not_found")
    return role, None


@require_GET
@require_permission("users.view_user", "users.manage_roles", "properties.manage_staff")
def _retrieve_role(request: HttpRequest, role_code: str) -> JsonResponse:
    role, error = _load_role(role_code)
    if error:
        return error
    return JsonResponse(serialize_role_record(role, actor=request.user))


@require_permission("users.manage_roles")
def _update_role(request: HttpRequest, role_code: str) -> JsonResponse:
    role, error = _load_role(role_code)
    if error:
        return error
    try:
        payload = parse_json_body(request)
        role = update_role(role, payload, actor=request.user)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_role")
    except PermissionError as exc:
        return json_error(str(exc), 403, code="permission_denied")
    return JsonResponse(serialize_role_record(role, actor=request.user))


@require_permission("users.manage_roles")
def _delete_role(request: HttpRequest, role_code: str) -> JsonResponse:
    role, error = _load_role(role_code)
    if error:
        return error
    try:
        deactivate_role(role, actor=request.user)
    except PermissionError as exc:
        return json_error(str(exc), 403, code="permission_denied")
    return JsonResponse({"ok": True})


@require_GET
@require_permission("users.view_user", "users.manage_permissions")
def permission_list_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"results": serialize_permissions(), "sections": serialize_app_sections()})


@require_http_methods(["GET", "POST"])
def user_collection_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return _list_users(request)
    return _create_user(request)


@require_http_methods(["GET", "PATCH"])
def user_detail_view(request: HttpRequest, user_id: int) -> JsonResponse:
    if request.method == "GET":
        return _retrieve_user(request, user_id)
    return _update_user(request, user_id)


@require_POST
@require_permission("users.manage_user")
def user_password_view(request: HttpRequest, user_id: int) -> JsonResponse:
    target = User.objects.filter(pk=user_id).first()
    if target is None:
        return json_error("User not found.", 404, code="not_found")

    try:
        payload = parse_json_body(request)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")

    password = payload.get("password")
    if not isinstance(password, str) or len(password) < 8:
        return json_error("Password must be at least 8 characters.", 400, code="invalid_password")

    try:
        update_user(target, actor=request.user, password=password)
    except PermissionError as exc:
        return json_error(str(exc), 403, code="permission_denied")

    return JsonResponse({"ok": True})


def _list_users(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return json_error("Authentication is required.", 401, code="unauthenticated")
    if not request.user.is_superuser and not user_has_permission(request.user, "users.view_user"):
        return json_error("You do not have permission to perform this action.", 403, code="permission_denied")

    users = visible_users(request.user, _user_queryset()).order_by("username")
    return JsonResponse({"results": [serialize_managed_user(user) for user in users]})


def _retrieve_user(request: HttpRequest, user_id: int) -> JsonResponse:
    if not request.user.is_authenticated:
        return json_error("Authentication is required.", 401, code="unauthenticated")
    if not request.user.is_superuser and not user_has_permission(request.user, "users.view_user"):
        return json_error("You do not have permission to perform this action.", 403, code="permission_denied")

    target = _user_queryset().filter(pk=user_id).first()
    if target is None:
        return json_error("User not found.", 404, code="not_found")
    return JsonResponse(serialize_managed_user(target))


def _create_user(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return json_error("Authentication is required.", 401, code="unauthenticated")
    if not request.user.is_superuser and not user_has_permission(request.user, "users.manage_user"):
        return json_error("You do not have permission to perform this action.", 403, code="permission_denied")

    try:
        payload = parse_json_body(request)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")

    error = _validate_user_payload(payload, creating=True)
    if error:
        return error

    if User.objects.filter(username__iexact=payload["username"]).exists():
        return json_error("A user with that username already exists.", 400, code="username_taken")

    requested_role = payload.get("role") or None
    if requested_role and not can_assign_role(request.user, requested_role):
        return json_error("You cannot assign that role.", 403, code="permission_denied")

    try:
        user = create_user(
            username=payload["username"],
            password=payload["password"],
            first_name=payload.get("first_name") or "",
            last_name=payload.get("last_name") or "",
            email=payload.get("email") or "",
            is_active=bool(payload.get("is_active", True)),
            role=payload.get("role") or None,
            property_access=payload.get("property_access"),
            property_ids=payload.get("property_ids"),
            reports_to_id=payload.get("reports_to_id"),
            actor=request.user,
        )
    except (PermissionError, ValueError) as exc:
        status = 403 if isinstance(exc, PermissionError) else 400
        return json_error(str(exc), status, code="invalid_user")

    return JsonResponse(serialize_managed_user(user), status=201)


def _update_user(request: HttpRequest, user_id: int) -> JsonResponse:
    if not request.user.is_authenticated:
        return json_error("Authentication is required.", 401, code="unauthenticated")
    target = _user_queryset().filter(pk=user_id).first()
    if target is None:
        return json_error("User not found.", 404, code="not_found")

    if not request.user.is_superuser:
        if target.pk != request.user.pk and not can_manage_target_user(request.user, target):
            return json_error("You do not have permission to perform this action.", 403, code="permission_denied")
        if target.pk == request.user.pk and not user_has_permission(request.user, "users.manage_user"):
            return json_error("You do not have permission to perform this action.", 403, code="permission_denied")

    try:
        payload = parse_json_body(request)
    except ValueError as exc:
        return json_error(str(exc), 400, code="invalid_json")

    error = _validate_user_payload(payload, creating=False)
    if error:
        return error

    if "role" in payload:
        if not can_assign_role(request.user, payload.get("role")):
            return json_error("You cannot assign that role.", 403, code="permission_denied")
        if target.pk != request.user.pk and not can_manage_target_user(request.user, target):
            return json_error("You cannot manage that user.", 403, code="permission_denied")

    try:
        update_kwargs = {
            "actor": request.user,
            "first_name": payload.get("first_name"),
            "last_name": payload.get("last_name"),
            "email": payload.get("email"),
            "is_active": payload.get("is_active"),
            "role": payload.get("role"),
            "password": payload.get("password"),
            "property_access": payload.get("property_access"),
            "property_ids": payload.get("property_ids"),
        }
        if "reports_to_id" in payload:
            update_kwargs["reports_to_id"] = payload.get("reports_to_id")
        user = update_user(target, **update_kwargs)
    except (PermissionError, ValueError) as exc:
        status = 403 if isinstance(exc, PermissionError) else 400
        return json_error(str(exc), status, code="invalid_user")

    user = _user_queryset().get(pk=user.pk)
    return JsonResponse(serialize_managed_user(user))


def _validate_user_payload(payload: dict, *, creating: bool) -> JsonResponse | None:
    if creating:
        username = str(payload.get("username") or "").strip()
        password = payload.get("password")
        if not username:
            return json_error("Username is required.", 400, code="invalid_username")
        if not isinstance(password, str) or len(password) < 8:
            return json_error("Password must be at least 8 characters.", 400, code="invalid_password")
        payload["username"] = username

    role = payload.get("role")
    if role is not None and role != "" and role not in known_role_codes():
        return json_error("Unknown role.", 400, code="invalid_role")

    rejected = _reject_direct_user_permissions(payload)
    if rejected:
        return rejected

    email = payload.get("email")
    if email is not None and email != "" and "@" not in str(email):
        return json_error("Enter a valid email address.", 400, code="invalid_email")

    property_access = payload.get("property_access")
    if property_access is not None and property_access not in UserPropertyAccess.Mode.values:
        return json_error("Unknown property access mode.", 400, code="invalid_property_access")

    property_ids = payload.get("property_ids")
    if property_ids is not None:
        if not isinstance(property_ids, list) or any(not isinstance(item, int) for item in property_ids):
            return json_error("Property IDs must be a list of integers.", 400, code="invalid_property_ids")

    if "reports_to_id" in payload:
        reports_to_id = payload.get("reports_to_id")
        if reports_to_id is not None and (isinstance(reports_to_id, bool) or not isinstance(reports_to_id, int)):
            return json_error("Reporting manager must be a user id.", 400, code="invalid_reports_to")

    return None


def _reject_direct_user_permissions(payload: dict) -> JsonResponse | None:
    for key in ("individual_permissions", "permissions"):
        value = payload.get(key)
        if value in (None, [], ()):
            continue
        return json_error(
            "Permissions cannot be assigned directly to a user. Assign a role instead.",
            400,
            code="user_permissions_not_allowed",
        )
    return None
