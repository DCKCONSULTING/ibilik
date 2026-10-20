from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import F, Prefetch, Q
from django.utils import timezone

from decimal import Decimal, InvalidOperation

from locations.errors import LocationError
from locations.models import BedType, Location, LocationStatus, LocationType


def parse_required_text(value, *, field: str) -> str:
    if value is None:
        raise LocationError(f"{field} is required.")
    text = str(value).strip()
    if not text:
        raise LocationError(f"{field} is required.")
    return text


def parse_optional_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_location_type(value) -> str:
    if value is None or value == "":
        raise LocationError("Type is required.")
    text = str(value).strip()
    valid = {item.value for item in LocationType}
    if text not in valid:
        raise LocationError("Type is not supported.", code="invalid_type")
    return text


def parse_status(value) -> str:
    if value is None or value == "":
        return LocationStatus.AVAILABLE
    text = str(value).strip()
    valid = {item.value for item in LocationStatus}
    if text not in valid:
        raise LocationError("Status is not supported.", code="invalid_status")
    return text


def parse_capacity(value):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise LocationError("Capacity must be a positive integer.", code="invalid_capacity")
    try:
        capacity = int(value)
    except (TypeError, ValueError) as exc:
        raise LocationError("Capacity must be a positive integer.", code="invalid_capacity") from exc
    if capacity < 1:
        raise LocationError("Capacity must be a positive integer.", code="invalid_capacity")
    return capacity


def parse_optional_int(value, *, field: str, minimum: int = 1):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise LocationError(f"{field} must be a valid integer.", code="invalid_capacity")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise LocationError(f"{field} must be a valid integer.", code="invalid_capacity") from exc
    if number < minimum:
        raise LocationError(f"{field} must be at least {minimum}.", code="invalid_capacity")
    return number


def parse_optional_rate(value):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise LocationError("Rate must be a valid decimal.", code="invalid_rate")
    try:
        rate = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise LocationError("Rate must be a valid decimal.", code="invalid_rate") from exc
    if not rate.is_finite() or rate < 0:
        raise LocationError("Rate must be a valid decimal.", code="invalid_rate")
    return rate.quantize(Decimal("0.01"))


def parse_bed_type(value) -> str:
    text = parse_optional_text(value)
    if not text:
        return ""
    valid = {item.value for item in BedType}
    if text not in valid:
        raise LocationError("Bed type is not supported.", code="invalid_bed_type")
    return text


def parse_amenities(value) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if not isinstance(value, list):
        raise LocationError("Amenities must be a list.", code="invalid_amenities")
    return [str(item).strip() for item in value if str(item).strip()]


def parse_size(value):
    if value in (None, ""):
        return None
    try:
        size = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise LocationError("Size must be a valid decimal.", code="invalid_size") from exc
    if not size.is_finite() or size <= 0:
        raise LocationError("Size must be a positive number.", code="invalid_size")
    return size.quantize(Decimal("0.01"))


def parse_active(value, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise LocationError("Active must be a boolean.", code="invalid_active")


def ensure_unique_code(property_obj, code: str, *, exclude_pk=None) -> None:
    if not code:
        return
    queryset = Location.objects.filter(property=property_obj, code=code)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    if queryset.exists():
        raise LocationError(
            "A location with this code already exists for the property.",
            code="duplicate_code",
        )


def locations_for_property(property_obj):
    return Location.objects.filter(property=property_obj).select_related("property")


def filter_locations(queryset, params):
    location_type = params.get("type")
    if location_type not in (None, "", "all"):
        valid = {item.value for item in LocationType}
        if location_type not in valid:
            raise LocationError("Type is not supported.", code="invalid_type")
        queryset = queryset.filter(location_type=location_type)

    status = params.get("status")
    if status not in (None, "", "all"):
        valid = {item.value for item in LocationStatus}
        if status not in valid:
            raise LocationError("Status is not supported.", code="invalid_status")
        queryset = queryset.filter(status=status)

    active = params.get("active")
    if active not in (None, "", "all"):
        queryset = queryset.filter(active=parse_active(active))

    search = parse_optional_text(params.get("search"))
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(code__icontains=search)
            | Q(property__name__icontains=search)
            | Q(floor__icontains=search)
        )

    return queryset.order_by("name", "id")


def _boolean_param(value, *, field: str):
    if value in (None, "", "all"):
        return None
    return parse_active(value, default=True)


def annotate_occupancy(queryset, now=None):
    from locations.location_state import occupancy_exists

    in_house, upcoming = occupancy_exists(now)
    return queryset.annotate(has_current_stay=in_house, has_upcoming_stay=upcoming)


