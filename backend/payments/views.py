from __future__ import annotations

from django.core.serializers.json import DjangoJSONEncoder
from django.http import FileResponse, HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.http import enforce_property_query, json_error, parse_json_body, require_permission
from cases.access import can_access_case
from cases.models import Case
from cases.serializers import serialize_follow_up_sources, serialize_pipeline_stages, serialize_user_summary
from crm.pagination import paginate_queryset
from payments.access import accessible_payments, accessible_refunds, can_access_payment, can_access_refund
from payments.errors import PaymentError
from payments.ledger import create_case_charge, void_case_charge
from payments.models import CaseCharge, ChargeKind, Payment, PaymentAttachment, PaymentRefund
from payments.serializers import (
    format_money,
    serialize_attachment,
    serialize_balance,
    serialize_balance_labels,
    serialize_charge,
    serialize_charge_categories,
    serialize_charge_kinds,
    serialize_methods,
    serialize_payment,
    serialize_refund,
    serialize_statuses,
    serialize_types,
)
from payments.services import (
    add_attachment,
    approve_payment,
    approve_refund,
    cancel_payment,
    case_balance,
    complete_refund,
    create_payment,
    filter_payments,
    order_payments,
    payment_filter_properties,
    payment_filter_staff,
    payment_queryset,
    payment_summary,
    reject_payment,
    reject_refund,
    request_refund,
    send_payment_reminder,
    submit_payment,
    update_payment,
)

VIEW = "payments.view_payment"
CREATE = "payments.create_payment"
CHANGE = "payments.change_payment"
APPROVE = "payments.verify_payment"
REJECT = "payments.reject_payment"
REQUEST_REFUND = "payments.request_refund"
MANAGE_REFUND = "payments.refund_payment"
REMIND = "payments.send_reminder"
ADD_CHARGE = "payments.add_charge"
ADD_PENALTY = "payments.add_penalty"
VOID_CHARGE = "payments.void_charge"


def _json(payload, *, status=200):
    return JsonResponse(payload, status=status, encoder=DjangoJSONEncoder)


def _handle_error(exc: Exception) -> JsonResponse:
    if isinstance(exc, PaymentError):
        status = 403 if exc.code in {"property_forbidden", "channel_unavailable"} else 404 if exc.code == "not_found" else 400
        if exc.code == "reminder_failed":
            status = 502
        return json_error(str(exc), status, code=exc.code)
    if isinstance(exc, ValueError):
        return json_error(str(exc), 400, code="invalid_json")
    raise exc


def _forbidden():
    return json_error("You do not have access to this payment.", 403, code="property_forbidden")


def _load_payment(user, payment_id: int) -> Payment | JsonResponse:
    payment = payment_queryset().filter(pk=payment_id).first()
    if payment is None:
        return json_error("Payment not found.", 404, code="not_found")
    if not can_access_payment(user, payment):
        return _forbidden()
    return payment


@require_http_methods(["GET", "POST"])
def payment_collection_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return _list_payments(request)
    return _create_payment(request)


@require_permission(VIEW)
@enforce_property_query
def _list_payments(request: HttpRequest) -> JsonResponse:
    try:
        queryset = order_payments(
            filter_payments(accessible_payments(request.user, payment_queryset()), request.GET),
            request.GET,
        )
    except PaymentError as exc:
        return _handle_error(exc)
    page = paginate_queryset(request, queryset, default_size=25, max_size=100)
    summary = payment_summary(request.user)
    payload = {
        "resource": "payments",
        "count": page["count"],
        "page": page["page"],
        "page_size": page["page_size"],
        "has_next": page["has_next"],
        "summary": {key: str(value) for key, value in summary.items()}
        | {f"{key}_label": format_money(value, "MYR") for key, value in summary.items()},
        "types": serialize_types(),
        "methods": serialize_methods(),
        "statuses": serialize_statuses(),
        "stages": serialize_pipeline_stages(),
        "sources": serialize_follow_up_sources(),
        "staff": [serialize_user_summary(user) for user in payment_filter_staff(request.user)],
        "properties": [{"id": item.pk, "name": item.name} for item in payment_filter_properties(request.user)],
        "results": [serialize_payment(item) for item in page["results"]],
    }
    case_id = request.GET.get("case") or request.GET.get("case_id")
    if case_id not in (None, "", "all"):
        try:
            case = Case.objects.filter(pk=int(case_id)).first()
        except (TypeError, ValueError):
            case = None
        if case is not None and can_access_case(request.user, case):
            balance = case_balance(case)
            payload["balance"] = serialize_balance(balance)
            payload["balance_labels"] = serialize_balance_labels(balance, "MYR")
            payload["charge_kinds"] = serialize_charge_kinds()
            payload["charge_categories"] = serialize_charge_categories()
    return _json(payload)


