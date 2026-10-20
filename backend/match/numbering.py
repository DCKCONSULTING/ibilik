from django.db.models import Max

from match.models import MatchRequest


def allocate_request_number() -> tuple[int, str]:
    last = MatchRequest.objects.aggregate(Max("sequence"))["sequence__max"] or 1000
    sequence = last + 1
    return sequence, f"MATCH-{sequence}"