def apply_occupancy_filter(queryset, occupancy):
    occupancy = (occupancy or "all").strip().lower()
    queryset = annotate_occupancy(queryset)
    if occupancy in {"", "all"}:
        return queryset
    if occupancy == "free":
        return queryset.filter(has_current_stay=False, has_upcoming_stay=False)
    if occupancy in {"in_house", "occupied"}:
        return queryset.filter(has_current_stay=True)
    if occupancy in {"reserved", "upcoming"}:
        return queryset.filter(has_current_stay=False, has_upcoming_stay=True)
    raise LocationError("Unknown occupancy filter.", code="invalid_occupancy")


def prefetch_stay_cases(queryset):
    from cases.models import Case

    return queryset.prefetch_related(
        Prefetch(
            "cases",
            queryset=Case.objects.select_related("customer", "property").order_by("check_in", "id"),
            to_attr="stay_cases",
        )
    )


def filter_availability(queryset, params):
    property_id = params.get("property")
    if property_id not in (None, "", "all"):
        try:
            queryset = queryset.filter(property_id=int(property_id))
        except (TypeError, ValueError) as exc:
            raise LocationError("property must be an integer.", code="invalid_property") from exc

    queryset = filter_locations(queryset, params)

    bookable = _boolean_param(params.get("bookable") or params.get("is_bookable"), field="bookable")
    if bookable is not None:
        queryset = queryset.filter(is_bookable=bookable)

    floor = parse_optional_text(params.get("floor"))
    if floor:
        queryset = queryset.filter(floor__iexact=floor)

    occupancy = params.get("occupancy") or params.get("availability") or "all"
    queryset = apply_occupancy_filter(queryset, occupancy)

    bookable_now = _boolean_param(params.get("bookable_now") or params.get("available_for_booking"), field="bookable_now")
    if bookable_now is True:
        queryset = queryset.filter(
            active=True,
            is_bookable=True,
            status=LocationStatus.AVAILABLE,
            has_current_stay=False,
            has_upcoming_stay=False,
        )
    elif bookable_now is False:
        queryset = queryset.exclude(
            active=True,
            is_bookable=True,
            status=LocationStatus.AVAILABLE,
            has_current_stay=False,
            has_upcoming_stay=False,
        )

    if _boolean_param(params.get("maintenance"), field="maintenance") is True:
        queryset = queryset.filter(status__in=[LocationStatus.MAINTENANCE, LocationStatus.OUT_OF_ORDER])

    now = timezone.now()
    start = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = start + timedelta(days=1)
    if _boolean_param(params.get("check_in_today"), field="check_in_today") is True:
        from cases.models import Case
        from pipeline.models import PipelineStage

        ids = Case.objects.filter(check_in__gte=start, check_in__lt=day_end, actual_check_in__isnull=True).exclude(stage=PipelineStage.LOST).values("location_id")
        queryset = queryset.filter(pk__in=ids)
    if _boolean_param(params.get("check_out_today"), field="check_out_today") is True:
        from cases.models import Case
        from pipeline.models import PipelineStage

        ids = (
            Case.objects.filter(check_out__gte=start, check_out__lt=day_end, actual_check_out__isnull=True)
            .exclude(stage=PipelineStage.LOST)
            .values("location_id")
        )
        queryset = queryset.filter(pk__in=ids)

    guest = parse_optional_text(params.get("guest") or params.get("customer"))
    if guest:
        from cases.models import Case

        ids = Case.objects.filter(Q(customer__name__icontains=guest) | Q(case_number__icontains=guest)).values("location_id")
        queryset = queryset.filter(pk__in=ids)

    return order_availability(queryset, params)


def order_availability(queryset, params):
    allowed = {
        "name": "name",
        "-name": "-name",
        "property": "property__name",
        "-property": "-property__name",
        "type": "location_type",
        "-type": "-location_type",
        "status": "status",
        "-status": "-status",
        "floor": "floor",
        "-floor": "-floor",
        "updated_at": "updated_at",
        "-updated_at": "-updated_at",
    }
    ordering = (params.get("ordering") or params.get("sort") or "property").strip()
    if ordering not in allowed:
        raise LocationError("Unknown sort field.", code="invalid_ordering")
    field = allowed[ordering]
    descending = field.startswith("-")
    lookup = field.lstrip("-")
    expression = F(lookup).desc(nulls_last=True) if descending else F(lookup).asc(nulls_last=True)
    return queryset.order_by("property__name", expression, "name", "id") if lookup != "property__name" else queryset.order_by(expression, "name", "id")


