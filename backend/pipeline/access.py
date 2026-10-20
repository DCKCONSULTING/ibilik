from __future__ import annotations

from django.db.models import QuerySet

from accounts.authorization import assigned_property_ids, has_global_property_access, is_superuser
from pipeline.models import Opportunity


def accessible_opportunities(user, queryset: QuerySet | None = None) -> QuerySet:
    qs = queryset if queryset is not None else Opportunity.objects.all()
    if not getattr(user, "is_authenticated", False):
        return qs.none()
    if is_superuser(user) or has_global_property_access(user):
        return qs
    property_ids = assigned_property_ids(user)
    return qs.filter(property_id__in=property_ids)


def can_access_opportunity(user, opportunity: Opportunity | None) -> bool:
    if opportunity is None or not getattr(user, "is_authenticated", False):
        return False
    if is_superuser(user) or has_global_property_access(user):
        return True
    if opportunity.property_id is None:
        return False
    return opportunity.property_id in assigned_property_ids(user)
