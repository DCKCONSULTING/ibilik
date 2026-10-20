from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF
from accounts.models import Property
from accounts.services import create_user, initialize_access_control
from cases.models import FollowUpType
from cases.services import create_case, create_follow_up
from crm.models import Customer
from locations.models import Location, LocationStatus, LocationType, MaintenanceIssue, MaintenanceStatus
from payments.models import PaymentStatus
from payments.services import create_payment
from pipeline.models import PipelineStage


class DashboardApiTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.superuser = User.objects.create_superuser("root", "root@example.com", "super-secret-pass")
        self.manager = create_user(
            username="manager.pat",
            password="manager-pass-123",
            first_name="Pat",
            last_name="Manager",
            role=ROLE_MANAGER,
        )
        self.cairo_staff = create_user(
            username="staff.lee",
            password="staff-pass-123",
            first_name="Aiman",
            last_name="Rahman",
            role=ROLE_STAFF,
        )
        self.alex_staff = create_user(
            username="staff.other",
            password="staff-pass-123",
            first_name="Sara",
            last_name="Ali",
            role=ROLE_STAFF,
        )
        self.cairo = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.alex = Property.objects.create(name="Hotel Penang", region="Penang", city="George Town", rate="120.00")
        self.cairo.staff.add(self.cairo_staff, self.manager)
        self.alex.staff.add(self.alex_staff)
        self.customer = Customer.objects.create(
            name="John Smith",
            email="john@example.com",
            phone="+201001234567",
            property=self.cairo,
        )
        self.alex_customer = Customer.objects.create(
            name="Nour Khaled",
            email="nour@example.com",
            phone="+201009999999",
            property=self.alex,
        )
        self.room = Location.objects.create(
            property=self.cairo,
            name="Deluxe 1201",
            code="KL-1201",
            location_type=LocationType.ROOM,
            is_bookable=True,
        )
        self.dirty_room = Location.objects.create(
            property=self.cairo,
            name="Deluxe 1202",
            code="KL-1202",
            location_type=LocationType.ROOM,
            is_bookable=True,
            status=LocationStatus.DIRTY,
        )
        self.alex_room = Location.objects.create(
            property=self.alex,
            name="Sea View 3",
            code="PG-3",
            location_type=LocationType.ROOM,
            is_bookable=True,
        )
        now = timezone.now()
        local = timezone.localtime(now)
        today = local.replace(hour=14, minute=0, second=0, microsecond=0)
        self.arrival = self._make_stay(
            title="Arriving today",
            customer=self.customer,
            property_obj=self.cairo,
            staff=self.cairo_staff,
            location=self.room,
            check_in=today,
            check_out=today + timedelta(days=2),
            value="4500.00",
        )
        self.in_house = self._make_stay(
            title="Current guest",
            customer=self.customer,
            property_obj=self.cairo,
            staff=self.cairo_staff,
            location=self.room,
            check_in=now - timedelta(days=1),
            check_out=now + timedelta(days=1),
            value="3200.00",
        )
        self.departure = self._make_stay(
            title="Leaving today",
            customer=self.customer,
            property_obj=self.cairo,
            staff=self.cairo_staff,
            check_in=now - timedelta(days=2),
            check_out=today + timedelta(hours=2),
            value="2100.00",
        )
        self.enquiry = create_case(
            actor=self.superuser,
            payload={
                "title": "Family suite enquiry",
                "customer_id": self.customer.pk,
                "property_id": self.cairo.pk,
                "assigned_to_id": self.cairo_staff.pk,
                "stage": PipelineStage.QUALIFIED,
                "value": "8000.00",
            },
        )
        self.alex_booking = self._make_stay(
            title="Beach stay",
            customer=self.alex_customer,
            property_obj=self.alex,
            staff=self.alex_staff,
            location=self.alex_room,
            check_in=now + timedelta(days=5),
            check_out=now + timedelta(days=8),
            value="8000.00",
        )
        self.pending_payment = create_payment(
            actor=self.superuser,
            payload={
                "case_id": self.in_house.pk,
                "amount": "500.00",
                "payment_type": "deposit",
                "expected_date": (now - timedelta(days=1)).isoformat(),
            },
        )
        self.approved_payment = create_payment(
            actor=self.superuser,
            payload={
                "case_id": self.departure.pk,
                "amount": "1200.00",
                "payment_method": "cash",
                "received": True,
            },
        )
        create_follow_up(
            self.enquiry,
            {
                "type": FollowUpType.CALL_CUSTOMER,
                "title": "Call guest about suite",
                "due_at": (now - timedelta(hours=2)).isoformat(),
            },
            actor=self.superuser,
        )
        MaintenanceIssue.objects.create(
            location=self.dirty_room,
            property=self.cairo,
            title="AC not cooling",
            status=MaintenanceStatus.OPEN,
            created_by=self.superuser,
        )

    def _make_stay(self, *, title, customer, property_obj, staff, check_in, check_out, value, location=None, stage=PipelineStage.WON):
        case = create_case(
            actor=self.superuser,
            payload={
                "title": title,
                "customer_id": customer.pk,
                "property_id": property_obj.pk,
                "assigned_to_id": staff.pk,
                "source": "website",
                "stage": stage,
                "value": value,
            },
        )
        case.check_in = check_in
        case.check_out = check_out
        case.location = location
        case.save(update_fields=["check_in", "check_out", "location", "updated_at"])
        return case

    def _login(self, username, password="staff-pass-123"):
        if username == "root":
            password = "super-secret-pass"
        if username == "manager.pat":
            password = "manager-pass-123"
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def test_dashboard_returns_live_hotel_metrics(self):
        self._login("root")
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["resource"], "dashboard")
        kpis = payload["kpis"]
        self.assertGreaterEqual(kpis["check_ins_today"], 1)
        self.assertGreaterEqual(kpis["check_outs_today"], 1)
        self.assertGreaterEqual(kpis["in_house"], 1)
        self.assertGreaterEqual(kpis["open_pipeline"], 1)
        self.assertEqual(Decimal(kpis["pipeline_value"]), Decimal("8000.00"))
        self.assertGreaterEqual(kpis["pending_payments"], 1)
        self.assertGreaterEqual(kpis["overdue_payments"], 1)
        self.assertGreaterEqual(kpis["open_follow_ups"], 1)
        self.assertGreaterEqual(kpis["rooms_attention"], 1)
        self.assertGreaterEqual(kpis["open_maintenance"], 1)
        self.assertEqual(Decimal(kpis["revenue_this_month"]), Decimal("1200.00"))
        self.assertTrue(any(item["booking_number"] == self.arrival.case_number for item in payload["arrivals"]))
        self.assertTrue(any(item["booking_number"] == self.in_house.case_number for item in payload["in_house"]))
        self.assertTrue(any(item["id"] == self.pending_payment.pk for item in payload["pending_payments"]))
        self.assertTrue(any(item["id"] == self.dirty_room.pk for item in payload["rooms"]["attention"]))
        self.assertEqual(self.pending_payment.status, PaymentStatus.PENDING)

    def test_staff_only_sees_assigned_property(self):
        self._login("staff.lee")
        payload = self.client.get("/api/dashboard/").json()
        booking_ids = {item["id"] for item in payload["recent_bookings"]}
        self.assertIn(self.arrival.pk, booking_ids)
        self.assertNotIn(self.alex_booking.pk, booking_ids)
        self.assertTrue(all(item["id"] == self.cairo.pk for item in payload["properties"]))

    def test_property_filter_limits_metrics(self):
        self._login("root")
        payload = self.client.get("/api/dashboard/", {"property": self.alex.pk}).json()
        self.assertEqual(payload["kpis"]["check_ins_today"], 0)
        self.assertEqual(payload["kpis"]["in_house"], 0)
        self.assertEqual(payload["kpis"]["upcoming"], 1)
        self.assertEqual(payload["kpis"]["open_pipeline"], 0)
        self.assertTrue(any(item["id"] == self.alex_booking.pk for item in payload["recent_bookings"]))
        self.assertFalse(any(item["id"] == self.arrival.pk for item in payload["recent_bookings"]))

    def test_invalid_property_returns_400(self):
        self._login("root")
        response = self.client.get("/api/dashboard/", {"property": "kl"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_property")