def availability_filter_properties(user):
    from accounts.authorization import accessible_properties

    return accessible_properties(user).order_by("name", "id")


def availability_floors(queryset):
    return [
        value
        for value in queryset.exclude(floor="").values_list("floor", flat=True).distinct().order_by("floor")
        if value
    ]


@transaction.atomic
def create_location(property_obj, payload: dict) -> Location:
    name = parse_required_text(payload.get("name"), field="Name")
    code = parse_optional_text(payload.get("code"))
    location_type = parse_location_type(payload.get("type") or payload.get("location_type"))
    description = parse_optional_text(payload.get("description"))
    capacity = parse_capacity(payload.get("capacity"))
    status = parse_status(payload.get("status"))
    active = parse_active(payload.get("active"), default=True)
    if not active:
        status = LocationStatus.INACTIVE
    ensure_unique_code(property_obj, code)
    return Location.objects.create(
        property=property_obj,
        name=name,
        code=code,
        location_type=location_type,
        description=description,
        capacity=capacity,
        max_adults=parse_optional_int(payload.get("max_adults"), field="Max adults"),
        max_children=parse_optional_int(payload.get("max_children"), field="Max children", minimum=0),
        floor=parse_optional_text(payload.get("floor")),
        bed_type=parse_bed_type(payload.get("bed_type")),
        bed_count=parse_optional_int(payload.get("bed_count"), field="Bed count"),
        base_rate=parse_optional_rate(payload.get("base_rate", payload.get("rate"))),
        currency=parse_optional_text(payload.get("currency")).upper(),
        status=status,
        is_bookable=parse_active(payload.get("is_bookable"), default=True),
        amenities=parse_amenities(payload.get("amenities")),
        size_sqm=parse_size(payload.get("size_sqm")),
        active=active,
    )


@transaction.atomic
def update_location(location: Location, payload: dict, *, actor=None) -> Location:
    if "name" in payload:
        location.name = parse_required_text(payload.get("name"), field="Name")
    if "code" in payload:
        code = parse_optional_text(payload.get("code"))
        ensure_unique_code(location.property, code, exclude_pk=location.pk)
        location.code = code
    if "type" in payload or "location_type" in payload:
        location.location_type = parse_location_type(payload.get("type") or payload.get("location_type"))
    if "description" in payload:
        location.description = parse_optional_text(payload.get("description"))
    if "capacity" in payload:
        location.capacity = parse_capacity(payload.get("capacity"))
    if "max_adults" in payload:
        location.max_adults = parse_optional_int(payload.get("max_adults"), field="Max adults")
    if "max_children" in payload:
        location.max_children = parse_optional_int(payload.get("max_children"), field="Max children", minimum=0)
    if "floor" in payload:
        location.floor = parse_optional_text(payload.get("floor"))
    if "bed_type" in payload:
        location.bed_type = parse_bed_type(payload.get("bed_type"))
    if "bed_count" in payload:
        location.bed_count = parse_optional_int(payload.get("bed_count"), field="Bed count")
    if "base_rate" in payload or "rate" in payload:
        location.base_rate = parse_optional_rate(payload.get("base_rate", payload.get("rate")))
    if "currency" in payload:
        location.currency = parse_optional_text(payload.get("currency")).upper()
    if "is_bookable" in payload:
        location.is_bookable = parse_active(payload.get("is_bookable"))
    if "amenities" in payload:
        location.amenities = parse_amenities(payload.get("amenities"))
    if "size_sqm" in payload:
        location.size_sqm = parse_size(payload.get("size_sqm"))
    previous_status = location.status
    if "status" in payload:
        location.status = parse_status(payload.get("status"))
    if "active" in payload:
        location.active = parse_active(payload.get("active"))
        if not location.active:
            location.status = LocationStatus.INACTIVE
    location.save()
    if location.status != previous_status:
        from locations.location_state import record_status_change

        record_status_change(location, previous_status, actor=actor, reason="Location updated")
    return location


@transaction.atomic
def deactivate_location(location: Location, *, actor=None) -> Location:
    from locations.location_state import set_operational_status

    return set_operational_status(location, LocationStatus.INACTIVE, actor=actor, reason="Deactivated")


def location_has_historical_relationships(location: Location) -> bool:
    cases = getattr(location, "cases", None)
    if cases is None:
        return False
    return cases.exists()


def delete_location(location: Location) -> None:
    if location_has_historical_relationships(location):
        raise LocationError(
            "This location is referenced by historical cases and cannot be deleted. Deactivate it instead.",
            code="location_in_use",
        )
    location.delete()
