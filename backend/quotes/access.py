from cases.access import accessible_cases, can_access_case
from quotes.models import Quote


def accessible_quotes(user, queryset=None):
    qs = queryset if queryset is not None else Quote.objects.all()
    return qs.filter(case_id__in=accessible_cases(user).values("pk"))


def can_access_quote(user, quote: Quote | None) -> bool:
    if quote is None:
        return False
    return can_access_case(user, quote.case)
