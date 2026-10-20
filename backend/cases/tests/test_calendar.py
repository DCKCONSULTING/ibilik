from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.catalog import ROLE_STAFF
from accounts.models import Property, UserPropertyAccess
from accounts.services import create_user, initialize_access_control
from cases.models import CaseFollowUp, FollowUpStatus, FollowUpType
from cases.services import create_case, create_follow_up
from crm.models import Customer
from payments.models import Payment, PaymentStatus
from payments.numbering import allocate_payment_number
from pipeline.models import PipelineStage


class CalendarEventsApiTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.superuser = User.objects.create_superuser("root", "root@example.com", "super-secret-pass")
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
        self.cairo.staff.add(self.cairo_staff)
        self.alex.staff.add(self.alex_staff)
        self.cairo_customer = Customer.objects.create(
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
        self.now = timezone.now().replace(minute=0, second=0, microsecond=0)
        self.cairo_case = create_case(
            actor=self.superuser,
            payload={
                "title": "Family room",
                "customer_id": self.cairo_customer.pk,
                "property_id": self.cairo.pk,
                "assigned_to_id": self.cairo_staff.pk,
                "source": "whatsapp",
                "stage": PipelineStage.WON,
                "value": "4500.00",
            },
        )
        self.cairo_case.check_in = self.now + timedelta(hours=2)
        self.cairo_case.check_out = self.now + timedelta(days=2, hours=11)
        self.cairo_case.quoted_at = self.now - timedelta(days=1)
        self.cairo_case.approved_at = self.now - timedelta(hours=6)
        self.cairo_case.finance_moved_at = self.now + timedelta(hours=5)
        self.cairo_case.save(
            update_fields=["check_in", "check_out", "quoted_at", "approved_at", "finance_moved_at", "updated_at"]
        )
        self.alex_case = create_case(
            actor=self.superuser,
            payload={
                "title": "Beach stay",
                "customer_id": self.alex_customer.pk,
                "property_id": self.alex.pk,
                "assigned_to_id": self.alex_staff.pk,
                "source": "website",
                "stage": PipelineStage.QUALIFIED,
            },
        )
        self.follow_up = create_follow_up(
            self.cairo_case,
            {
                "type": FollowUpType.SEND_QUOTE,
                "title": "Send quote",
                "assigned_to_id": self.cairo_staff.pk,
                "due_at": (self.now + timedelta(hours=4)).isoformat(),
            },
            actor=self.superuser,
        )
        self.alex_follow_up = create_follow_up(
            self.alex_case,
            {
                "type": FollowUpType.CALL_CUSTOMER,
                "title": "Call guest",
                "assigned_to_id": self.alex_staff.pk,
                "due_at": (self.now + timedelta(hours=3)).isoformat(),
            },
            actor=self.superuser,
        )
        sequence, payment_number = allocate_payment_number()
        self.payment = Payment.objects.create(
            sequence=sequence,
            payment_number=payment_number,
            case=self.cairo_case,
            amount=Decimal("4500.00"),
            currency="MYR",
            expected_date=self.now + timedelta(hours=8),
            status=PaymentStatus.PENDING,
            created_by=self.superuser,
        )

    def _login(self, username, password="staff-pass-123"):
        if username == "root":
            password = "super-secret-pass"
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def _range(self, **extra):
        params = {
            "start": (self.now - timedelta(days=2)).isoformat(),
            "end": (self.now + timedelta(days=5)).isoformat(),
        }
        params.update(extra)
        return params

    def test_requires_range_and_returns_typed_events(self):
        self._login("root")
        missing = self.client.get("/api/calendar/events/")
        self.assertEqual(missing.status_code, 400)
        listing = self.client.get("/api/calendar/events/", self._range())
        self.assertEqual(listing.status_code, 200, listing.content)
        body = listing.json()
        self.assertEqual(body["resource"], "calendar-events")
        types = {item["type"] for item in body["results"]}
        self.assertEqual(types, {"check_in", "check_out", "follow_up", "payment", "quote", "approval", "finance"})
        check_in = next(item for item in body["results"] if item["type"] == "check_in")
        self.assertEqual(check_in["case"]["id"], self.cairo_case.pk)
        self.assertEqual(check_in["customer"]["name"], "John Smith")
        self.assertEqual(check_in["property"]["name"], "Hotel KL")
        self.assertEqual(check_in["staff"]["name"], "Aiman Rahman")
        self.assertEqual(check_in["source_model"], "case")
        self.assertTrue(check_in["start"].startswith(self.cairo_case.check_in.isoformat()[:19]))
        payment = next(item for item in body["results"] if item["type"] == "payment")
        self.assertEqual(payment["source_id"], self.payment.pk)
        self.assertEqual(payment["metadata"]["amount_label"], "MYR 4,500")
        follow_up = next(
            item
            for item in body["results"]
            if item["source_model"] == "case_follow_up" and item["source_id"] == self.follow_up.pk
        )
        self.assertEqual(follow_up["type"], "follow_up")
        self.assertEqual(follow_up["case"]["case_number"], self.cairo_case.case_number)

    def test_filters_and_search(self):
        self._login("root")
        check_ins = self.client.get("/api/calendar/events/", self._range(type="check_in")).json()
        self.assertEqual(check_ins["count"], 1)
        self.assertEqual(check_ins["results"][0]["type"], "check_in")
        check_outs = self.client.get("/api/calendar/events/", self._range(type="check-outs")).json()
        self.assertEqual(check_outs["count"], 1)
        follow_ups = self.client.get("/api/calendar/events/", self._range(type="follow-ups")).json()
        self.assertEqual(follow_ups["count"], 2)
        payments = self.client.get("/api/calendar/events/", self._range(type="payment")).json()
        self.assertEqual(payments["count"], 1)
        quotes = self.client.get("/api/calendar/events/", self._range(type="quote")).json()
        self.assertEqual(quotes["count"], 1)
        approvals = self.client.get("/api/calendar/events/", self._range(type="approval")).json()
        self.assertEqual(approvals["count"], 1)
        finance = self.client.get("/api/calendar/events/", self._range(type="finance")).json()
        self.assertEqual(finance["count"], 1)
        staff = self.client.get("/api/calendar/events/", self._range(staff=self.cairo_staff.pk)).json()
        self.assertTrue(all((item["staff"] or {}).get("id") == self.cairo_staff.pk for item in staff["results"]))
        property_filter = self.client.get("/api/calendar/events/", self._range(property=self.alex.pk)).json()
        self.assertTrue(all(item["property"]["id"] == self.alex.pk for item in property_filter["results"]))
        stage = self.client.get("/api/calendar/events/", self._range(case_stage="won")).json()
        self.assertTrue(all(item["case"]["stage"] == "won" for item in stage["results"]))
        source = self.client.get("/api/calendar/events/", self._range(source="website")).json()
        self.assertTrue(all(item["case"]["source"] == "website" for item in source["results"]))
        pending = self.client.get("/api/calendar/events/", self._range(status="pending")).json()
        self.assertTrue(all(item["type"] == "follow_up" and item["status"] == "pending" for item in pending["results"]))
        expected = self.client.get("/api/calendar/events/", self._range(status="expected")).json()
        self.assertTrue(all(item["type"] == "payment" and item["status"] == "expected" for item in expected["results"]))
        search = self.client.get("/api/calendar/events/", self._range(search="John Smith")).json()
        self.assertGreaterEqual(search["count"], 1)
        self.assertTrue(all(item["customer"]["name"] == "John Smith" for item in search["results"]))
        combined = self.client.get(
            "/api/calendar/events/",
            self._range(type="payment", staff=self.cairo_staff.pk, property=self.cairo.pk, case_stage="won"),
        ).json()
        self.assertEqual(combined["count"], 1)
        self.assertEqual(combined["results"][0]["source_id"], self.payment.pk)

    def test_permissions_and_staff_filter_scope(self):
        self._login("root")
        listing = self.client.get("/api/calendar/events/", self._range()).json()
        staff_ids = {item["id"] for item in listing["staff"]}
        self.assertIn(self.cairo_staff.pk, staff_ids)
        self.assertIn(self.alex_staff.pk, staff_ids)
        self._login("staff.lee")
        scoped = self.client.get("/api/calendar/events/", self._range()).json()
        self.assertTrue(all(item["property"]["id"] == self.cairo.pk for item in scoped["results"]))
        self.assertFalse(any(item["source_id"] == self.alex_follow_up.pk for item in scoped["results"]))
        scoped_staff = {item["id"] for item in scoped["staff"]}
        self.assertIn(self.cairo_staff.pk, scoped_staff)
        self.assertNotIn(self.alex_staff.pk, scoped_staff)

    def test_range_excludes_events_outside_window(self):
        self._login("root")
        outside = self.client.get(
            "/api/calendar/events/",
            {
                "start": (self.now + timedelta(days=10)).isoformat(),
                "end": (self.now + timedelta(days=12)).isoformat(),
            },
        ).json()
        self.assertEqual(outside["count"], 0)

    def test_follow_up_record_is_not_duplicated(self):
        self._login("root")
        listing = self.client.get("/api/calendar/events/", self._range(type="follow_up")).json()
        ids = [item["id"] for item in listing["results"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(CaseFollowUp.objects.count(), 2)
