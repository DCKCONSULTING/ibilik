from __future__ import annotations

from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from cases.models import Case
from cases.services import CaseError, follow_up_filter_properties, follow_up_filter_staff, parse_date_bound
from quotes.access import accessible_quotes
from quotes.errors import QuoteError
from quotes.models import Quote, QuoteStatus
from quotes.numbering import allocate_quote_number

DEFAULT_VALIDITY_DAYS = 7


def quote_queryset():
    return Quote.objects.select_related(
        "case",
        "case__customer",
        "case__property",
        "case__assigned_to",
        "created_by",
    )


def record_quote_from_case(case: Case, *, actor=None) -> Quote:
    existing = case.case_quotes.filter(status=QuoteStatus.PENDING).order_by("-id").first()
    valid_until = timezone.now() + timedelta(days=DEFAULT_VALIDITY_DAYS)
    if existing is not None:
        existing.amount = case.value
        existing.notes = case.quote_notes or existing.notes
        existing.valid_until = valid_until
        existing.save(update_fields=["amount", "notes", "valid_until", "updated_at"])
        return existing
    sequence, quote_number = allocate_quote_number()
    return Quote.objects.create(
        sequence=sequence,
        quote_number=quote_number,
        case=case,
        amount=case.value,
        currency="MYR",
        status=QuoteStatus.PENDING,
        valid_until=valid_until,
        notes=case.quote_notes or "",
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )


def mark_latest_quote(case: Case, status: str) -> Quote | None:
    quote = case.case_quotes.exclude(status=QuoteStatus.CANCELLED).order_by("-id").first()
    if quote is None:
        return None
    if quote.status == status:
        return quote
    quote.status = status
    quote.save(update_fields=["status", "updated_at"])
    return quote


def sync_quote_after_workflow(case: Case, action: str, *, actor=None) -> Quote | None:
    if action == "quote":
        return record_quote_from_case(case, actor=actor)
    if action == "approve":
        return mark_latest_quote(case, QuoteStatus.ACCEPTED)
    if action == "reopen":
        updated = None
        for quote in case.case_quotes.filter(status=QuoteStatus.PENDING):
            quote.status = QuoteStatus.CANCELLED
            quote.save(update_fields=["status", "updated_at"])
            updated = quote
        return updated
    return None


def sync_quote_for_stage(case: Case) -> Quote | None:
    if case.stage == "won":
        return mark_latest_quote(case, QuoteStatus.ACCEPTED)
    if case.stage == "lost":
        return mark_latest_quote(case, QuoteStatus.REJECTED)
    return None


def filter_quotes(queryset, params):
    status = (params.get("status") or "all").strip().lower()
    if status in {"", "all"}:
        pass
    elif status == "expired":
        queryset = queryset.filter(status=QuoteStatus.PENDING, valid_until__lt=timezone.now())
    elif status in QuoteStatus.values:
        queryset = queryset.filter(status=status)
    else:
        raise QuoteError("Unknown quote status.", code="invalid_status")

    property_id = params.get("property")
    if property_id not in (None, "", "all"):
        try:
            queryset = queryset.filter(case__property_id=int(property_id))
        except (TypeError, ValueError) as exc:
            raise QuoteError("property must be an integer.", code="invalid_property") from exc

    staff = params.get("staff") or params.get("assigned_staff")
    if staff not in (None, "", "all"):
        try:
            queryset = queryset.filter(case__assigned_to_id=int(staff))
        except (TypeError, ValueError) as exc:
            raise QuoteError("staff must be an integer.", code="invalid_assignee") from exc

    case_id = params.get("case") or params.get("case_id")
    if case_id not in (None, "", "all"):
        try:
            queryset = queryset.filter(case_id=int(case_id))
        except (TypeError, ValueError):
            queryset = queryset.filter(case__case_number__icontains=str(case_id).strip())

    case_number = (params.get("case_number") or "").strip()
    if case_number:
        queryset = queryset.filter(case__case_number__icontains=case_number)

    customer_id = params.get("customer") or params.get("customer_id")
    if customer_id not in (None, "", "all"):
        try:
            queryset = queryset.filter(case__customer_id=int(customer_id))
        except (TypeError, ValueError) as exc:
            raise QuoteError("customer must be an integer.", code="invalid_customer") from exc

    date_field = (params.get("date_field") or "created_at").strip()
    field_map = {
        "created_at": "created_at",
        "created": "created_at",
        "valid_until": "valid_until",
        "valid": "valid_until",
        "updated_at": "updated_at",
        "updated": "updated_at",
    }
    if date_field not in field_map:
        raise QuoteError("Unknown date field.", code="invalid_date_field")
    lookup = field_map[date_field]
    due = (params.get("due") or params.get("date") or "all").strip().lower()
    if due not in (None, "", "all"):
        now = timezone.now()
        local = timezone.localtime(now)
        start_today = local.replace(hour=0, minute=0, second=0, microsecond=0)
        if due == "today":
            queryset = queryset.filter(**{f"{lookup}__gte": start_today, f"{lookup}__lt": start_today + timedelta(days=1)})
        elif due == "this_week":
            week_start = start_today - timedelta(days=local.weekday())
            queryset = queryset.filter(**{f"{lookup}__gte": week_start, f"{lookup}__lt": week_start + timedelta(days=7)})
        elif due == "this_month":
            month_start = start_today.replace(day=1)
            if month_start.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1)
            queryset = queryset.filter(**{f"{lookup}__gte": month_start, f"{lookup}__lt": month_end})
        elif due == "custom":
            try:
                date_from = parse_date_bound(params.get("date_from") or params.get("from"))
                date_to = parse_date_bound(params.get("date_to") or params.get("to"), end=True)
            except CaseError as exc:
                raise QuoteError(str(exc), code=getattr(exc, "code", "invalid_date")) from exc
            if date_from is not None:
                queryset = queryset.filter(**{f"{lookup}__gte": date_from})
            if date_to is not None:
                queryset = queryset.filter(**{f"{lookup}__lte": date_to})
        else:
            raise QuoteError("Unknown date filter.", code="invalid_due_filter")

    search = (params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(quote_number__icontains=search)
            | Q(notes__icontains=search)
            | Q(case__case_number__icontains=search)
            | Q(case__title__icontains=search)
            | Q(case__customer__name__icontains=search)
            | Q(case__customer__phone__icontains=search)
            | Q(case__customer__email__icontains=search)
            | Q(case__property__name__icontains=search)
        )
    return queryset


def order_quotes(queryset, params):
    allowed = {
        "created_at",
        "-created_at",
        "updated_at",
        "-updated_at",
        "amount",
        "-amount",
        "valid_until",
        "-valid_until",
    }
    ordering = (params.get("ordering") or params.get("sort") or "-created_at").strip()
    if ordering not in allowed:
        raise QuoteError("Unknown sort field.", code="invalid_ordering")
    field = ordering.lstrip("-")
    descending = ordering.startswith("-")
    expression = F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_last=True)
    return queryset.order_by(expression, "-id" if descending else "id")


def quote_filter_staff(user):
    return follow_up_filter_staff(user)


def quote_filter_properties(user):
    return follow_up_filter_properties(user)


def accessible_quote_queryset(user):
    return accessible_quotes(user, quote_queryset())
