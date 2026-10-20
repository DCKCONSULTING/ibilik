from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from cases.models import Case
from payments.models import Payment
from quotes.models import Quote


@receiver(pre_save, sender=Case)
def remember_case_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._match_previous = None
        return
    previous = Case.objects.filter(pk=instance.pk).values("stage", "check_in", "check_out").first()
    instance._match_previous = previous


@receiver(post_save, sender=Case)
def ingest_case_match(sender, instance, created, **kwargs):
    from match.intake import ingest_from_case

    ingest_from_case(instance, created=created, previous=getattr(instance, "_match_previous", None))


@receiver(post_save, sender=Quote)
def ingest_quote_match(sender, instance, created, **kwargs):
    from match.intake import ingest_from_quote

    ingest_from_quote(instance, created=created)


@receiver(pre_save, sender=Payment)
def remember_payment_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._match_previous_status = None
        return
    previous = Payment.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    instance._match_previous_status = previous


@receiver(post_save, sender=Payment)
def ingest_payment_match(sender, instance, created, **kwargs):
    from match.intake import ingest_from_payment

    ingest_from_payment(
        instance,
        created=created,
        previous_status=getattr(instance, "_match_previous_status", None),
    )
