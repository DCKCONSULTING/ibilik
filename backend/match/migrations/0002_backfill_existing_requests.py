from django.db import migrations
from django.db.models import Max


def _allocate(MatchRequest):
    last = MatchRequest.objects.aggregate(Max("sequence"))["sequence__max"] or 1000
    sequence = last + 1
    return sequence, f"MATCH-{sequence}"


def _ensure(MatchRequest, MatchRequestHistory, **values):
    source_module = values["source_module"]
    source_ref = values["source_ref"]
    if MatchRequest.objects.filter(source_module=source_module, source_ref=source_ref).exists():
        return
    sequence, request_number = _allocate(MatchRequest)
    request = MatchRequest.objects.create(sequence=sequence, request_number=request_number, **values)
    MatchRequestHistory.objects.create(
        request=request,
        action="created",
        previous_value="",
        new_value=request_number,
        actor=None,
    )


def forwards(apps, schema_editor):
    Case = apps.get_model("cases", "Case")
    Quote = apps.get_model("quotes", "Quote")
    Payment = apps.get_model("payments", "Payment")
    MatchRequest = apps.get_model("match", "MatchRequest")
    MatchRequestHistory = apps.get_model("match", "MatchRequestHistory")

    for case in Case.objects.all().iterator():
        _ensure(
            MatchRequest,
            MatchRequestHistory,
            source_module="cases",
            source_ref=f"case:{case.pk}",
            request_type="booking" if case.check_in else "inquiry",
            customer_id=case.customer_id,
            property_id=case.property_id,
            location_id=case.location_id,
            related_case_id=case.pk,
            subject=(case.title or "Customer request")[:255],
            description=case.original_request or case.description or "",
            priority="normal",
            status="new",
        )
        if case.check_in and case.stage == "lost":
            _ensure(
                MatchRequest,
                MatchRequestHistory,
                source_module="bookings",
                source_ref=f"case:{case.pk}:cancelled",
                request_type="cancellation",
                customer_id=case.customer_id,
                property_id=case.property_id,
                location_id=case.location_id,
                related_case_id=case.pk,
                subject=f"Cancellation: {case.case_number}",
                description=case.title or "",
                priority="high",
                status="new",
            )

    for quote in Quote.objects.select_related("case").iterator():
        case = quote.case
        _ensure(
            MatchRequest,
            MatchRequestHistory,
            source_module="quotes",
            source_ref=f"quote:{quote.pk}",
            request_type="quote",
            customer_id=case.customer_id,
            property_id=case.property_id,
            location_id=case.location_id,
            related_case_id=case.pk,
            related_quote_id=quote.pk,
            subject=f"Quote {quote.quote_number}",
            description=quote.notes or case.title or "",
            priority="normal",
            status="new",
        )

    for payment in Payment.objects.select_related("case").iterator():
        case = payment.case
        _ensure(
            MatchRequest,
            MatchRequestHistory,
            source_module="payments",
            source_ref=f"payment:{payment.pk}",
            request_type="payment",
            customer_id=case.customer_id,
            property_id=case.property_id,
            location_id=case.location_id,
            related_case_id=case.pk,
            related_payment_id=payment.pk,
            subject=f"Payment {payment.payment_number}",
            description=payment.notes or case.title or "",
            priority="normal",
            status="new",
        )
        if payment.status == "rejected":
            _ensure(
                MatchRequest,
                MatchRequestHistory,
                source_module="payments",
                source_ref=f"payment:{payment.pk}:rejected",
                request_type="payment",
                customer_id=case.customer_id,
                property_id=case.property_id,
                location_id=case.location_id,
                related_case_id=case.pk,
                related_payment_id=payment.pk,
                subject=f"Payment rejected: {payment.payment_number}",
                description=getattr(payment, "rejection_reason", "") or payment.notes or "",
                priority="high",
                status="new",
            )


def backwards(apps, schema_editor):
    MatchRequest = apps.get_model("match", "MatchRequest")
    MatchRequest.objects.filter(source_module__in={"cases", "quotes", "payments", "bookings"}).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("match", "0001_initial"),
        ("cases", "0007_case_charges_and_payment_idempotency"),
        ("quotes", "0002_quote_currency_myr"),
        ("payments", "0004_case_charges_and_payment_idempotency"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
