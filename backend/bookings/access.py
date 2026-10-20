from cases.access import accessible_cases, can_access_case


def accessible_bookings(user, queryset=None):
    qs = accessible_cases(user, queryset)
    return qs.filter(check_in__isnull=False)


def can_access_booking(user, case) -> bool:
    if case is None or case.check_in is None:
        return False
    return can_access_case(user, case)
