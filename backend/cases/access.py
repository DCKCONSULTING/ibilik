from __future__ import annotations

from django.db.models import QuerySet

from accounts.authorization import assigned_property_ids, has_global_property_access, is_superuser
from cases.models import Case, CaseFollowUp


def accessible_cases(user, queryset: QuerySet | None = None) -> QuerySet:
    qs = queryset if queryset is not None else Case.objects.all()
    if not getattr(user, "is_authenticated", False):
        return qs.none()
    if is_superuser(user) or has_global_property_access(user):
        return qs
    property_ids = assigned_property_ids(user)
    return qs.filter(property_id__in=property_ids)


def can_access_case(user, case: Case | None) -> bool:
    if case is None or not getattr(user, "is_authenticated", False):
        return False
    if is_superuser(user) or has_global_property_access(user):
        return True
    if case.property_id is None:
        return False
    return case.property_id in assigned_property_ids(user)


def accessible_follow_ups(user, queryset: QuerySet | None = None) -> QuerySet:
    from accounts.scope import owned_or_team_q

    qs = queryset if queryset is not None else CaseFollowUp.objects.all()
    qs = qs.filter(case_id__in=accessible_cases(user).values("pk"))
    return qs.filter(owned_or_team_q(user))


def can_access_follow_up(user, follow_up: CaseFollowUp | None) -> bool:
    from accounts.scope import can_view_owned_record

    if follow_up is None:
        return False
    if not can_access_case(user, follow_up.case):
        return False
    return can_view_owned_record(
        user,
        owner_id=follow_up.assigned_to_id,
        created_by_id=follow_up.created_by_id,
    )