@require_permission(CREATE, CHANGE)
def _create_payment(request: HttpRequest) -> JsonResponse:
    try:
        payment = create_payment(actor=request.user, payload=parse_json_body(request))
    except (ValueError, PaymentError) as exc:
        return _handle_error(exc)
    return _json(serialize_payment(payment_queryset().get(pk=payment.pk), include_detail=True), status=201)


@require_http_methods(["GET", "PATCH", "DELETE"])
def payment_detail_view(request: HttpRequest, payment_id: int) -> JsonResponse:
    if request.method == "GET":
        return _retrieve_payment(request, payment_id)
    if request.method == "PATCH":
        return _update_payment(request, payment_id)
    return _cancel_payment(request, payment_id)


@require_permission(VIEW)
def _retrieve_payment(request: HttpRequest, payment_id: int) -> JsonResponse:
    payment = _load_payment(request.user, payment_id)
    if isinstance(payment, JsonResponse):
        return payment
    return _json(serialize_payment(payment, include_detail=True))


@require_permission(CHANGE)
def _update_payment(request: HttpRequest, payment_id: int) -> JsonResponse:
    payment = _load_payment(request.user, payment_id)
    if isinstance(payment, JsonResponse):
        return payment
    try:
        payment = update_payment(payment, parse_json_body(request), actor=request.user)
    except (ValueError, PaymentError) as exc:
        return _handle_error(exc)
    return _json(serialize_payment(payment_queryset().get(pk=payment.pk), include_detail=True))


@require_permission(CHANGE)
def _cancel_payment(request: HttpRequest, payment_id: int) -> JsonResponse:
    payment = _load_payment(request.user, payment_id)
    if isinstance(payment, JsonResponse):
        return payment
    try:
        cancel_payment(payment, actor=request.user)
    except PaymentError as exc:
        return _handle_error(exc)
    return JsonResponse({"ok": True})


@require_http_methods(["POST"])
@require_permission(CHANGE)
def payment_submit_view(request: HttpRequest, payment_id: int) -> JsonResponse:
    payment = _load_payment(request.user, payment_id)
    if isinstance(payment, JsonResponse):
        return payment
    try:
        payment = submit_payment(payment, actor=request.user)
    except PaymentError as exc:
        return _handle_error(exc)
    return _json(serialize_payment(payment_queryset().get(pk=payment.pk), include_detail=True))


@require_http_methods(["POST"])
@require_permission(APPROVE)
def payment_approve_view(request: HttpRequest, payment_id: int) -> JsonResponse:
    payment = _load_payment(request.user, payment_id)
    if isinstance(payment, JsonResponse):
        return payment
    try:
        payment = approve_payment(payment, actor=request.user)
    except PaymentError as exc:
        return _handle_error(exc)
    return _json(serialize_payment(payment_queryset().get(pk=payment.pk), include_detail=True))


@require_http_methods(["POST"])
@require_permission(REJECT, APPROVE)
def payment_reject_view(request: HttpRequest, payment_id: int) -> JsonResponse:
    payment = _load_payment(request.user, payment_id)
    if isinstance(payment, JsonResponse):
        return payment
    try:
        payload = parse_json_body(request)
        payment = reject_payment(payment, actor=request.user, reason=payload.get("rejection_reason") or payload.get("reason") or "")
    except (ValueError, PaymentError) as exc:
        return _handle_error(exc)
    return _json(serialize_payment(payment_queryset().get(pk=payment.pk), include_detail=True))


