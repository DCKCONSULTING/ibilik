from django.db.models import Max

from payments.models import Payment, PaymentRefund


def allocate_payment_number() -> tuple[int, str]:
    last = Payment.objects.aggregate(Max("sequence"))["sequence__max"] or 1000
    sequence = last + 1
    return sequence, f"PAY-{sequence}"


def allocate_refund_number() -> tuple[int, str]:
    last = PaymentRefund.objects.aggregate(Max("sequence"))["sequence__max"] or 1000
    sequence = last + 1
    return sequence, f"REF-{sequence}"
