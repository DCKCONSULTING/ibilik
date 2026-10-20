from django.db.models import Max

from quotes.models import Quote


def allocate_quote_number() -> tuple[int, str]:
    last = Quote.objects.aggregate(Max("sequence"))["sequence__max"] or 1000
    sequence = last + 1
    return sequence, f"QT-{sequence}"
