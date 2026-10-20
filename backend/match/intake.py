from __future__ import annotations

import logging

from pipeline.models import PipelineStage
from match.models import MatchRequest, MatchRequestPriority, MatchRequestType
from match.services import ensure_match_request

logger = logging.getLogger(__name__)


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        logger.exception("Match intake failed.")
        return None


def ingest_from_case(case, *, created: bool, previous: dict | None = None):
    previous = previous or {}
    if created:
        request_type = MatchRequestType.BOOKING if case.check_in else MatchRequestType.INQUIRY
        _safe(
            ensure_match_request,
            source_module="cases",
            source_ref=f"case:{case.pk}",
            request_type=request_type,
            subject=case.title or "Customer request",
            description=case.original_request or case.description or "",
            customer=case.customer,
            property_obj=case.property,
            location=getattr(case, "location", None),
            related_case=case,
        )
        return

    existing = MatchRequest.objects.filter(source_module="cases", source_ref=f"case:{case.pk}").first()
    if existing and existing.request_type == MatchRequestType.INQUIRY and case.check_in and existing.is_open():
        existing.request_type = MatchRequestType.BOOKING
        existing.location = getattr(case, "location", existing.location)
        existing.save(update_fields=["request_type", "location", "updated_at"])

    prev_stage = previous.get("stage")
    if case.check_in and case.stage == PipelineStage.LOST and prev_stage and prev_stage != PipelineStage.LOST:
        _safe(
            ensure_match_request,
            source_module="bookings",
            source_ref=f"case:{case.pk}:cancelled",
            request_type=MatchRequestType.CANCELLATION,
            subject=f"Cancellation: {case.case_number}",
            description=case.title or "",
            customer=case.customer,
            property_obj=case.property,
            location=getattr(case, "location", None),
            related_case=case,
            priority=MatchRequestPriority.HIGH,
        )

    prev_check_in = previous.get("check_in")
    prev_check_out = previous.get("check_out")
    if (
        case.check_in
        and prev_check_in
        and (prev_check_in != case.check_in or prev_check_out != case.check_out)
    ):
        _safe(
            ensure_match_request,
            source_module="bookings",
            source_ref=f"case:{case.pk}:modified",
            request_type=MatchRequestType.MODIFICATION,
            subject=f"Modification: {case.case_number}",
            description=case.title or "",
            customer=case.customer,
            property_obj=case.property,
            location=getattr(case, "location", None),
            related_case=case,
        )


def ingest_from_quote(quote, *, created: bool):
    if not created:
        return
    case = quote.case
    _safe(
        ensure_match_request,
        source_module="quotes",
        source_ref=f"quote:{quote.pk}",
        request_type=MatchRequestType.QUOTE,
        subject=f"Quote {quote.quote_number}",
        description=quote.notes or case.title or "",
        customer=case.customer,
        property_obj=case.property,
        location=getattr(case, "location", None),
        related_case=case,
        related_quote=quote,
    )


def ingest_from_payment(payment, *, created: bool, previous_status: str | None = None):
    case = payment.case
    if created:
        _safe(
            ensure_match_request,
            source_module="payments",
            source_ref=f"payment:{payment.pk}",
            request_type=MatchRequestType.PAYMENT,
            subject=f"Payment {payment.payment_number}",
            description=payment.notes or case.title or "",
            customer=case.customer,
            property_obj=case.property,
            location=getattr(case, "location", None),
            related_case=case,
            related_payment=payment,
        )
    if previous_status != "rejected" and getattr(payment, "status", None) == "rejected":
        _safe(
            ensure_match_request,
            source_module="payments",
            source_ref=f"payment:{payment.pk}:rejected",
            request_type=MatchRequestType.PAYMENT,
            subject=f"Payment rejected: {payment.payment_number}",
            description=getattr(payment, "rejection_reason", "") or payment.notes or "",
            customer=case.customer,
            property_obj=case.property,
            location=getattr(case, "location", None),
            related_case=case,
            related_payment=payment,
            priority=MatchRequestPriority.HIGH,
        )