@require_http_methods(["POST"])
@require_permission(REMIND, CHANGE)
def payment_remind_view(request: HttpRequest, payment_id: int) -> JsonResponse:
    payment = _load_payment(request.user, payment_id)
    if isinstance(payment, JsonResponse):
        return payment
    try:
        payload = parse_json_body(request)
        message = send_payment_reminder(
            payment,
            actor=request.user,
            channel=payload.get("channel"),
            content=payload.get("content") or payload.get("message"),
        )
    except (ValueError, PaymentError) as exc:
        return _handle_error(exc)
    return _json(
        {
            "ok": True,
            "status": message.status,
            "channel": message.channel,
            "payment": serialize_payment(payment_queryset().get(pk=payment.pk), include_detail=True),
        }
    )


@require_http_methods(["GET", "POST"])
def payment_attachment_collection_view(request: HttpRequest, payment_id: int) -> JsonResponse:
    payment = _load_payment(request.user, payment_id)
    if isinstance(payment, JsonResponse):
        return payment
    if request.method == "GET":
        return _json({"results": [serialize_attachment(item) for item in payment.attachments.all()]})
    return _upload_attachment(request, payment)


@require_permission(CHANGE)
def _upload_attachment(request: HttpRequest, payment: Payment) -> JsonResponse:
    uploaded = request.FILES.get("file") or request.FILES.get("attachment")
    if uploaded is None:
        return json_error("A file is required.", 400, code="invalid_attachment")
    try:
        attachment = add_attachment(
            payment,
            uploaded_file=uploaded,
            actor=request.user,
            description=request.POST.get("description") or "",
        )
    except PaymentError as exc:
        return _handle_error(exc)
    return _json(serialize_attachment(attachment), status=201)


@require_http_methods(["GET"])
@require_permission(VIEW)
def payment_attachment_download_view(request: HttpRequest, payment_id: int, attachment_id: int):
    payment = _load_payment(request.user, payment_id)
    if isinstance(payment, JsonResponse):
        return payment
    attachment = PaymentAttachment.objects.filter(pk=attachment_id, payment=payment).first()
    if attachment is None or not attachment.file:
        return json_error("Attachment not found.", 404, code="not_found")
    return FileResponse(attachment.file.open("rb"), as_attachment=False, filename=attachment.original_name or attachment.file.name)


