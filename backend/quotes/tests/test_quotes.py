from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF
from accounts.models import Property
from accounts.services import create_user, initialize_access_control
from cases.services import create_case, update_case
from crm.models import Customer
from pipeline.models import PipelineStage
from quotes.models import Quote, QuoteStatus


class QuoteApiTests(TestCase):
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
        self.cairo_case = create_case(
            actor=self.superuser,
            payload={
                "title": "Family room",
                "customer_id": self.customer.pk,
                "property_id": self.cairo.pk,
                "assigned_to_id": self.cairo_staff.pk,
                "source": "whatsapp",
                "stage": PipelineStage.QUALIFIED,
                "value": "30000.00",
            },
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
                "value": "8000.00",
            },
        )

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

    def _quote_case(self, case_id, **payload):
        self._login("root")
        body = {"action": "quote", "value": "4500.00", "notes": "Family room rate"}
        body.update(payload)
        return self.client.post(f"/api/cases/{case_id}/actions/", data=body, content_type="application/json")

    def test_unauthenticated_list_is_rejected(self):
        response = self.client.get("/api/quotes/")
        self.assertEqual(response.status_code, 401)

    def test_quote_action_creates_quote_record(self):
        response = self._quote_case(self.cairo_case.pk)
        self.assertEqual(response.status_code, 200, response.content)
        quote = Quote.objects.get(case=self.cairo_case)
        self.assertEqual(quote.quote_number, "QT-1001")
        self.assertEqual(quote.amount, Decimal("4500.00"))
        self.assertEqual(quote.currency, "MYR")
        self.assertEqual(quote.status, QuoteStatus.PENDING)
        self.assertIsNotNone(quote.valid_until)
        self.assertEqual(quote.case.customer_id, self.customer.pk)
        self.assertEqual(quote.case.property_id, self.cairo.pk)

    def test_superuser_lists_all_quotes(self):
        self._quote_case(self.cairo_case.pk)
        self._quote_case(self.alex_case.pk, value="8000.00", notes="Beach")
        self._login("root")
        listing = self.client.get("/api/quotes/")
        self.assertEqual(listing.status_code, 200)
        body = listing.json()
        self.assertEqual(body["resource"], "quotes")
        self.assertEqual(body["count"], 2)
        self.assertEqual({item["quote_number"] for item in body["results"]}, {"QT-1001", "QT-1002"})

    def test_staff_sees_only_accessible_property_quotes(self):
        self._quote_case(self.cairo_case.pk)
        self._quote_case(self.alex_case.pk, value="8000.00")
        cairo_quote = Quote.objects.get(case=self.cairo_case)
        alex_quote = Quote.objects.get(case=self.alex_case)
        self._login("staff.lee")
        listing = self.client.get("/api/quotes/").json()
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["results"][0]["id"], cairo_quote.pk)
        self.assertEqual(self.client.get(f"/api/quotes/{alex_quote.pk}/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/quotes/{cairo_quote.pk}/").status_code, 200)

    def test_search_and_filters(self):
        self._quote_case(self.cairo_case.pk)
        self._quote_case(self.alex_case.pk, value="8000.00", notes="Beach")
        cairo_quote = Quote.objects.get(case=self.cairo_case)
        cairo_quote.valid_until = timezone.now() - timedelta(days=2)
        cairo_quote.save(update_fields=["valid_until", "updated_at"])
        self._login("root")
        self.assertEqual(self.client.get("/api/quotes/", {"search": "QT-1001"}).json()["count"], 1)
        self.assertEqual(self.client.get("/api/quotes/", {"search": self.cairo_case.case_number}).json()["count"], 1)
        self.assertGreaterEqual(self.client.get("/api/quotes/", {"search": "John Smith"}).json()["count"], 1)
        self.assertGreaterEqual(self.client.get("/api/quotes/", {"search": "201001234567"}).json()["count"], 1)
        self.assertGreaterEqual(self.client.get("/api/quotes/", {"search": "Hotel KL"}).json()["count"], 1)
        pending = self.client.get("/api/quotes/", {"status": "pending"}).json()
        self.assertTrue(all(item["workflow_status"] == "pending" for item in pending["results"]))
        expired = self.client.get("/api/quotes/", {"status": "expired"}).json()
        self.assertGreaterEqual(expired["count"], 1)
        self.assertTrue(any(item["id"] == cairo_quote.pk and item["status"] == "expired" for item in expired["results"]))
        by_property = self.client.get("/api/quotes/", {"property": self.alex.pk}).json()
        self.assertTrue(all(item["property"]["id"] == self.alex.pk for item in by_property["results"]))
        by_staff = self.client.get("/api/quotes/", {"staff": self.cairo_staff.pk}).json()
        self.assertTrue(all(item["staff"]["id"] == self.cairo_staff.pk for item in by_staff["results"]))
        by_case = self.client.get("/api/quotes/", {"case": self.cairo_case.pk}).json()
        self.assertEqual(by_case["count"], 1)
        by_case_number = self.client.get("/api/quotes/", {"case_number": self.cairo_case.case_number}).json()
        self.assertEqual(by_case_number["count"], 1)
        by_customer = self.client.get("/api/quotes/", {"customer": self.customer.pk}).json()
        self.assertTrue(all(item["customer"]["id"] == self.customer.pk for item in by_customer["results"]))
        this_month = self.client.get("/api/quotes/", {"date_field": "created_at", "due": "this_month"}).json()
        self.assertGreaterEqual(this_month["count"], 1)
        empty = self.client.get("/api/quotes/", {"status": "rejected"}).json()
        self.assertEqual(empty["count"], 0)
        self.assertEqual(empty["results"], [])

    def test_pagination_and_ordering(self):
        self._quote_case(self.cairo_case.pk)
        extra = []
        for index in range(12):
            case = create_case(
                actor=self.superuser,
                payload={
                    "title": f"Quote case {index}",
                    "customer_id": self.customer.pk,
                    "property_id": self.cairo.pk,
                    "assigned_to_id": self.cairo_staff.pk,
                    "stage": PipelineStage.QUALIFIED,
                    "value": f"{1000 + index}.00",
                },
            )
            extra.append(case)
            self._quote_case(case.pk, value=f"{1000 + index}.00")
        self._login("root")
        listing = self.client.get("/api/quotes/", {"page_size": 10, "page": 1})
        self.assertEqual(listing.status_code, 200)
        body = listing.json()
        self.assertGreaterEqual(body["count"], 13)
        self.assertEqual(len(body["results"]), 10)
        self.assertTrue(body["has_next"])
        amount_desc = self.client.get("/api/quotes/", {"ordering": "-amount"}).json()
        amounts = [Decimal(item["amount"]) for item in amount_desc["results"] if item["amount"]]
        self.assertEqual(amounts, sorted(amounts, reverse=True))

    def test_approve_and_lost_update_quote_status(self):
        self._quote_case(self.cairo_case.pk)
        self._login("root")
        approved = self.client.post(
            f"/api/cases/{self.cairo_case.pk}/actions/",
            data={"action": "approve"},
            content_type="application/json",
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(Quote.objects.get(case=self.cairo_case).status, QuoteStatus.ACCEPTED)
        self._quote_case(self.alex_case.pk, value="8000.00")
        update_case(self.alex_case, {"stage": "lost"}, actor=self.superuser)
        self.assertEqual(Quote.objects.get(case=self.alex_case).status, QuoteStatus.REJECTED)

    def test_combined_filters_and_detail(self):
        self._quote_case(self.cairo_case.pk)
        quote = Quote.objects.get(case=self.cairo_case)
        self._login("root")
        combined = self.client.get(
            "/api/quotes/",
            {
                "status": "pending",
                "property": self.cairo.pk,
                "staff": self.cairo_staff.pk,
                "customer": self.customer.pk,
                "case": self.cairo_case.pk,
            },
        ).json()
        self.assertEqual(combined["count"], 1)
        self.assertEqual(combined["results"][0]["id"], quote.pk)
        detail = self.client.get(f"/api/quotes/{quote.pk}/")
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["quote_number"], "QT-1001")
        self.assertEqual(body["case"]["case_number"], self.cairo_case.case_number)
        self.assertEqual(body["customer"]["name"], "John Smith")
        self.assertEqual(body["staff"]["username"], "staff.lee")
