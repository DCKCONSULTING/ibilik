from django.db import migrations


STATUS_MAP = {
    "expected": "pending",
    "received": "approved",
    "cancelled": "cancelled",
}


def copy_legacy_payments(apps, schema_editor):
    CasePayment = apps.get_model("cases", "CasePayment")
    Payment = apps.get_model("payments", "Payment")
    sequence = 1000
    for item in CasePayment.objects.order_by("id"):
        sequence += 1
        Payment.objects.get_or_create(
            payment_number=f"PAY-{sequence}",
            defaults={
                "sequence": sequence,
                "case_id": item.case_id,
                "payment_type": "payment",
                "amount": item.amount,
                "currency": item.currency,
                "payment_method": "bank_transfer",
                "status": STATUS_MAP.get(item.status, "pending"),
                "expected_date": item.expected_date,
                "paid_at": item.paid_at,
                "created_by_id": item.created_by_id,
            },
        )


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
        ("cases", "0003_case_stay_and_payment"),
    ]

    operations = [
        migrations.RunPython(copy_legacy_payments, noop),
    ]
