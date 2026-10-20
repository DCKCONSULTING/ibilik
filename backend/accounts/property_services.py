from __future__ import annotations

from datetime import time
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from accounts.authorization import (
    can_access_property,
    has_global_property_access,
    scope_queryset,
)
from accounts.models import Property, PropertyStatus, PropertyType


def parse_rate(value) -> Decimal:
    if value is None or value == "":
        raise ValueError("Rate is required.")
    if isinstance(value, bool):
        raise ValueError("Rate must be a valid decimal.")
    try:
        rate = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Rate must be a valid decimal.") from exc
    if not rate.is_finite():
        raise ValueError("Rate must be a valid decimal.")
    if rate < 0:
        raise ValueError("Rate cannot be negative.")
    quantized = rate.quantize(Decimal("0.01"))
    if quantized.copy_abs() >= Decimal("10000000000"):
        raise ValueError("Rate is too large.")
    return quantized


def parse_required_text(value, *, field: str) -> str:
    if value is None:
        raise ValueError(f"{field} is required.")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field} is required.")
    return text


def parse_optional_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_optional_email(value) -> str:
    text = parse_optional_text(value)
    if not text:
        return ""
    try:
        validate_email(text)
    except ValidationError as exc:
        raise ValueError("Email must be valid.") from exc
    return text


def parse_currency(value, *, default: str = "MYR") -> str:
    text = parse_optional_text(value).upper()
    if not text:
        return default
    if len(text) < 3 or len(text) > 8 or not text.isalpha():
        raise ValueError("Currency must be a valid code.")
    return text


def parse_timezone(value, *, default: str = "Asia/Kuala_Lumpur") -> str:
    text = parse_optional_text(value) or default
    try:
        ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Timezone is not supported.") from exc
    return text


def parse_time_value(value, *, field: str, default: time) -> time:
    if value in (None, ""):
        return default
    if isinstance(value, time):
        return value
    text = str(value).strip()
    try:
        parsed = time.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid time.") from exc
    return parsed


def parse_choice(value, choices, *, field: str, default: str | None = None) -> str:
    if value in (None, ""):
        if default is None:
            raise ValueError(f"{field} is required.")
        return default
    text = str(value).strip()
    valid = {item.value for item in choices}
    if text not in valid:
        raise ValueError(f"{field} is not supported.")
    return text


def parse_optional_int(value, *, field: str, minimum: int = 1, maximum: int | None = None):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a valid integer.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a valid integer.") from exc
    if number < minimum:
        raise ValueError(f"{field} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ValueError(f"{field} must be at most {maximum}.")
    return number


def parse_optional_decimal(value, *, field: str, minimum: Decimal | None = None, maximum: Decimal | None = None):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a valid decimal.")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a valid decimal.") from exc
    if not number.is_finite():
        raise ValueError(f"{field} must be a valid decimal.")
    if minimum is not None and number < minimum:
        raise ValueError(f"{field} is out of range.")
    if maximum is not None and number > maximum:
        raise ValueError(f"{field} is out of range.")
    return number


def parse_amenities(value) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if not isinstance(value, list):
        raise ValueError("Amenities must be a list.")
    amenities = []
    for item in value:
        text = str(item).strip()
        if text:
            amenities.append(text)
    return amenities


def parse_status_value(value) -> str:
    return parse_choice(value, PropertyStatus, field="Status", default=PropertyStatus.ACTIVE)