@require_http_methods(["GET", "POST"])
def refund_collection_view(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return _list_refunds(request)
    return _create_refund(request)


@require_permission(VIEW)
def _list_refunds(request: HttpRequest) -> JsonResponse:
    queryset = accessible_refunds(request.user).select_related("payment", "payment__case", "requested_by", "approved_by")
    payment_id = request.GET.get("payment") or request.GET.get("payment_id")
    if payment_id not in (None, "", "all"):
        queryset = queryset.filter(payment_id=payment_id)
    page = paginate_queryset(request, queryset, default_size=25, max_size=100)
    return _json({"resource": "refunds", "count": page["count"], "results": [serialize_refund(item) for item in page["results"]]})


@require_permission(REQUEST_REFUND, CHANGE)
def _create_refund(request: HttpRequest) -> JsonResponse:
    try:
        payload = parse_json_body(request)
        payment_id = payload.get("payment_id")
        payment = payment_queryset().filter(pk=int(payment_id)).first() if payment_id not in (None, "") else None
    except (TypeError, ValueError):
        return json_error("payment_id is required.", 400, code="invalid_payment")
    if payment is None:
        return json_error("Payment not found.", 404, code="not_found")
    if not can_access_payment(request.user, payment):
        return _forbidden()
    try:
        refund = request_refund(payment, actor=request.user, payload=payload)
    except PaymentError as exc:
        return _handle_error(exc)
    return _json(serialize_refund(refund), status=201)


@require_http_methods(["POST"])
@require_permission(REQUEST_REFUND, CHANGE)
def payment_refund_view(request: HttpRequest, payment_id: int) -> JsonResponse:
    payment = _load_payment(request.user, payment_id)
    if isinstance(payment, JsonResponse):
        return payment
    try:
        refund = request_refund(payment, actor=request.user, payload=parse_json_body(request))
    except (ValueError, PaymentError) as exc:
        return _handle_error(exc)
    return _json(serialize_refund(refund), status=201)


def _load_refund(user, refund_id: int):
    refund = PaymentRefund.objects.select_related("payment", "payment__case", "payment__case__customer").filter(pk=refund_id).first()
    if refund is None:
        return json_error("Refund not found.", 404, code="not_found")
    if not can_access_refund(user, refund):
        return _forbidden()
    return refund


@require_http_methods(["GET"])
@require_permission(VIEW)
def refund_detail_view(request: HttpRequest, refund_id: int) -> JsonResponse:
    refund = _load_refund(request.user, refund_id)
    if isinstance(refund, JsonResponse):
        return refund
    return _json(serialize_refund(refund))


@require_http_methods(["POST"])
@require_permission(MANAGE_REFUND, APPROVE)
def refund_approve_view(request: HttpRequest, refund_id: int) -> JsonResponse:
    refund = _load_refund(request.user, refund_id)
    if isinstance(refund, JsonResponse):
        return refund
    try:
        refund = approve_refund(refund, actor=request.user)
    except PaymentError as exc:
        return _handle_error(exc)
    return _json(serialize_refund(refund))


@require_http_methods(["POST"])
@require_permission(MANAGE_REFUND, REJECT, APPROVE)
def refund_reject_view(request: HttpRequest, refund_id: int) -> JsonResponse:
    refund = _load_refund(request.user, refund_id)
    if isinstance(refund, JsonResponse):
        return refund
    try:
        payload = parse_json_body(request)
        refund = reject_refund(refund, actor=request.user, reason=payload.get("rejection_reason") or payload.get("reason") or "")
    except (ValueError, PaymentError) as exc:
        return _handle_error(exc)
    return _json(serialize_refund(refund))


@require_http_methods(["POST"])
@require_permission(MANAGE_REFUND, APPROVE)
def refund_complete_view(request: HttpRequest, refund_id: int) -> JsonResponse:
    refund = _load_refund(request.user, refund_id)
    if isinstance(refund, JsonResponse):
        return refund
    try:
        refund = complete_refund(refund, actor=request.user)
    except PaymentError as exc:
        return _handle_error(exc)
    return _json(serialize_refund(refund))


def _payment_detail(payment: Payment) -> dict:
    return serialize_payment(payment_queryset().get(pk=payment.pk), include_detail=True)


@require_http_methods(["POST"])
@require_permission(ADD_CHARGE, CHANGE)
def payment_charge_view(request: HttpRequest, payment_id: int) -> JsonResponse:
    payment = _load_payment(request.user, payment_id)
    if isinstance(payment, JsonResponse):
        return payment
    try:
        create_case_charge(actor=request.user, case=payment.case, payload=parse_json_body(request), kind=ChargeKind.CHARGE)
    except (ValueError, PaymentError) as exc:
        return _handle_error(exc)
    return _json(_payment_detail(payment), status=201)


@require_http_methods(["POST"])
@require_permission(ADD_PENALTY, CHANGE)
def payment_penalty_view(request: HttpRequest, payment_id: int) -> JsonResponse:
    payment = _load_payment(request.user, payment_id)
    if isinstance(payment, JsonResponse):
        return payment
    try:
        create_case_charge(actor=request.user, case=payment.case, payload=parse_json_body(request), kind=ChargeKind.PENALTY)
    except (ValueError, PaymentError) as exc:
        return _handle_error(exc)
    return _json(_payment_detail(payment), status=201)


@require_http_methods(["POST"])
@require_permission(VOID_CHARGE)
def charge_void_view(request: HttpRequest, charge_id: int) -> JsonResponse:
    charge = CaseCharge.objects.select_related("case", "case__customer", "case__property").filter(pk=charge_id).first()
    if charge is None:
        return json_error("Charge not found.", 404, code="not_found")
    if not can_access_case(request.user, charge.case):
        return json_error("You do not have access to this payment.", 403, code="property_forbidden")
    try:
        payload = parse_json_body(request)
        void_case_charge(charge, actor=request.user, reason=payload.get("reason") or payload.get("void_reason") or "")
    except (ValueError, PaymentError) as exc:
        return _handle_error(exc)
    payment = payment_queryset().filter(case=charge.case).order_by("-id").first()
    if payment is None:
        return _json(serialize_charge(charge))
    return _json(_payment_detail(payment))

