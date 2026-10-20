from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from accounts.http import json_error, require_permission
from accounts.property_excel import (
    ExcelImportError,
    commit_import,
    excel_http_response,
    export_locations_workbook,
    export_portfolio_workbook,
    export_properties_workbook,
    export_template_workbook,
    preview_import,
)

VIEW = "properties.view_property"
MUTATE = ("properties.add_property", "properties.change_property")


def _excel_error(exc: Exception) -> JsonResponse:
    if isinstance(exc, PermissionError):
        return json_error(str(exc), 403, code="property_forbidden")
    if isinstance(exc, ExcelImportError):
        status = 404 if exc.code == "not_found" else 400
        if exc.code == "import_invalid":
            status = 422
        return json_error(str(exc), status, code=exc.code)
    return json_error(str(exc), 400, code="invalid_excel")


def _mode(request: HttpRequest, default: str = "portfolio") -> str:
    return (request.POST.get("mode") or request.GET.get("mode") or default).strip().lower()


def _optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ExcelImportError("property_id must be a valid integer.", code="invalid_property") from exc


@require_GET
@require_permission(VIEW)
def properties_export_view(request: HttpRequest):
    try:
        content = export_properties_workbook(request.user)
    except Exception as exc:
        return _excel_error(exc)
    return excel_http_response(content, "properties_export.xlsx")


@require_GET
@require_permission(VIEW)
def locations_export_view(request: HttpRequest):
    try:
        property_id = _optional_int(request.GET.get("property_id"))
        content = export_locations_workbook(request.user, property_id=property_id)
    except Exception as exc:
        return _excel_error(exc)
    return excel_http_response(content, "locations_export.xlsx")


@require_GET
@require_permission(VIEW)
def portfolio_export_view(request: HttpRequest):
    try:
        property_id = _optional_int(request.GET.get("property_id"))
        content = export_portfolio_workbook(request.user, property_id=property_id)
    except Exception as exc:
        return _excel_error(exc)
    filename = "property_export.xlsx" if property_id else "portfolio_export.xlsx"
    return excel_http_response(content, filename)


@require_GET
@require_permission(VIEW)
def import_template_view(request: HttpRequest):
    return excel_http_response(export_template_workbook(), "properties_locations_import_template.xlsx")


@require_POST
@require_permission(*MUTATE)
def import_preview_view(request: HttpRequest):
    try:
        property_id = _optional_int(request.POST.get("property_id") or request.GET.get("property_id"))
        payload = preview_import(
            request.user,
            request.FILES.get("file"),
            mode=_mode(request),
            locked_property_id=property_id,
        )
    except Exception as exc:
        return _excel_error(exc)
    return JsonResponse(payload)


@require_POST
@require_permission(*MUTATE)
def import_commit_view(request: HttpRequest):
    try:
        property_id = _optional_int(request.POST.get("property_id") or request.GET.get("property_id"))
        payload = commit_import(
            request.user,
            request.FILES.get("file"),
            mode=_mode(request),
            locked_property_id=property_id,
        )
    except Exception as exc:
        return _excel_error(exc)
    return JsonResponse(payload)