def apply_property_fields(property_obj: Property, payload: dict, *, creating: bool = False) -> Property:
    if "name" in payload or creating:
        property_obj.name = parse_required_text(payload.get("name"), field="Name")
    if "code" in payload or creating:
        code = parse_optional_text(payload.get("code")).upper()
        if code:
            clash = Property.objects.filter(code=code)
            if property_obj.pk:
                clash = clash.exclude(pk=property_obj.pk)
            if clash.exists():
                raise ValueError("A property with this code already exists.")
        property_obj.code = code
    if "property_type" in payload or creating:
        property_obj.property_type = parse_choice(
            payload.get("property_type"),
            PropertyType,
            field="Property type",
            default=PropertyType.HOTEL,
        )
    if "description" in payload or creating:
        property_obj.description = parse_optional_text(payload.get("description"))
    if "country" in payload or creating:
        property_obj.country = parse_optional_text(payload.get("country")) or "Malaysia"
    if "region" in payload or creating:
        property_obj.region = parse_required_text(payload.get("region"), field="Region")
    if "city" in payload or creating:
        property_obj.city = parse_required_text(payload.get("city"), field="City")
    if "address_line1" in payload or creating:
        property_obj.address_line1 = parse_optional_text(payload.get("address_line1"))
    if "address_line2" in payload or creating:
        property_obj.address_line2 = parse_optional_text(payload.get("address_line2"))
    if "postal_code" in payload or creating:
        property_obj.postal_code = parse_optional_text(payload.get("postal_code"))
    if "latitude" in payload or creating:
        property_obj.latitude = parse_optional_decimal(
            payload.get("latitude"),
            field="Latitude",
            minimum=Decimal("-90"),
            maximum=Decimal("90"),
        )
    if "longitude" in payload or creating:
        property_obj.longitude = parse_optional_decimal(
            payload.get("longitude"),
            field="Longitude",
            minimum=Decimal("-180"),
            maximum=Decimal("180"),
        )
    if "phone" in payload or creating:
        property_obj.phone = parse_optional_text(payload.get("phone"))
    if "email" in payload or creating:
        property_obj.email = parse_optional_email(payload.get("email"))
    if "website" in payload or creating:
        property_obj.website = parse_optional_text(payload.get("website"))
    if "currency" in payload or creating:
        property_obj.currency = parse_currency(payload.get("currency"))
    if "rate" in payload or "base_rate" in payload or creating:
        property_obj.rate = parse_rate(payload.get("rate", payload.get("base_rate")))
    if "status" in payload or creating:
        property_obj.status = parse_status_value(payload.get("status"))
    if "check_in_time" in payload or creating:
        property_obj.check_in_time = parse_time_value(
            payload.get("check_in_time"),
            field="Check-in time",
            default=time(15, 0),
        )
    if "check_out_time" in payload or creating:
        property_obj.check_out_time = parse_time_value(
            payload.get("check_out_time"),
            field="Check-out time",
            default=time(12, 0),
        )
    if "timezone" in payload or creating:
        property_obj.timezone = parse_timezone(payload.get("timezone"))
    if "star_rating" in payload or creating:
        property_obj.star_rating = parse_optional_int(payload.get("star_rating"), field="Star rating", minimum=1, maximum=5)
    if "amenities" in payload or creating:
        property_obj.amenities = parse_amenities(payload.get("amenities"))
    return property_obj


def properties_for_user(user: User):
    return scope_queryset(
        user,
        Property.objects.annotate(
            staff_count=Count("staff", distinct=True),
            location_count=Count("locations", distinct=True),
        ).order_by("name", "id"),
        resource="properties",
    )


def property_summary(property_obj: Property) -> dict:
    from cases.models import Case
    from locations.models import Location, LocationStatus
    from pipeline.models import PipelineStage
    from quotes.models import Quote, QuoteStatus

    now = timezone.now()
    occupied_count = (
        Case.objects.filter(
            property=property_obj,
            location_id__isnull=False,
            actual_check_in__isnull=False,
            actual_check_out__isnull=True,
        )
        .exclude(stage=PipelineStage.LOST)
        .values("location_id")
        .distinct()
        .count()
    )
    locations = Location.objects.filter(property=property_obj).aggregate(
        location_count=Count("id"),
        available_count=Count("id", filter=Q(active=True, status=LocationStatus.AVAILABLE)),
    )
    locations["occupied_count"] = occupied_count
    cases = Case.objects.filter(property=property_obj).aggregate(
        case_count=Count("id"),
        open_cases_count=Count("id", filter=~Q(stage__in=[PipelineStage.WON, PipelineStage.LOST])),
        booking_count=Count("id", filter=Q(check_in__isnull=False)),
        upcoming_bookings_count=Count("id", filter=Q(check_in__gt=now)),
    )
    quotes = Quote.objects.filter(case__property=property_obj).aggregate(
        quote_count=Count("id"),
        pending_quotes_count=Count("id", filter=Q(status=QuoteStatus.PENDING)),
    )
    return {**locations, **cases, **quotes}


def get_accessible_property(user: User, property_id: int) -> Property | None:
    property_obj = Property.objects.filter(pk=property_id).first()
    if property_obj is None:
        return None
    if not can_access_property(user, property_obj):
        raise PermissionError("You do not have access to this property.")
    return property_obj


@transaction.atomic
def create_property(
    *,
    actor: User,
    name: str,
    region: str,
    city: str,
    rate,
    **extra,
) -> Property:
    payload = {"name": name, "region": region, "city": city, "rate": rate, **extra}
    property_obj = apply_property_fields(Property(), payload, creating=True)
    property_obj.save()
    if not has_global_property_access(actor):
        property_obj.staff.add(actor)
    return property_obj


@transaction.atomic
def update_property(property_obj: Property, payload: dict | None = None, **legacy) -> Property:
    data = {**(payload or {}), **{key: value for key, value in legacy.items() if value is not None}}
    if "rate" not in data and "base_rate" in data:
        data["rate"] = data["base_rate"]
    apply_property_fields(property_obj, data, creating=False)
    property_obj.save()
    return property_obj


@transaction.atomic
def assign_property_staff(property_obj: Property, user: User, **kwargs) -> None:
    from accounts.property_staff import assign_property_staff as assign_staff

    assign_staff(property_obj, user, **kwargs)


@transaction.atomic
def remove_property_staff(property_obj: Property, user: User) -> None:
    from accounts.property_staff import remove_property_staff as remove_staff

    remove_staff(property_obj, user)
