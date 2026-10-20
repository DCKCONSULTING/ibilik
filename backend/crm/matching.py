from __future__ import annotations

import re

from django.db import transaction
from django.db.models import Q

from crm.models import Customer, CustomerChannelIdentity, CustomerStatus, IdentifierType


def normalize_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def normalize_phone(value: str | None) -> str:
    if not value:
        return ""
    raw = re.sub(r"[^\d+]", "", str(value).strip())
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    return f"+{digits}"


def normalize_identifier(value: str | None) -> str:
    return str(value or "").strip()


def _fill_customer_profile(customer: Customer, *, name: str, email: str, phone: str) -> Customer:
    changed = False
    if name and (not customer.name or customer.name.lower().startswith("unknown") or customer.name.startswith("Customer ")):
        customer.name = name
        changed = True
    if email and not customer.email:
        customer.email = email
        changed = True
    if phone and not customer.phone:
        customer.phone = phone
        changed = True
    if changed:
        customer.save(update_fields=["name", "email", "phone", "updated_at"])
    return customer


def _upsert_identity(
    customer: Customer,
    *,
    channel: str,
    identifier: str,
    identifier_type: str,
    display_name: str = "",
    metadata: dict | None = None,
) -> CustomerChannelIdentity | None:
    identity, created = CustomerChannelIdentity.objects.get_or_create(
        channel=channel,
        identifier_type=identifier_type,
        identifier=identifier,
        defaults={
            "customer": customer,
            "display_name": display_name,
            "metadata": metadata or {},
        },
    )
    if not created and identity.customer_id != customer.pk:
        return None
    updates = []
    if display_name and identity.display_name != display_name:
        identity.display_name = display_name
        updates.append("display_name")
    if metadata:
        merged = {**(identity.metadata or {}), **metadata}
        if merged != identity.metadata:
            identity.metadata = merged
            updates.append("metadata")
    if updates:
        updates.append("updated_at")
        identity.save(update_fields=updates)
    return identity


@transaction.atomic
def match_or_create_customer(
    *,
    name: str = "",
    email: str = "",
    phone: str = "",
    identities: list[dict] | None = None,
    created_by=None,
) -> Customer:
    """Resolve one canonical customer.

    Priority:
    1. Existing channel identity
    2. Normalized phone
    3. Normalized email
    4. Create a new customer
    """

    email = normalize_email(email)
    phone = normalize_phone(phone)
    name = (name or "").strip()
    identities = identities or []

    customer = None
    for item in identities:
        identifier = normalize_identifier(item.get("identifier"))
        identifier_type = item.get("identifier_type")
        channel = item.get("channel")
        if identifier_type == IdentifierType.PHONE:
            identifier = normalize_phone(identifier)
        elif identifier_type == IdentifierType.EMAIL:
            identifier = normalize_email(identifier)
        if not identifier or not identifier_type or not channel:
            continue
        existing = (
            CustomerChannelIdentity.objects.select_related("customer")
            .filter(channel=channel, identifier_type=identifier_type, identifier=identifier)
            .first()
        )
        if existing:
            customer = existing.customer
            break

    if customer is None and phone:
        customer = Customer.objects.filter(phone=phone).first()
        if customer is None:
            identity = (
                CustomerChannelIdentity.objects.select_related("customer")
                .filter(identifier_type=IdentifierType.PHONE, identifier=phone)
                .first()
            )
            if identity:
                customer = identity.customer

    if customer is None and email:
        customer = Customer.objects.filter(email=email).first()
        if customer is None:
            identity = (
                CustomerChannelIdentity.objects.select_related("customer")
                .filter(identifier_type=IdentifierType.EMAIL, identifier=email)
                .first()
            )
            if identity:
                customer = identity.customer

    if customer is None:
        customer = Customer.objects.create(
            name=name or (email or phone or "Unknown customer"),
            email=email,
            phone=phone,
            status=CustomerStatus.LEAD,
            created_by=created_by,
        )
    else:
        _fill_customer_profile(customer, name=name, email=email, phone=phone)

    for item in identities:
        identifier = normalize_identifier(item.get("identifier"))
        identifier_type = item.get("identifier_type")
        channel = item.get("channel")
        if identifier_type == IdentifierType.PHONE:
            identifier = normalize_phone(identifier)
        elif identifier_type == IdentifierType.EMAIL:
            identifier = normalize_email(identifier)
        if not identifier or not identifier_type or not channel:
            continue
        existing = CustomerChannelIdentity.objects.filter(
            channel=channel,
            identifier_type=identifier_type,
            identifier=identifier,
        ).first()
        if existing and existing.customer_id != customer.pk:
            continue
        _upsert_identity(
            customer,
            channel=channel,
            identifier=identifier,
            identifier_type=identifier_type,
            display_name=item.get("display_name") or name,
            metadata=item.get("metadata") or {},
        )

    return customer


def customers_matching(*, email: str = "", phone: str = "") -> list[Customer]:
    email = normalize_email(email)
    phone = normalize_phone(phone)
    query = Q()
    if email:
        query |= Q(email=email)
    if phone:
        query |= Q(phone=phone)
    if not query:
        return []
    return list(Customer.objects.filter(query))
