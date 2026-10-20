from __future__ import annotations

from django.http import HttpRequest


def paginate_queryset(request: HttpRequest, queryset, *, default_size: int = 20, max_size: int = 100):
    try:
        page = max(int(request.GET.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get("page_size", default_size))
    except (TypeError, ValueError):
        page_size = default_size
    page_size = min(max(page_size, 1), max_size)
    total = queryset.count()
    start = (page - 1) * page_size
    items = list(queryset[start : start + page_size])
    return {
        "count": total,
        "page": page,
        "page_size": page_size,
        "has_next": start + page_size < total,
        "results": items,
    }
