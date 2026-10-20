from cases.access import accessible_cases, can_access_case
from payments.models import Payment, PaymentRefund


def accessible_payments(user, queryset=None):
    qs = queryset if queryset is not None else Payment.objects.all()
    return qs.filter(case_id__in=accessible_cases(user).values("pk"))


def can_access_payment(user, payment: Payment | None) -> bool:
    if payment is None:
        return False
    return can_access_case(user, payment.case)


def accessible_refunds(user, queryset=None):
    qs = queryset if queryset is not None else PaymentRefund.objects.all()
    return qs.filter(payment__case_id__in=accessible_cases(user).values("pk"))


def can_access_refund(user, refund: PaymentRefund | None) -> bool:
    if refund is None:
        return False
    return can_access_payment(user, refund.payment)
