from accounts.authorization import can_access_property, has_global_property_access, is_superuser
from locations.models import Location


def accessible_locations(user, queryset=None):
    qs = queryset if queryset is not None else Location.objects.all()
    if not getattr(user, "is_authenticated", False):
        return qs.none()
    if is_superuser(user) or has_global_property_access(user):
        return qs
    return qs.filter(property__staff=user)


def can_access_location(user, location: Location | None) -> bool:
    if location is None:
        return False
    return can_access_property(user, location.property)
