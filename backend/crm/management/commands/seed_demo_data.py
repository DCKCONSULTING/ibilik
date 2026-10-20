"""Idempotent development seed for iBilik CRM omnichannel data.

Creates only demo-prefixed records. Existing non-demo data is left untouched.
Safe to run repeatedly.

Renames the previous Egyptian demo hotels in place so existing cases, quotes,
payments, and staff assignments keep their foreign keys.

Development-only users (created if missing, passwords not overwritten):

    admin_demo     DemoPass123!   SUPERUSER / all properties
    manager_kl     DemoPass123!   MANAGER / Kuala Lumpur only
    staff_kl       DemoPass123!   STAFF / Kuala Lumpur only
    global_staff   DemoPass123!   STAFF / all properties
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF, ROLE_SUPERUSER
from accounts.models import Property, PropertyType, UserPropertyAccess
from accounts.services import apply_property_access, create_user, initialize_access_control
from cases.activity import log_assigned, log_created
from cases.models import Case, CaseActivity, CaseFollowUp, FollowUpStatus, FollowUpType
from cases.numbering import allocate_case_number, link_conversation
from crm.models import (
    Channel,
    Conversation,
    ConversationStatus,
    Customer,
    CustomerChannelIdentity,
    CustomerStatus,
    IdentifierType,
    Message,
    MessageDirection,
    MessageStatus,
    SenderType,
)
from django.core.files.base import ContentFile

from locations.models import BedType, Location, LocationStatus, LocationType
from payments.models import Payment, PaymentAttachment, PaymentMethod, PaymentRefund, PaymentStatus, PaymentType, RefundStatus
from quotes.models import Quote, QuoteStatus
from pipeline.models import FinanceStatus, PipelineStage

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
    b"\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

DEMO_PASSWORD = "DemoPass123!"
DEMO_SOURCE = {"source": "demo"}


PROPERTY_KL = "iBilik Kuala Lumpur City Centre"
PROPERTY_PENANG = "iBilik Penang Heritage Hotel"
PROPERTY_LANGKAWI = "iBilik Langkawi Beach Resort"
PROPERTY_JB = "iBilik Johor Bahru Business Hotel"

PROPERTY_ALIASES = {
    "iBilik Cairo Downtown": PROPERTY_KL,
    "iBilik Alexandria Beach": PROPERTY_PENANG,
    "iBilik Hurghada Resort": PROPERTY_LANGKAWI,
    "gg": PROPERTY_JB,
}

USER_ALIASES = {
    "manager_cairo": "manager_kl",
    "staff_cairo": "staff_kl",
}

PHONE_ALIASES = {
    "+201001234567": "+60111234567",
    "+201002345678": "+60122345678",
    "+201003456789": "+60133456789",
    "+201004567890": "+60144567890",
    "+201005678901": "+60155678901",
    "+201006789012": "+60166789012",
    "+201007890123": "+60177890123",
    "+201008901234": "+60188901234",
    "+201009012345": "+60199012345",
    "+201000123456": "+60100123456",
}

PROPERTIES = (
    {
        "name": PROPERTY_KL,
        "code": "KL",
        "property_type": PropertyType.HOTEL,
        "description": "A city-centre hotel near Bukit Bintang with guest rooms, meeting facilities, dining, and guest services.",
        "country": "Malaysia",
        "region": "Kuala Lumpur",
        "city": "Kuala Lumpur",
        "address_line1": "Jalan Sultan Ismail, Bukit Bintang",
        "address_line2": "Kuala Lumpur, Malaysia",
        "postal_code": "50250",
        "latitude": "3.147800",
        "longitude": "101.710000",
        "phone": "+603-0000-1001",
        "email": "reservations.kl@demo.ibilik.local",
        "website": "https://demo.ibilik.local/kl",
        "currency": "MYR",
        "rate": "220.00",
        "status": "active",
        "check_in_time": "15:00",
        "check_out_time": "12:00",
        "timezone": "Asia/Kuala_Lumpur",
        "star_rating": 4,
        "amenities": ["Wi-Fi", "Restaurant", "Meeting rooms", "Parking", "24-hour reception"],
    },
    {
        "name": PROPERTY_PENANG,
        "code": "PEN",
        "property_type": PropertyType.BOUTIQUE_HOTEL,
        "description": "A heritage-style hotel in George Town serving leisure travellers, families, and business guests.",
        "country": "Malaysia",
        "region": "Penang",
        "city": "George Town",
        "address_line1": "George Town, Penang",
        "address_line2": "Malaysia",
        "postal_code": "10200",
        "latitude": "5.414100",
        "longitude": "100.328800",
        "phone": "+604-0000-2002",
        "email": "reservations.penang@demo.ibilik.local",
        "website": "https://demo.ibilik.local/penang",
        "currency": "MYR",
        "rate": "180.00",
        "status": "active",
        "check_in_time": "15:00",
        "check_out_time": "12:00",
        "timezone": "Asia/Kuala_Lumpur",
        "star_rating": 4,
        "amenities": ["Wi-Fi", "Heritage courtyard", "Restaurant", "Meeting space"],
    },
    {
        "name": PROPERTY_LANGKAWI,
        "code": "LGK",
        "property_type": PropertyType.RESORT,
        "description": "A fictional beach resort in Langkawi with rooms, villas, dining, and guest recreation facilities.",
        "country": "Malaysia",
        "region": "Kedah",
        "city": "Langkawi",
        "address_line1": "Pantai Cenang, Langkawi",
        "address_line2": "Kedah, Malaysia",
        "postal_code": "07000",
        "latitude": "6.293500",
        "longitude": "99.727800",
        "phone": "+604-0000-3003",
        "email": "reservations.langkawi@demo.ibilik.local",
        "website": "https://demo.ibilik.local/langkawi",
        "currency": "MYR",
        "rate": "320.00",
        "status": "active",
        "check_in_time": "15:00",
        "check_out_time": "12:00",
        "timezone": "Asia/Kuala_Lumpur",
        "star_rating": 5,
        "amenities": ["Wi-Fi", "Beach access", "Pool", "Spa", "Restaurant", "Villas"],
    },
    {
        "name": PROPERTY_JB,
        "code": "JHB",
        "property_type": PropertyType.BUSINESS_HOTEL,
        "description": "A fictional business hotel serving corporate travellers and short-stay guests in Johor Bahru.",
        "country": "Malaysia",
        "region": "Johor",
        "city": "Johor Bahru",
        "address_line1": "Johor Bahru, Johor",
        "address_line2": "Malaysia",
        "postal_code": "80000",
        "latitude": "1.492700",
        "longitude": "103.741400",
        "phone": "+607-0000-4004",
        "email": "reservations.jb@demo.ibilik.local",
        "website": "https://demo.ibilik.local/jb",
        "currency": "MYR",
        "rate": "160.00",
        "status": "active",
        "check_in_time": "14:00",
        "check_out_time": "12:00",
        "timezone": "Asia/Kuala_Lumpur",
        "star_rating": 3,
        "amenities": ["Wi-Fi", "Work desk rooms", "Meeting room", "Parking", "Restaurant"],
    },
)

LOCATIONS = (
    {
        "property": PROPERTY_KL,
        "name": "Deluxe Room 101",
        "code": "101",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "City-view room with queen bed",
    },
    {
        "property": PROPERTY_KL,
        "name": "Deluxe Room 102",
        "code": "102",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Standard deluxe room",
    },
    {
        "property": PROPERTY_KL,
        "name": "Deluxe Room 103",
        "code": "103",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Twin room near the lift",
    },
    {
        "property": PROPERTY_KL,
        "name": "Deluxe Room 104",
        "code": "104",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.DIRTY,
        "description": "Quiet room overlooking the courtyard",
    },
    {
        "property": PROPERTY_KL,
        "name": "Deluxe Room 105",
        "code": "105",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.MAINTENANCE,
        "description": "Bathroom refurbishment",
    },
    {
        "property": PROPERTY_KL,
        "name": "Family Room 201",
        "code": "201",
        "type": LocationType.ROOM,
        "capacity": 4,
        "status": LocationStatus.AVAILABLE,
        "description": "Family room with two beds",
    },
    {
        "property": PROPERTY_KL,
        "name": "Executive Suite 301",
        "code": "301",
        "type": LocationType.SUITE,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Executive suite with city view",
    },
    {
        "property": PROPERTY_KL,
        "name": "Meeting Room A",
        "code": "MR-A",
        "type": LocationType.MEETING_ROOM,
        "capacity": 20,
        "status": LocationStatus.AVAILABLE,
        "description": "Small corporate meeting room",
    },
    {
        "property": PROPERTY_KL,
        "name": "Restaurant Table 01",
        "code": "T01",
        "type": LocationType.TABLE,
        "capacity": 4,
        "status": LocationStatus.AVAILABLE,
        "description": "Main restaurant table",
    },
    {
        "property": PROPERTY_KL,
        "name": "Restaurant Table 02",
        "code": "T02",
        "type": LocationType.TABLE,
        "capacity": 6,
        "status": LocationStatus.AVAILABLE,
        "description": "Large dining table",
    },
    {
        "property": PROPERTY_KL,
        "name": "Reception Desk 01",
        "code": "D01",
        "type": LocationType.DESK,
        "capacity": 1,
        "status": LocationStatus.AVAILABLE,
        "description": "Main reception desk",
    },
    {
        "property": PROPERTY_KL,
        "name": "Parking Bay P01",
        "code": "P01",
        "type": LocationType.PARKING,
        "capacity": 1,
        "status": LocationStatus.AVAILABLE,
        "description": "Guest parking bay",
    },
    {
        "property": PROPERTY_PENANG,
        "name": "Heritage Room 201",
        "code": "201",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Heritage-style queen room",
    },
    {
        "property": PROPERTY_PENANG,
        "name": "Heritage Room 202",
        "code": "202",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Courtyard-facing room",
    },
    {
        "property": PROPERTY_PENANG,
        "name": "Family Room 203",
        "code": "203",
        "type": LocationType.ROOM,
        "capacity": 4,
        "status": LocationStatus.AVAILABLE,
        "description": "Family room with two beds",
    },
    {
        "property": PROPERTY_PENANG,
        "name": "Heritage Suite 301",
        "code": "301",
        "type": LocationType.SUITE,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Spacious heritage suite",
    },
    {
        "property": PROPERTY_PENANG,
        "name": "Heritage Suite 302",
        "code": "302",
        "type": LocationType.SUITE,
        "capacity": 3,
        "status": LocationStatus.AVAILABLE,
        "description": "Suite with sitting area",
    },
    {
        "property": PROPERTY_PENANG,
        "name": "Restaurant Table 01",
        "code": "T01",
        "type": LocationType.TABLE,
        "capacity": 4,
        "status": LocationStatus.AVAILABLE,
        "description": "Indoor restaurant table",
    },
    {
        "property": PROPERTY_PENANG,
        "name": "Restaurant Table 02",
        "code": "T02",
        "type": LocationType.TABLE,
        "capacity": 6,
        "status": LocationStatus.AVAILABLE,
        "description": "Family dining table",
    },
    {
        "property": PROPERTY_PENANG,
        "name": "Meeting Room B",
        "code": "MR-B",
        "type": LocationType.MEETING_ROOM,
        "capacity": 12,
        "status": LocationStatus.AVAILABLE,
        "description": "Small event and meeting space",
    },
    {
        "property": PROPERTY_LANGKAWI,
        "name": "Garden Room 301",
        "code": "301",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Garden-facing room",
    },
    {
        "property": PROPERTY_LANGKAWI,
        "name": "Garden Room 302",
        "code": "302",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Ground-floor garden room",
    },
    {
        "property": PROPERTY_LANGKAWI,
        "name": "Sea View Room 303",
        "code": "303",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Sea-view room",
    },
    {
        "property": PROPERTY_LANGKAWI,
        "name": "Beach Villa 01",
        "code": "V01",
        "type": LocationType.VILLA,
        "capacity": 4,
        "status": LocationStatus.AVAILABLE,
        "description": "Private villa near the beach",
    },
    {
        "property": PROPERTY_LANGKAWI,
        "name": "Beach Villa 02",
        "code": "V02",
        "type": LocationType.VILLA,
        "capacity": 6,
        "status": LocationStatus.AVAILABLE,
        "description": "Two-bedroom beach villa",
    },
    {
        "property": PROPERTY_LANGKAWI,
        "name": "Family Villa 03",
        "code": "V03",
        "type": LocationType.VILLA,
        "capacity": 6,
        "status": LocationStatus.AVAILABLE,
        "description": "Family villa with living area",
    },
    {
        "property": PROPERTY_LANGKAWI,
        "name": "Pool Cabana 01",
        "code": "CAB-1",
        "type": LocationType.OTHER,
        "capacity": 4,
        "status": LocationStatus.AVAILABLE,
        "description": "Poolside cabana",
    },
    {
        "property": PROPERTY_LANGKAWI,
        "name": "Restaurant Table 01",
        "code": "T01",
        "type": LocationType.TABLE,
        "capacity": 4,
        "status": LocationStatus.AVAILABLE,
        "description": "Resort restaurant table",
    },
    {
        "property": PROPERTY_LANGKAWI,
        "name": "Restaurant Table 02",
        "code": "T02",
        "type": LocationType.TABLE,
        "capacity": 6,
        "status": LocationStatus.AVAILABLE,
        "description": "Large restaurant table",
    },
    {
        "property": PROPERTY_LANGKAWI,
        "name": "Spa Room 01",
        "code": "SPA-1",
        "type": LocationType.OTHER,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Private spa treatment room",
    },
    {
        "property": PROPERTY_JB,
        "name": "Standard Room 401",
        "code": "401",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Standard king room",
    },
    {
        "property": PROPERTY_JB,
        "name": "Standard Room 402",
        "code": "402",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Business traveller room",
    },
    {
        "property": PROPERTY_JB,
        "name": "Standard Room 403",
        "code": "403",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Quiet standard room",
    },
    {
        "property": PROPERTY_JB,
        "name": "Executive Room 404",
        "code": "404",
        "type": LocationType.ROOM,
        "capacity": 2,
        "status": LocationStatus.AVAILABLE,
        "description": "Executive room with work desk",
    },
    {
        "property": PROPERTY_JB,
        "name": "Family Room 405",
        "code": "405",
        "type": LocationType.ROOM,
        "capacity": 4,
        "status": LocationStatus.AVAILABLE,
        "description": "Family room",
    },
    {
        "property": PROPERTY_JB,
        "name": "Meeting Room C",
        "code": "MR-C",
        "type": LocationType.MEETING_ROOM,
        "capacity": 16,
        "status": LocationStatus.AVAILABLE,
        "description": "Corporate meeting room",
    },
    {
        "property": PROPERTY_JB,
        "name": "Restaurant Table 01",
        "code": "T01",
        "type": LocationType.TABLE,
        "capacity": 4,
        "status": LocationStatus.AVAILABLE,
        "description": "Hotel restaurant table",
    },
    {
        "property": PROPERTY_JB,
        "name": "Parking Bay P01",
        "code": "P01",
        "type": LocationType.PARKING,
        "capacity": 1,
        "status": LocationStatus.AVAILABLE,
        "description": "Guest parking bay",
    },
)

CASE_LOCATIONS = {
    "john-confirmed-weekend": (PROPERTY_KL, "101"),
    "omar-city-break": (PROPERTY_KL, "102"),
    "john-twin": (PROPERTY_KL, "103"),
    "omar-group-quote": (PROPERTY_KL, "301"),
    "david-conference": (PROPERTY_KL, "MR-A"),
    "sarah-family": (PROPERTY_PENANG, "202"),
    "emma-summer": (PROPERTY_PENANG, "203"),
    "emma-extended": (PROPERTY_PENANG, "T02"),
    "james-diving": (PROPERTY_LANGKAWI, "302"),
    "layla-weekend": (PROPERTY_LANGKAWI, "303"),
    "james-red-sea": (PROPERTY_LANGKAWI, "V01"),
    "mohamed-corporate": (PROPERTY_LANGKAWI, "V02"),
}

CUSTOMERS = (
    {
        "key": "john",
        "name": "John Smith",
        "email": "john@example.com",
        "phone": "+60111234567",
        "status": CustomerStatus.ACTIVE,
        "property": "iBilik Kuala Lumpur City Centre",
        "notes": "Demo multi-channel guest. Website enquiry continued on WhatsApp and Facebook.",
        "identities": (
            (Channel.WEBSITE, IdentifierType.EMAIL, "john@example.com"),
            (Channel.WEBSITE, IdentifierType.PHONE, "+60111234567"),
            (Channel.WHATSAPP, IdentifierType.PHONE, "+60111234567"),
            (Channel.FACEBOOK, IdentifierType.FACEBOOK_PSID, "demo-psid-john"),
        ),
    },
    {
        "key": "sarah",
        "name": "Sarah Ahmed",
        "email": "sarah@example.com",
        "phone": "+60122345678",
        "status": CustomerStatus.ACTIVE,
        "property": "iBilik Penang Heritage Hotel",
        "notes": "Demo WhatsApp guest with AI bot history.",
        "identities": ((Channel.WHATSAPP, IdentifierType.PHONE, "+60122345678"),),
    },
    {
        "key": "mohamed",
        "name": "Mohamed Ali",
        "email": "mohamed@example.com",
        "phone": "+60133456789",
        "status": CustomerStatus.LEAD,
        "property": "iBilik Langkawi Beach Resort",
        "notes": "Demo Facebook Messenger guest.",
        "identities": ((Channel.FACEBOOK, IdentifierType.FACEBOOK_PSID, "demo-psid-mohamed"),),
    },
    {
        "key": "emma",
        "name": "Emma Wilson",
        "email": "emma@example.com",
        "phone": "+60144567890",
        "status": CustomerStatus.ACTIVE,
        "property": "iBilik Penang Heritage Hotel",
        "notes": "Demo website + WhatsApp guest.",
        "identities": (
            (Channel.WEBSITE, IdentifierType.EMAIL, "emma@example.com"),
            (Channel.WEBSITE, IdentifierType.PHONE, "+60144567890"),
            (Channel.WHATSAPP, IdentifierType.PHONE, "+60144567890"),
        ),
    },
    {
        "key": "omar",
        "name": "Omar Hassan",
        "email": "omar@example.com",
        "phone": "+60155678901",
        "status": CustomerStatus.LEAD,
        "property": "iBilik Kuala Lumpur City Centre",
        "notes": "Demo website-only guest.",
        "identities": (
            (Channel.WEBSITE, IdentifierType.EMAIL, "omar@example.com"),
            (Channel.WEBSITE, IdentifierType.PHONE, "+60155678901"),
        ),
    },
    {
        "key": "james",
        "name": "James Brown",
        "email": "james@example.com",
        "phone": "+60166789012",
        "status": CustomerStatus.ACTIVE,
        "property": "iBilik Langkawi Beach Resort",
        "notes": "Demo WhatsApp guest.",
        "identities": ((Channel.WHATSAPP, IdentifierType.PHONE, "+60166789012"),),
    },
    {
        "key": "nour",
        "name": "Nour Khaled",
        "email": "nour@example.com",
        "phone": "+60177890123",
        "status": CustomerStatus.LEAD,
        "property": "iBilik Penang Heritage Hotel",
        "notes": "Demo Facebook Messenger guest.",
        "identities": ((Channel.FACEBOOK, IdentifierType.FACEBOOK_PSID, "demo-psid-nour"),),
    },
    {
        "key": "david",
        "name": "David Miller",
        "email": "david@example.com",
        "phone": "+60188901234",
        "status": CustomerStatus.ACTIVE,
        "property": "iBilik Kuala Lumpur City Centre",
        "notes": "Demo WhatsApp guest.",
        "identities": ((Channel.WHATSAPP, IdentifierType.PHONE, "+60188901234"),),
    },
    {
        "key": "layla",
        "name": "Layla Ibrahim",
        "email": "layla@example.com",
        "phone": "+60199012345",
        "status": CustomerStatus.LEAD,
        "property": "iBilik Langkawi Beach Resort",
        "notes": "Demo website guest.",
        "identities": (
            (Channel.WEBSITE, IdentifierType.EMAIL, "layla@example.com"),
            (Channel.WEBSITE, IdentifierType.PHONE, "+60199012345"),
        ),
    },
    {
        "key": "peter",
        "name": "Peter Clark",
        "email": "peter@example.com",
        "phone": "+60100123456",
        "status": CustomerStatus.LEAD,
        "property": None,
        "notes": "Demo WhatsApp guest with no property assigned.",
        "identities": ((Channel.WHATSAPP, IdentifierType.PHONE, "+60100123456"),),
    },
)


OPPORTUNITIES = (
    {
        "key": "john-weekend",
        "customer": "john",
        "property": "iBilik Kuala Lumpur City Centre",
        "title": "Weekend booking",
        "description": "Friday and Saturday stay at iBilik Kuala Lumpur City Centre.",
        "stage": PipelineStage.NEW,
        "value": "4500.00",
        "assigned": "staff_kl",
    },
    {
        "key": "omar-city-break",
        "customer": "omar",
        "property": "iBilik Kuala Lumpur City Centre",
        "title": "City break enquiry",
        "description": "Short city stay after a website enquiry.",
        "stage": PipelineStage.NEW,
        "value": "2200.00",
        "assigned": "staff_kl",
    },
    {
        "key": "layla-weekend",
        "customer": "layla",
        "property": "iBilik Langkawi Beach Resort",
        "title": "Langkawi weekend",
        "description": "Weekend resort enquiry from the website.",
        "stage": PipelineStage.NEW,
        "value": "3600.00",
        "assigned": "global_staff",
    },
    {
        "key": "james-diving",
        "customer": "james",
        "property": "iBilik Langkawi Beach Resort",
        "title": "Diving package",
        "description": "WhatsApp enquiry about a diving weekend.",
        "stage": PipelineStage.NEW,
        "value": "5100.00",
        "assigned": "global_staff",
    },
    {
        "key": "sarah-family",
        "customer": "sarah",
        "property": "iBilik Penang Heritage Hotel",
        "title": "Family room enquiry",
        "description": "Family room for a school-holiday stay.",
        "stage": PipelineStage.QUALIFIED,
        "value": "3800.00",
        "assigned": "global_staff",
    },
    {
        "key": "emma-follow-up",
        "customer": "emma",
        "property": "iBilik Penang Heritage Hotel",
        "title": "Family follow-up",
        "description": "Qualified after WhatsApp and website contact.",
        "stage": PipelineStage.QUALIFIED,
        "value": "2900.00",
        "assigned": "global_staff",
    },
    {
        "key": "john-twin",
        "customer": "john",
        "property": "iBilik Kuala Lumpur City Centre",
        "title": "Twin room option",
        "description": "Second option while the weekend rate is reviewed.",
        "stage": PipelineStage.QUALIFIED,
        "value": "4700.00",
        "assigned": "manager_kl",
    },
    {
        "key": "omar-group-qual",
        "customer": "omar",
        "property": "iBilik Kuala Lumpur City Centre",
        "title": "Small group stay",
        "description": "Three-room enquiry now qualified.",
        "stage": PipelineStage.QUALIFIED,
        "value": "6400.00",
        "assigned": "staff_kl",
    },
    {
        "key": "mohamed-corporate",
        "customer": "mohamed",
        "property": "iBilik Langkawi Beach Resort",
        "title": "Corporate accommodation",
        "description": "Quoted corporate rooms for a field team.",
        "stage": PipelineStage.QUOTED,
        "value": "12500.00",
        "assigned": "global_staff",
    },
    {
        "key": "sarah-seaview",
        "customer": "sarah",
        "property": "iBilik Penang Heritage Hotel",
        "title": "Sea view quote",
        "description": "Quoted a heritage family room.",
        "stage": PipelineStage.QUOTED,
        "value": "6200.00",
        "assigned": "global_staff",
    },
    {
        "key": "omar-group-quote",
        "customer": "omar",
        "property": "iBilik Kuala Lumpur City Centre",
        "title": "Group booking quote",
        "description": "Formal quote for a small group city stay.",
        "stage": PipelineStage.QUOTED,
        "value": "8900.00",
        "assigned": "manager_kl",
    },
    {
        "key": "emma-extended",
        "customer": "emma",
        "property": "iBilik Penang Heritage Hotel",
        "title": "Extended stay",
        "description": "Negotiating a two-week family stay.",
        "stage": PipelineStage.NEGOTIATING,
        "value": "15400.00",
        "assigned": "global_staff",
    },
    {
        "key": "david-long-stay",
        "customer": "david",
        "property": "iBilik Kuala Lumpur City Centre",
        "title": "Long stay rate",
        "description": "Negotiating a monthly corporate rate.",
        "stage": PipelineStage.NEGOTIATING,
        "value": "9800.00",
        "assigned": "manager_kl",
    },
    {
        "key": "mohamed-overflow",
        "customer": "mohamed",
        "property": "iBilik Langkawi Beach Resort",
        "title": "Conference overflow",
        "description": "Negotiating overflow rooms for a conference.",
        "stage": PipelineStage.NEGOTIATING,
        "value": "18700.00",
        "assigned": "global_staff",
    },
    {
        "key": "david-conference",
        "customer": "david",
        "property": "iBilik Kuala Lumpur City Centre",
        "title": "Conference booking",
        "description": "Conference rooms confirmed and paid.",
        "stage": PipelineStage.WON,
        "value": "24500.00",
        "assigned": "manager_kl",
    },
    {
        "key": "emma-summer",
        "customer": "emma",
        "property": "iBilik Penang Heritage Hotel",
        "title": "Summer family stay",
        "description": "Won after a quoted family holiday.",
        "stage": PipelineStage.WON,
        "value": "11200.00",
        "assigned": "global_staff",
    },
    {
        "key": "james-red-sea",
        "customer": "james",
        "property": "iBilik Langkawi Beach Resort",
        "title": "Langkawi island package",
        "description": "Won diving and stay package.",
        "stage": PipelineStage.WON,
        "value": "16800.00",
        "assigned": "global_staff",
    },
    {
        "key": "john-confirmed-weekend",
        "customer": "john",
        "property": "iBilik Kuala Lumpur City Centre",
        "title": "Confirmed weekend stay",
        "description": "Previous weekend enquiry that converted.",
        "stage": PipelineStage.WON,
        "value": "4500.00",
        "assigned": "staff_kl",
    },
    {
        "key": "nour-room",
        "customer": "nour",
        "property": "iBilik Penang Heritage Hotel",
        "title": "Room enquiry",
        "description": "Guest chose another hotel.",
        "stage": PipelineStage.LOST,
        "value": "1800.00",
        "assigned": "global_staff",
    },
    {
        "key": "layla-festival",
        "customer": "layla",
        "property": "iBilik Langkawi Beach Resort",
        "title": "Festival dates",
        "description": "Lost because the requested dates were sold out.",
        "stage": PipelineStage.LOST,
        "value": "2700.00",
        "assigned": "global_staff",
    },
    {
        "key": "peter-budget",
        "customer": "peter",
        "property": None,
        "title": "Budget request",
        "description": "Unassigned enquiry that did not convert.",
        "stage": PipelineStage.LOST,
        "value": "900.00",
        "assigned": None,
    },
)


OPPORTUNITY_CONVERSATIONS = {
    "john-weekend": "john-website",
    "omar-city-break": "omar-website",
    "layla-weekend": "layla-website",
    "james-diving": "james-whatsapp",
    "sarah-family": "sarah-whatsapp",
    "emma-follow-up": "emma-whatsapp",
    "john-twin": "john-whatsapp",
    "omar-group-qual": "omar-website",
    "mohamed-corporate": "mohamed-facebook",
    "sarah-seaview": "sarah-whatsapp",
    "omar-group-quote": "omar-website",
    "emma-extended": "emma-website",
    "david-long-stay": "david-whatsapp",
    "mohamed-overflow": "mohamed-facebook",
    "david-conference": "david-whatsapp",
    "emma-summer": "emma-website",
    "james-red-sea": "james-whatsapp",
    "john-confirmed-weekend": "john-facebook",
    "nour-room": "nour-facebook",
    "layla-festival": "layla-website",
    "peter-budget": "peter-whatsapp",
}


CASE_FOLLOW_UPS = {
    "john-weekend": (
        {
            "type": FollowUpType.CALL_CUSTOMER,
            "title": "Call customer",
            "description": "Confirm dates for the Kuala Lumpur family room request.",
            "hours": 2,
            "status": FollowUpStatus.PENDING,
        },
        {
            "type": FollowUpType.INTERNAL_REVIEW,
            "title": "Internal rate review",
            "description": "Cancelled after the guest asked for WhatsApp instead.",
            "hours": -2,
            "status": FollowUpStatus.CANCELLED,
        },
    ),
    "sarah-family": (
        {
            "type": FollowUpType.SEND_QUOTE,
            "title": "Send quote",
            "description": "Send the family room quote for Penang.",
            "hours": 4,
            "status": FollowUpStatus.PENDING,
        },
    ),
    "mohamed-corporate": (
        {
            "type": FollowUpType.FOLLOW_UP,
            "title": "Follow up quote",
            "description": "Check whether the corporate team accepted the quote.",
            "hours": 24,
            "status": FollowUpStatus.PENDING,
        },
    ),
    "emma-extended": (
        {
            "type": FollowUpType.FOLLOW_UP,
            "title": "Customer decision",
            "description": "Call Emma about the two-week family stay.",
            "hours": 6,
            "status": FollowUpStatus.PENDING,
        },
    ),
    "john-confirmed-weekend": (
        {
            "type": FollowUpType.PAYMENT_FOLLOW_UP,
            "title": "Send payment reminder",
            "description": "Remind John about the remaining weekend-stay balance.",
            "hours": 10,
            "status": FollowUpStatus.PENDING,
        },
    ),
    "david-conference": (
        {
            "type": FollowUpType.PAYMENT_FOLLOW_UP,
            "title": "Move to Finance",
            "description": "Send the won conference booking to finance.",
            "hours": 8,
            "status": FollowUpStatus.PENDING,
        },
    ),
    "omar-city-break": (
        {
            "type": FollowUpType.CHECK_AVAILABILITY,
            "title": "Check availability",
            "description": "Confirm weekend rooms at iBilik Kuala Lumpur City Centre.",
            "hours": -6,
            "status": FollowUpStatus.PENDING,
        },
    ),
    "john-twin": (
        {
            "type": FollowUpType.REQUEST_INFORMATION,
            "title": "Request information",
            "description": "Ask John whether twin or double is preferred.",
            "hours": 12,
            "status": FollowUpStatus.COMPLETED,
        },
    ),
    "layla-weekend": (
        {
            "type": FollowUpType.SEND_QUOTE,
            "title": "Send Langkawi quote",
            "description": "Website guest waiting for a weekend resort quote.",
            "hours": 26,
            "status": FollowUpStatus.PENDING,
        },
    ),
    "james-diving": (
        {
            "type": FollowUpType.CALL_CUSTOMER,
            "title": "Call about diving dates",
            "description": "WhatsApp guest asked about a diving weekend.",
            "hours": -20,
            "status": FollowUpStatus.PENDING,
        },
    ),
    "nour-room": (
        {
            "type": FollowUpType.FOLLOW_UP,
            "title": "Lost-lead callback",
            "description": "Facebook guest chose another hotel; keep a closing note.",
            "hours": -48,
            "status": FollowUpStatus.COMPLETED,
        },
    ),
    "peter-budget": (
        {
            "type": FollowUpType.OTHER,
            "title": "Budget follow-up",
            "description": "Unassigned WhatsApp enquiry still needs a reply.",
            "hours": 3,
            "status": FollowUpStatus.PENDING,
        },
    ),
}


CASE_STAYS = {
    "emma-summer": {"check_in": -2, "check_out": 46},
    "omar-city-break": {"check_in": -18, "check_out": 22},
    "sarah-family": {"check_in": -8, "check_out": 28},
    "james-diving": {"check_in": -6, "check_out": 18},
    "john-twin": {"check_in": 12, "check_out": 60},
    "john-confirmed-weekend": {"check_in": 9, "check_out": 57},
    "omar-group-quote": {"check_in": 36, "check_out": 84},
    "emma-extended": {"check_in": 20, "check_out": 68},
    "layla-weekend": {"check_in": 16, "check_out": 64},
    "mohamed-corporate": {"check_in": 40, "check_out": 88},
    "david-conference": {"check_in": 26, "check_out": 74},
    "james-red-sea": {"check_in": 80, "check_out": 152},
}

CASE_WORKFLOW_HOURS = {
    "mohamed-corporate": {"quoted": -10},
    "sarah-seaview": {"quoted": 6},
    "omar-group-quote": {"quoted": -30},
    "emma-extended": {"quoted": -40},
    "david-long-stay": {"quoted": -16},
    "mohamed-overflow": {"quoted": 20},
    "david-conference": {"quoted": -72, "approved": -48, "finance": -8},
    "emma-summer": {"quoted": -50, "approved": -20},
    "james-red-sea": {"quoted": -36, "approved": -12, "finance": 30},
    "john-confirmed-weekend": {"quoted": -28, "approved": -6},
}

CASE_PAYMENTS = {
    "john-confirmed-weekend": (
        {
            "number": "PAY-1001",
            "type": PaymentType.DEPOSIT,
            "amount": "1500.00",
            "method": PaymentMethod.BANK_TRANSFER,
            "hours": -48,
            "status": PaymentStatus.APPROVED,
            "proof": True,
            "notes": "Booking deposit received.",
        },
        {
            "number": "PAY-1002",
            "type": PaymentType.PAYMENT,
            "amount": "3000.00",
            "method": PaymentMethod.BANK_TRANSFER,
            "hours": 14,
            "status": PaymentStatus.PENDING,
            "notes": "Remaining balance expected.",
        },
    ),
    "david-conference": (
        {
            "number": "PAY-1003",
            "type": PaymentType.DEPOSIT,
            "amount": "5000.00",
            "method": PaymentMethod.BANK_TRANSFER,
            "hours": -72,
            "status": PaymentStatus.APPROVED,
            "proof": True,
            "notes": "Conference deposit.",
            "refunds": (
                {
                    "number": "REF-1001",
                    "amount": "2000.00",
                    "status": RefundStatus.COMPLETED,
                    "reason": "Room count reduced after confirmation.",
                },
                {
                    "number": "REF-1002",
                    "amount": "1000.00",
                    "status": RefundStatus.PENDING_APPROVAL,
                    "reason": "Partial cancellation of meeting rooms.",
                },
            ),
        },
        {
            "number": "PAY-1004",
            "type": PaymentType.PAYMENT,
            "amount": "10000.00",
            "method": PaymentMethod.CREDIT_CARD,
            "hours": -24,
            "status": PaymentStatus.APPROVED,
            "proof": True,
        },
        {
            "number": "PAY-1005",
            "type": PaymentType.PAYMENT,
            "amount": "9500.00",
            "method": PaymentMethod.BANK_TRANSFER,
            "hours": 36,
            "status": PaymentStatus.PENDING_APPROVAL,
            "proof": True,
        },
    ),
    "emma-summer": (
        {
            "number": "PAY-1006",
            "type": PaymentType.PAYMENT,
            "amount": "11200.00",
            "method": PaymentMethod.ONLINE,
            "hours": -4,
            "status": PaymentStatus.APPROVED,
            "proof": True,
        },
    ),
    "david-long-stay": (
        {
            "number": "PAY-1007",
            "type": PaymentType.DEPOSIT,
            "amount": "2000.00",
            "method": PaymentMethod.CASH,
            "hours": -30,
            "status": PaymentStatus.PENDING,
            "notes": "Overdue deposit.",
        },
        {
            "number": "PAY-1008",
            "type": PaymentType.PAYMENT,
            "amount": "7800.00",
            "method": PaymentMethod.BANK_TRANSFER,
            "hours": 50,
            "status": PaymentStatus.PENDING,
        },
    ),
    "james-red-sea": (
        {
            "number": "PAY-1009",
            "type": PaymentType.PAYMENT,
            "amount": "8000.00",
            "method": PaymentMethod.BANK_TRANSFER,
            "hours": -12,
            "status": PaymentStatus.REJECTED,
            "proof": True,
            "rejection_reason": "Screenshot does not match the transfer amount.",
        },
        {
            "number": "PAY-1010",
            "type": PaymentType.DEPOSIT,
            "amount": "4000.00",
            "method": PaymentMethod.BANK_TRANSFER,
            "hours": 70,
            "status": PaymentStatus.PENDING,
        },
    ),
    "emma-extended": (
        {
            "number": "PAY-1011",
            "type": PaymentType.DEPOSIT,
            "amount": "4000.00",
            "method": PaymentMethod.BANK_TRANSFER,
            "hours": 20,
            "status": PaymentStatus.PENDING_APPROVAL,
            "proof": True,
            "notes": "Deposit proof awaiting review.",
        },
    ),
}

CASE_QUOTES = {
    "mohamed-corporate": {
        "number": "QT-1001",
        "status": QuoteStatus.PENDING,
        "valid_hours": 80,
        "notes": "Corporate room rate for the field team.",
    },
    "sarah-seaview": {
        "number": "QT-1002",
        "status": QuoteStatus.PENDING,
        "valid_hours": -20,
        "notes": "Heritage family room quote. Validity has passed.",
    },
    "omar-group-quote": {
        "number": "QT-1003",
        "status": QuoteStatus.PENDING,
        "valid_hours": 48,
        "notes": "Group city-stay package.",
    },
    "emma-extended": {
        "number": "QT-1004",
        "status": QuoteStatus.ACCEPTED,
        "valid_hours": 36,
        "notes": "Two-week family stay accepted for negotiation.",
    },
    "david-long-stay": {
        "number": "QT-1005",
        "status": QuoteStatus.ACCEPTED,
        "valid_hours": 24,
        "notes": "Monthly corporate rate.",
    },
    "mohamed-overflow": {
        "number": "QT-1006",
        "status": QuoteStatus.ACCEPTED,
        "valid_hours": 60,
        "notes": "Conference overflow rooms.",
    },
    "david-conference": {
        "number": "QT-1007",
        "status": QuoteStatus.ACCEPTED,
        "valid_hours": -10,
        "notes": "Conference booking confirmed.",
    },
    "emma-summer": {
        "number": "QT-1008",
        "status": QuoteStatus.ACCEPTED,
        "valid_hours": 12,
        "notes": "Summer family holiday.",
    },
    "james-red-sea": {
        "number": "QT-1009",
        "status": QuoteStatus.ACCEPTED,
        "valid_hours": 72,
        "notes": "Diving and stay package.",
    },
    "john-confirmed-weekend": {
        "number": "QT-1010",
        "status": QuoteStatus.ACCEPTED,
        "valid_hours": 16,
        "notes": "Weekend stay confirmation.",
    },
    "nour-room": {
        "number": "QT-1011",
        "status": QuoteStatus.REJECTED,
        "valid_hours": -30,
        "notes": "Guest chose another hotel.",
    },
    "layla-festival": {
        "number": "QT-1012",
        "status": QuoteStatus.REJECTED,
        "valid_hours": -18,
        "notes": "Requested festival dates were sold out.",
    },
}


def _messages(*rows):
    return rows


CONVERSATIONS = (
    {
        "key": "john-website",
        "customer": "john",
        "channel": Channel.WEBSITE,
        "property": "iBilik Kuala Lumpur City Centre",
        "subject": "Weekend rate enquiry",
        "unread": 0,
        "messages": _messages(
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "I want to know the rate for this weekend."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "Thanks John, we received your website enquiry."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Do you have twin rooms as well as doubles?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "Yes, both room types are available this weekend."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Great, I will wait for the rate on WhatsApp."),
        ),
    },
    {
        "key": "john-whatsapp",
        "customer": "john",
        "channel": Channel.WHATSAPP,
        "property": "iBilik Kuala Lumpur City Centre",
        "subject": "Weekend rate follow-up",
        "unread": 1,
        "messages": _messages(
            (SenderType.BOT, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "Hello John, I'd be happy to help with your website enquiry."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Do you have availability this weekend?"),
            (SenderType.BOT, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "Let me check that for you."),
            (SenderType.BOT, MessageDirection.OUTBOUND, MessageStatus.READ, "Yes, Friday and Saturday are available at iBilik Kuala Lumpur City Centre."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "Hello John, regarding your enquiry, the weekend rate is RM 220."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "Perfect, can you hold a double room?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "I can hold it for 24 hours. Shall I proceed?"),
        ),
    },
    {
        "key": "john-facebook",
        "customer": "john",
        "channel": Channel.FACEBOOK,
        "property": "iBilik Kuala Lumpur City Centre",
        "subject": "Facebook weekend question",
        "unread": 1,
        "messages": _messages(
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "Hi, I also messaged on the website. Is parking included?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "Yes John, on-site parking is included with the weekend rate."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "And late checkout?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "Late checkout until 14:00 is available on Sunday."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "Thanks, I will confirm on WhatsApp."),
        ),
    },
    {
        "key": "sarah-whatsapp",
        "customer": "sarah",
        "channel": Channel.WHATSAPP,
        "property": "iBilik Penang Heritage Hotel",
        "subject": "Penang family stay",
        "unread": 0,
        "messages": _messages(
            (SenderType.BOT, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "Hello Sarah, how can I help you today?"),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "I need a family room in George Town."),
            (SenderType.BOT, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "iBilik Penang Heritage Hotel has family rooms from RM 180 per night."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Is breakfast included?"),
            (SenderType.BOT, MessageDirection.OUTBOUND, MessageStatus.READ, "Yes, breakfast is included for two adults and two children."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "I can reserve a heritage family room for next Thursday."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Please reserve it. We arrive after 18:00."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "Reserved. I have noted the late arrival."),
        ),
    },
    {
        "key": "mohamed-facebook",
        "customer": "mohamed",
        "channel": Channel.FACEBOOK,
        "property": "iBilik Langkawi Beach Resort",
        "subject": "Langkawi diving trip",
        "unread": 1,
        "messages": _messages(
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "Do you arrange diving trips from the resort?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "Yes, we have daily boat trips from iBilik Langkawi Beach Resort."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "How many nights do you recommend?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "Most guests stay three nights. The rate is RM 320 per night."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "Can I get a quote for 12-15 October?"),
        ),
    },
    {
        "key": "emma-website",
        "customer": "emma",
        "channel": Channel.WEBSITE,
        "property": "iBilik Penang Heritage Hotel",
        "subject": "Website booking question",
        "unread": 0,
        "messages": _messages(
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "Hello, I would like to know your room rates."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "Hi Emma, iBilik Penang Heritage Hotel starts at RM 180 per night."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Is a courtyard room guaranteed?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "A courtyard heritage room can be guaranteed if booked at least 7 days ahead."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "I will continue on WhatsApp with dates."),
        ),
    },
    {
        "key": "emma-whatsapp",
        "customer": "emma",
        "channel": Channel.WHATSAPP,
        "property": "iBilik Penang Heritage Hotel",
        "subject": "Dates for Penang",
        "unread": 0,
        "messages": _messages(
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Hi, following my website form. 20-23 November please."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "Those dates are open. A heritage double is RM 180 per night."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Can I pay a deposit by card?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "Yes. I can send a payment link after you confirm."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Please send the link tomorrow morning."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.READ, "I will send it after 09:00."),
        ),
    },
    {
        "key": "omar-website",
        "customer": "omar",
        "channel": Channel.WEBSITE,
        "property": "iBilik Kuala Lumpur City Centre",
        "subject": "Business stay in Kuala Lumpur",
        "unread": 1,
        "messages": _messages(
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "I need a quiet room near downtown for two nights."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "iBilik Kuala Lumpur City Centre is a good fit. Rate is RM 220 per night."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Do you have desks in the rooms?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "Yes, every room has a work desk and fast Wi-Fi."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "Invoice in a company name is required."),
        ),
    },
    {
        "key": "james-whatsapp",
        "customer": "james",
        "channel": Channel.WHATSAPP,
        "property": "iBilik Langkawi Beach Resort",
        "subject": "Langkawi couples stay",
        "unread": 0,
        "messages": _messages(
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Looking for a quiet room away from the pool."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "We can offer a garden-view room at RM 320 per night."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Is there a spa?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "Yes, the spa is complimentary for staying guests."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Book 3-6 December please."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.READ, "Reserved for 3-6 December."),
        ),
    },
    {
        "key": "nour-facebook",
        "customer": "nour",
        "channel": Channel.FACEBOOK,
        "property": "iBilik Penang Heritage Hotel",
        "subject": "Short Penang break",
        "unread": 1,
        "messages": _messages(
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "Is this hotel available next weekend?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "Yes Nour, next weekend is open at iBilik Penang Heritage Hotel."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "What is included in RM 180?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "Breakfast, Wi-Fi, and heritage-area walking access."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "Can I bring a small pet?"),
        ),
    },
    {
        "key": "david-whatsapp",
        "customer": "david",
        "channel": Channel.WHATSAPP,
        "property": "iBilik Kuala Lumpur City Centre",
        "subject": "KLIA airport transfer",
        "unread": 0,
        "messages": _messages(
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Do you offer airport pickup?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "Yes, KLIA transfers are RM 80 each way."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "I land at 22:40 on Friday."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "I can schedule a driver. Room rate is RM 220."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Please add the transfer to the booking."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.FAILED, "Unable to send the confirmation just now. Please try again."),
        ),
    },
    {
        "key": "layla-website",
        "customer": "layla",
        "channel": Channel.WEBSITE,
        "property": "iBilik Langkawi Beach Resort",
        "subject": "Langkawi family quote",
        "unread": 0,
        "messages": _messages(
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "We are four adults looking for two rooms."),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "Two connecting rooms are available at RM 320 each."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Any discount for 5 nights?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "A 10 percent stay discount applies from the fourth night."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Please send a written quote to this email."),
        ),
    },
    {
        "key": "peter-whatsapp",
        "customer": "peter",
        "channel": Channel.WHATSAPP,
        "property": None,
        "subject": "Unassigned property enquiry",
        "unread": 1,
        "messages": _messages(
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "Which of your hotels is closest to KLCC?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.SENT, "iBilik Kuala Lumpur City Centre is the closest. I have not assigned a property yet."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.READ, "Can you compare Kuala Lumpur and Penang briefly?"),
            (SenderType.STAFF, MessageDirection.OUTBOUND, MessageStatus.DELIVERED, "Kuala Lumpur is central. Penang is a heritage stay at a lower rate."),
            (SenderType.CUSTOMER, MessageDirection.INBOUND, MessageStatus.RECEIVED, "I will decide tomorrow."),
        ),
    },
)


def _alias_usernames(username):
    aliases = [old for old, new in USER_ALIASES.items() if new == username]
    return [username, *aliases]


def _sync_demo_user(*, username, first_name, last_name, role, property_access, property_ids, actor):
    existing = None
    for candidate in _alias_usernames(username):
        existing = User.objects.filter(username=candidate).first()
        if existing:
            break
    if existing:
        existing.username = username
        existing.first_name = first_name
        existing.last_name = last_name
        existing.email = f"{username}@demo.ibilik.local"
        existing.save(update_fields=["username", "first_name", "last_name", "email"])
        apply_property_access(
            existing,
            actor=actor,
            mode=property_access,
            property_ids=property_ids,
            allow_self_change=True,
        )
        return existing, False
    user = create_user(
        username=username,
        password=DEMO_PASSWORD,
        first_name=first_name,
        last_name=last_name,
        email=f"{username}@demo.ibilik.local",
        role=role,
        property_access=property_access,
        property_ids=property_ids,
        actor=actor,
    )
    return user, True


def _apply_property_spec(property_obj, spec):
    from accounts.property_services import apply_property_fields

    apply_property_fields(property_obj, spec, creating=False)
    property_obj.save()
    return property_obj


def _upsert_property(spec):
    name = spec["name"]
    property_obj = Property.objects.filter(name=name).first()
    aliases = [old for old, new in PROPERTY_ALIASES.items() if new == name]
    aliased = list(Property.objects.filter(name__in=aliases))
    created = False
    if property_obj is None and aliased:
        property_obj = aliased.pop(0)
        property_obj.name = name
    if property_obj is None:
        property_obj = Property(name=name, region=spec["region"], city=spec["city"], rate=spec["rate"])
        created = True
    _apply_property_spec(property_obj, spec)
    for extra in aliased:
        if extra.pk == property_obj.pk:
            continue
        extra.cases.update(property=property_obj)
        extra.interested_customers.update(property=property_obj)
        extra.conversations.update(property=property_obj)
        extra.opportunities.update(property=property_obj)
        extra.locations.update(property=property_obj)
        extra.delete()
    return property_obj, created


def _location_operational_fields(spec, property_obj):
    capacity = spec.get("capacity")
    code = spec.get("code") or ""
    name = spec["name"].lower()
    loc_type = spec["type"]
    floor = ""
    if code.isdigit() and len(code) >= 3:
        floor = str(int(code[0]))
    bed_type = ""
    bed_count = None
    if loc_type in {LocationType.ROOM, LocationType.SUITE, LocationType.VILLA, LocationType.APARTMENT}:
        if "twin" in name:
            bed_type, bed_count = BedType.TWIN, 2
        elif "family" in name or "villa" in name:
            bed_type, bed_count = BedType.QUEEN, 2
        elif "king" in name or "executive" in name or "suite" in name:
            bed_type, bed_count = BedType.KING, 1
        else:
            bed_type, bed_count = BedType.QUEEN, 1
    size = {
        LocationType.ROOM: "28.00",
        LocationType.SUITE: "48.00",
        LocationType.VILLA: "85.00",
        LocationType.APARTMENT: "62.00",
        LocationType.MEETING_ROOM: "36.00",
        LocationType.TABLE: "4.00",
        LocationType.PARKING: "12.00",
        LocationType.DESK: "3.00",
        LocationType.OTHER: "16.00",
    }.get(loc_type)
    return {
        "max_adults": capacity,
        "max_children": 1 if capacity and capacity >= 3 else (0 if capacity else None),
        "floor": floor,
        "bed_type": bed_type,
        "bed_count": bed_count,
        "base_rate": spec.get("base_rate") or property_obj.rate,
        "currency": "MYR",
        "is_bookable": loc_type != LocationType.DESK,
        "amenities": spec.get("amenities") or [],
        "size_sqm": spec.get("size_sqm") or size,
    }


def _remap_demo_phones():
    from crm.models import CustomerChannelIdentity

    for old, new in PHONE_ALIASES.items():
        Customer.objects.filter(phone=old).update(phone=new)
        CustomerChannelIdentity.objects.filter(identifier=old).update(identifier=new)


def _cleanup_stale_locations(properties):
    desired = {}
    for spec in LOCATIONS:
        desired.setdefault(spec["property"], set()).add(spec["code"])
    for name, property_obj in properties.items():
        keep = desired.get(name, set())
        stale = Location.objects.filter(property=property_obj).exclude(code__in=keep)
        Case.objects.filter(location__in=stale).update(location=None)
        stale.delete()


def _remove_obsolete_properties(keep_names):
    obsolete = set(PROPERTY_ALIASES) | {"gg"}
    leftovers = Property.objects.exclude(name__in=keep_names).filter(name__in=obsolete)
    leftovers.delete()


class Command(BaseCommand):
    help = "Seed idempotent iBilik CRM demo customers, conversations, and messages."

    @transaction.atomic
    def handle(self, *args, **options):
        initialize_access_control()
        counts = {
            "properties": 0,
            "customers": 0,
            "identities": 0,
            "conversations": 0,
            "messages": 0,
            "users": 0,
            "cases": 0,
            "follow_ups": 0,
            "quotes": 0,
            "payments": 0,
            "locations": 0,
        }

        _remap_demo_phones()
        CaseFollowUp.objects.filter(title__in=("Send Hurghada quote",)).delete()
        Quote.objects.filter(currency="EGP").update(currency="MYR")
        Payment.objects.filter(currency="EGP").update(currency="MYR")

        properties = {}
        for spec in PROPERTIES:
            property_obj, created = _upsert_property(spec)
            properties[spec["name"]] = property_obj
            counts["properties"] += int(created)
        _remove_obsolete_properties(set(properties))

        locations = {}
        for spec in LOCATIONS:
            property_obj = properties[spec["property"]]
            extra = _location_operational_fields(spec, property_obj)
            defaults = {
                "name": spec["name"],
                "location_type": spec["type"],
                "description": spec.get("description") or "",
                "capacity": spec.get("capacity"),
                "status": spec["status"],
                "active": spec.get("active", True),
                **extra,
            }
            location, created = Location.objects.get_or_create(
                property=property_obj,
                code=spec["code"],
                defaults=defaults,
            )
            if not created:
                for field, value in defaults.items():
                    setattr(location, field, value)
                location.save()
            locations[(spec["property"], spec["code"])] = location
            counts["locations"] += int(created)
        _cleanup_stale_locations(properties)

        actor = User.objects.filter(is_superuser=True).first()
        if actor is None:
            actor = User.objects.create_superuser(
                username="admin_demo",
                email="admin_demo@demo.ibilik.local",
                password=DEMO_PASSWORD,
                first_name="Siti",
                last_name="Hajar",
            )
            counts["users"] += 1
        else:
            admin = User.objects.filter(username="admin_demo").first()
            if admin is None:
                create_user(
                    username="admin_demo",
                    password=DEMO_PASSWORD,
                    first_name="Siti",
                    last_name="Hajar",
                    email="admin_demo@demo.ibilik.local",
                    role=ROLE_SUPERUSER,
                    actor=actor,
                )
                counts["users"] += 1
            else:
                admin.first_name = "Siti"
                admin.last_name = "Hajar"
                admin.save(update_fields=["first_name", "last_name"])

        kl_id = properties[PROPERTY_KL].pk
        for username, first_name, last_name, role, access, property_ids in (
            ("manager_kl", "Aiman", "Rahman", ROLE_MANAGER, UserPropertyAccess.Mode.ASSIGNED, [kl_id]),
            ("staff_kl", "Nur", "Aisyah", ROLE_STAFF, UserPropertyAccess.Mode.ASSIGNED, [kl_id]),
            ("global_staff", "Daniel", "Tan", ROLE_STAFF, UserPropertyAccess.Mode.GLOBAL, []),
        ):
            user, created = _sync_demo_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                role=role,
                property_access=access,
                property_ids=property_ids,
                actor=actor,
            )
            counts["users"] += int(created)
            if access == UserPropertyAccess.Mode.ASSIGNED:
                properties[PROPERTY_KL].staff.add(user)

        staff_user = User.objects.filter(username="global_staff").first() or actor

        customers = {}
        for spec in CUSTOMERS:
            customer, created = Customer.objects.get_or_create(
                email=spec["email"],
                defaults={
                    "name": spec["name"],
                    "phone": spec["phone"],
                    "status": spec["status"],
                    "notes": spec["notes"],
                    "property": properties.get(spec["property"]) if spec["property"] else None,
                    "created_by": actor,
                },
            )
            if not created:
                customer.name = spec["name"]
                customer.phone = spec["phone"]
                customer.status = spec["status"]
                if spec["notes"] and not customer.notes:
                    customer.notes = spec["notes"]
                if spec["property"]:
                    customer.property = properties[spec["property"]]
                customer.save()
            customers[spec["key"]] = customer
            counts["customers"] += int(created)

            for channel, identifier_type, identifier in spec["identities"]:
                identity, identity_created = CustomerChannelIdentity.objects.get_or_create(
                    channel=channel,
                    identifier_type=identifier_type,
                    identifier=identifier,
                    defaults={
                        "customer": customer,
                        "display_name": spec["name"],
                        "metadata": DEMO_SOURCE,
                    },
                )
                if identity_created:
                    counts["identities"] += 1
                elif identity.customer_id == customer.pk and identity.metadata.get("source") != "demo":
                    identity.metadata = {**(identity.metadata or {}), **DEMO_SOURCE}
                    identity.save(update_fields=["metadata", "updated_at"])

        now = timezone.now()
        seeded_conversations = {}
        for index, spec in enumerate(CONVERSATIONS):
            conversation_id = f"demo-conversation-{spec['key']}"
            customer = customers[spec["customer"]]
            property_obj = properties.get(spec["property"]) if spec["property"] else None
            conversation, created = Conversation.objects.get_or_create(
                channel=spec["channel"],
                external_conversation_id=conversation_id,
                defaults={
                    "customer": customer,
                    "property": property_obj,
                    "subject": spec["subject"],
                    "status": ConversationStatus.OPEN,
                    "unread_count": spec["unread"],
                },
            )
            if created:
                counts["conversations"] += 1
            else:
                conversation.customer = customer
                conversation.property = property_obj
                conversation.subject = spec["subject"]
                conversation.unread_count = spec["unread"]
                conversation.save()

            last_message = None
            for message_index, (sender_type, direction, status, content) in enumerate(spec["messages"], start=1):
                occurred = now - timedelta(hours=36 - index * 2) + timedelta(minutes=message_index * 7)
                external_message_id = f"demo-message-{spec['key']}-{message_index:03d}"
                is_staff = sender_type == SenderType.STAFF
                is_bot = sender_type == SenderType.BOT
                sender_name = "AI Bot" if is_bot else ("Staff" if is_staff else customer.name)
                message, message_created = Message.objects.get_or_create(
                    channel=spec["channel"],
                    external_message_id=external_message_id,
                    defaults={
                        "conversation": conversation,
                        "direction": direction,
                        "sender_type": sender_type,
                        "sender_name": sender_name,
                        "sender_identifier": staff_user.username if is_staff else customer.phone or customer.email,
                        "content": content,
                        "status": status,
                        "error_message": "Demo outbound send failed." if status == MessageStatus.FAILED else "",
                        "created_by": staff_user if is_staff else None,
                        "received_at": occurred if direction == MessageDirection.INBOUND else None,
                        "sent_at": occurred if direction == MessageDirection.OUTBOUND else None,
                        "raw_event": DEMO_SOURCE,
                    },
                )
                Message.objects.filter(pk=message.pk).update(
                    created_at=occurred,
                    received_at=occurred if direction == MessageDirection.INBOUND else None,
                    sent_at=occurred if direction == MessageDirection.OUTBOUND else None,
                    sender_type=sender_type,
                    sender_name=sender_name,
                    content=content,
                    status=status,
                )
                if message_created:
                    counts["messages"] += 1
                last_message = Message.objects.get(pk=message.pk)

            if last_message:
                conversation.last_message_preview = last_message.content[:500]
                conversation.last_message_at = last_message.created_at
                conversation.save(update_fields=["last_message_preview", "last_message_at", "updated_at"])
            seeded_conversations[spec["key"]] = conversation

        assignees = {
            "staff_kl": User.objects.filter(username="staff_kl").first(),
            "manager_kl": User.objects.filter(username="manager_kl").first(),
            "global_staff": staff_user,
        }
        for index, spec in enumerate(OPPORTUNITIES):
            occurred = now - timedelta(hours=8 + index * 3)
            conversation = seeded_conversations.get(OPPORTUNITY_CONVERSATIONS.get(spec["key"]))
            original_request = spec["description"]
            source = ""
            originating_message = None
            if conversation is not None:
                source = conversation.channel
                first_inbound = (
                    Message.objects.filter(
                        conversation=conversation,
                        direction=MessageDirection.INBOUND,
                        sender_type=SenderType.CUSTOMER,
                    )
                    .order_by("created_at", "id")
                    .first()
                )
                if first_inbound is not None:
                    original_request = first_inbound.content
                    originating_message = first_inbound
            closed_at = occurred if spec["stage"] in {PipelineStage.WON, PipelineStage.LOST} else None
            case = Case.objects.filter(external_key=f"demo-opportunity-{spec['key']}").first()
            created = case is None
            if created:
                sequence, case_number = allocate_case_number()
                case = Case.objects.create(
                    sequence=sequence,
                    case_number=case_number,
                    external_key=f"demo-opportunity-{spec['key']}",
                    customer=customers[spec["customer"]],
                    property=properties.get(spec["property"]) if spec["property"] else None,
                    originating_conversation=conversation,
                    originating_message=originating_message,
                    title=spec["title"],
                    description=spec["description"],
                    original_request=original_request,
                    source=source,
                    stage=spec["stage"],
                    value=spec["value"],
                    assigned_to=assignees.get(spec["assigned"]),
                    created_by=actor,
                    closed_at=closed_at,
                )
                counts["cases"] += 1
                log_created(case, actor=actor)
                if case.assigned_to_id:
                    log_assigned(case, actor=actor)
            else:
                case.customer = customers[spec["customer"]]
                case.property = properties.get(spec["property"]) if spec["property"] else None
                case.originating_conversation = conversation
                if originating_message is not None and case.originating_message_id is None:
                    case.originating_message = originating_message
                case.title = spec["title"]
                case.description = spec["description"]
                if not case.original_request:
                    case.original_request = original_request
                if not case.source:
                    case.source = source
                case.stage = spec["stage"]
                case.value = spec["value"]
                case.assigned_to = assignees.get(spec["assigned"])
                case.closed_at = closed_at
                case.save()

            stay = CASE_STAYS.get(spec["key"])
            workflow = CASE_WORKFLOW_HOURS.get(spec["key"], {})
            update_fields = []
            if stay:
                case.check_in = now + timedelta(hours=stay["check_in"])
                case.check_out = now + timedelta(hours=stay["check_out"])
                update_fields.extend(["check_in", "check_out"])
                if stay["check_in"] < 0 and case.actual_check_out is None:
                    case.actual_check_in = case.check_in
                    update_fields.append("actual_check_in")
                elif stay["check_in"] >= 0:
                    case.actual_check_in = None
                    update_fields.append("actual_check_in")
            location_key = CASE_LOCATIONS.get(spec["key"])
            if location_key:
                case.location = locations.get(location_key)
                update_fields.append("location")
            if "quoted" in workflow:
                case.quoted_at = now + timedelta(hours=workflow["quoted"])
                update_fields.append("quoted_at")
            if "approved" in workflow:
                case.approved_at = now + timedelta(hours=workflow["approved"])
                update_fields.append("approved_at")
            if "finance" in workflow:
                case.finance_moved_at = now + timedelta(hours=workflow["finance"])
                case.finance_status = FinanceStatus.SENT
                update_fields.extend(["finance_moved_at", "finance_status"])
            if update_fields:
                case.save(update_fields=[*update_fields, "updated_at"])

            for payment_spec in CASE_PAYMENTS.get(spec["key"], ()):
                expected_date = now + timedelta(hours=payment_spec["hours"])
                sequence = int(str(payment_spec["number"]).split("-")[1])
                approved = payment_spec["status"] == PaymentStatus.APPROVED
                rejected = payment_spec["status"] == PaymentStatus.REJECTED
                pending_approval = payment_spec["status"] == PaymentStatus.PENDING_APPROVAL
                payment, payment_created = Payment.objects.get_or_create(
                    payment_number=payment_spec["number"],
                    defaults={
                        "sequence": sequence,
                        "case": case,
                        "payment_type": payment_spec["type"],
                        "amount": payment_spec["amount"],
                        "currency": "MYR",
                        "payment_method": payment_spec["method"],
                        "status": payment_spec["status"],
                        "expected_date": expected_date,
                        "paid_at": now if approved else None,
                        "notes": payment_spec.get("notes") or "",
                        "created_by": actor,
                        "approved_by": actor if approved else None,
                        "approved_at": now if approved else None,
                        "rejected_by": actor if rejected else None,
                        "rejected_at": now if rejected else None,
                        "rejection_reason": payment_spec.get("rejection_reason") or "",
                        "submitted_at": now if pending_approval or approved or rejected else None,
                    },
                )
                if payment_created:
                    counts["payments"] += 1
                else:
                    payment.case = case
                    payment.payment_type = payment_spec["type"]
                    payment.amount = payment_spec["amount"]
                    payment.currency = "MYR"
                    payment.payment_method = payment_spec["method"]
                    payment.status = payment_spec["status"]
                    payment.expected_date = expected_date
                    payment.paid_at = now if approved else payment.paid_at
                    payment.notes = payment_spec.get("notes") or ""
                    payment.rejection_reason = payment_spec.get("rejection_reason") or ""
                    payment.save()
                if payment_spec.get("proof") and not payment.attachments.exists():
                    PaymentAttachment.objects.create(
                        payment=payment,
                        file=ContentFile(TINY_PNG, name=f"{payment.payment_number.lower()}-proof.png"),
                        original_name=f"{payment.payment_number}-proof.png",
                        content_type="image/png",
                        description="Bank transfer screenshot",
                        uploaded_by=actor,
                    )
                    CaseActivity.objects.get_or_create(
                        case=case,
                        event_type="payment_proof_uploaded",
                        message=f"Payment proof uploaded for {payment.payment_number}.",
                        defaults={"actor": actor},
                    )
                if payment_created:
                    CaseActivity.objects.get_or_create(
                        case=case,
                        event_type="payment_created",
                        message=f"Payment created: {payment.payment_number} ({payment.get_payment_type_display()} {payment.currency} {payment.amount}).",
                        defaults={"actor": actor},
                    )
                for refund_spec in payment_spec.get("refunds") or ():
                    refund_sequence = int(str(refund_spec["number"]).split("-")[1])
                    refund_completed = refund_spec["status"] == RefundStatus.COMPLETED
                    refund_pending = refund_spec["status"] == RefundStatus.PENDING_APPROVAL
                    refund, refund_created = PaymentRefund.objects.get_or_create(
                        refund_number=refund_spec["number"],
                        defaults={
                            "sequence": refund_sequence,
                            "payment": payment,
                            "amount": refund_spec["amount"],
                            "reason": refund_spec.get("reason") or "",
                            "status": refund_spec["status"],
                            "requested_by": actor,
                            "approved_by": actor if refund_completed or refund_spec["status"] == RefundStatus.APPROVED else None,
                            "approved_at": now if refund_completed or refund_spec["status"] == RefundStatus.APPROVED else None,
                            "completed_by": actor if refund_completed else None,
                            "completed_at": now if refund_completed else None,
                        },
                    )
                    if not refund_created:
                        refund.payment = payment
                        refund.amount = refund_spec["amount"]
                        refund.reason = refund_spec.get("reason") or ""
                        refund.status = refund_spec["status"]
                        refund.save()
                    if refund_created:
                        CaseActivity.objects.get_or_create(
                            case=case,
                            event_type="refund_requested" if refund_pending else "refund_completed",
                            message=f"Refund {refund.refund_number} {'requested' if refund_pending else 'completed'} for {payment.payment_number}.",
                            defaults={"actor": actor},
                        )
            quote_spec = CASE_QUOTES.get(spec["key"])
            if quote_spec:
                sequence = int(str(quote_spec["number"]).split("-")[1])
                valid_until = now + timedelta(hours=quote_spec["valid_hours"])
                quote, quote_created = Quote.objects.get_or_create(
                    quote_number=quote_spec["number"],
                    defaults={
                        "sequence": sequence,
                        "case": case,
                        "amount": spec["value"],
                        "currency": "MYR",
                        "status": quote_spec["status"],
                        "valid_until": valid_until,
                        "notes": quote_spec.get("notes") or case.quote_notes or "",
                        "created_by": actor,
                    },
                )
                if quote_created:
                    counts["quotes"] += 1
                else:
                    quote.case = case
                    quote.amount = spec["value"]
                    quote.currency = "MYR"
                    quote.status = quote_spec["status"]
                    quote.valid_until = valid_until
                    quote.notes = quote_spec.get("notes") or ""
                    quote.save()
            if conversation is not None:
                link_conversation(case, conversation, originating=True)
            Case.objects.filter(pk=case.pk).update(created_at=occurred, updated_at=occurred)
            CaseActivity.objects.filter(case=case).update(created_at=occurred)

            for follow_spec in CASE_FOLLOW_UPS.get(spec["key"], ()):
                due_at = now + timedelta(hours=follow_spec["hours"])
                follow_up, follow_created = CaseFollowUp.objects.get_or_create(
                    case=case,
                    title=follow_spec["title"],
                    defaults={
                        "follow_up_type": follow_spec["type"],
                        "description": follow_spec["description"],
                        "assigned_to": case.assigned_to,
                        "due_at": due_at,
                        "status": follow_spec["status"],
                        "completed_at": now if follow_spec["status"] == FollowUpStatus.COMPLETED else None,
                        "created_by": actor,
                    },
                )
                if follow_created:
                    counts["follow_ups"] += 1
                    if follow_spec["status"] == FollowUpStatus.PENDING:
                        CaseActivity.objects.get_or_create(
                            case=case,
                            event_type="follow_up_created",
                            message=f"Follow-up created: {follow_up.title}.",
                            defaults={"actor": actor},
                        )
                    else:
                        CaseActivity.objects.get_or_create(
                            case=case,
                            event_type="follow_up_completed",
                            message=f"Follow-up completed: {follow_up.title}",
                            defaults={"actor": actor},
                        )
                else:
                    follow_up.follow_up_type = follow_spec["type"]
                    follow_up.description = follow_spec["description"]
                    follow_up.assigned_to = case.assigned_to
                    follow_up.due_at = due_at
                    follow_up.status = follow_spec["status"]
                    follow_up.completed_at = now if follow_spec["status"] == FollowUpStatus.COMPLETED else None
                    follow_up.save()

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        for label, value in counts.items():
            self.stdout.write(f"  created {label}: {value}")
        self.stdout.write("Development users (password unchanged if they already existed):")
        self.stdout.write(f"  admin_demo / {DEMO_PASSWORD}  SUPERUSER")
        self.stdout.write(f"  manager_kl / {DEMO_PASSWORD}  Kuala Lumpur only")
        self.stdout.write(f"  staff_kl / {DEMO_PASSWORD}  Kuala Lumpur only")
        self.stdout.write(f"  global_staff / {DEMO_PASSWORD}  all properties")
