from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.catalog import ROLE_STAFF
from accounts.models import Property, UserPropertyAccess
from accounts.services import create_user, initialize_access_control
from cases.models import CaseFollowUp, FollowUpStatus, FollowUpType
from cases.services import create_case, create_follow_up
from crm.models import Customer
from pipeline.models import PipelineStage


class GlobalFollowUpApiTests(TestCase):
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
        self.global_staff = create_user(
            username="staff.global",
            password="staff-pass-123",
            role=ROLE_STAFF,
            property_access=UserPropertyAccess.Mode.GLOBAL,
            actor=self.superuser,
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
        self.cairo_case = create_case(
            actor=self.superuser,
            payload={
                "title": "Family room",
                "customer_id": self.cairo_customer.pk,
                "property_id": self.cairo.pk,
                "assigned_to_id": self.cairo_staff.pk,
                "source": "whatsapp",
                "stage": PipelineStage.QUALIFIED,
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
                "stage": PipelineStage.NEW,
            },
        )
        now = timezone.now()
        self.pending = create_follow_up(
            self.cairo_case,
            {
                "type": FollowUpType.SEND_QUOTE,
                "title": "Send quote",
                "assigned_to_id": self.cairo_staff.pk,
                "due_at": (now + timedelta(hours=2)).isoformat(),
            },
            actor=self.superuser,
        )
        self.overdue = create_follow_up(
            self.cairo_case,
            {
                "type": FollowUpType.CALL_CUSTOMER,
                "title": "Call customer",
                "assigned_to_id": self.cairo_staff.pk,
                "due_at": (now - timedelta(hours=3)).isoformat(),
            },
            actor=self.superuser,
        )
        self.completed = create_follow_up(
            self.cairo_case,
            {"type": FollowUpType.FOLLOW_UP, "title": "Completed check", "due_at": now.isoformat()},
            actor=self.superuser,
        )
        self.completed.status = FollowUpStatus.COMPLETED
        self.completed.completed_at = now
        self.completed.save(update_fields=["status", "completed_at", "updated_at"])
        self.cancelled = create_follow_up(
            self.cairo_case,
            {"type": FollowUpType.INTERNAL_REVIEW, "title": "Cancelled review"},
            actor=self.superuser,
        )
        self.cancelled.status = FollowUpStatus.CANCELLED
        self.cancelled.save(update_fields=["status", "updated_at"])
        self.alex_follow_up = create_follow_up(
            self.alex_case,
            {
                "type": FollowUpType.CHECK_AVAILABILITY,
                "title": "Check rate",
                "assigned_to_id": self.alex_staff.pk,
                "due_at": (now + timedelta(days=1)).isoformat(),
            },
            actor=self.superuser,
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

    def test_list_pagination_search_and_sorting(self):
        self._login("root")
        listing = self.client.get("/api/follow-ups/", {"status": "all", "page_size": 2, "ordering": "due_at"})
        self.assertEqual(listing.status_code, 200, listing.content)
        body = listing.json()
        self.assertEqual(body["resource"], "follow-ups")
        self.assertGreaterEqual(body["count"], 5)
        self.assertEqual(body["page_size"], 2)
        self.assertTrue(body["has_next"])
        self.assertEqual(len(body["results"]), 2)
        self.assertTrue(body["results"][0]["case"]["case_number"].startswith("CASE-"))
        self.assertEqual(body["results"][0]["customer"]["name"], body["results"][0]["customer"]["name"])

        search = self.client.get("/api/follow-ups/", {"status": "all", "search": "CASE-1001"}).json()
        self.assertGreaterEqual(search["count"], 1)
        self.assertTrue(all("CASE-1001" in item["case"]["case_number"] for item in search["results"]))

        by_name = self.client.get("/api/follow-ups/", {"status": "all", "search": "John Smith"}).json()
        self.assertGreaterEqual(by_name["count"], 1)
        by_phone = self.client.get("/api/follow-ups/", {"status": "all", "search": "+201001234567"}).json()
        self.assertGreaterEqual(by_phone["count"], 1)
        by_title = self.client.get("/api/follow-ups/", {"status": "all", "search": "Send quote"}).json()
        self.assertEqual(by_title["count"], 1)

        created_sort = self.client.get("/api/follow-ups/", {"status": "all", "ordering": "-created_at"}).json()
        created_ids = [item["id"] for item in created_sort["results"]]
        self.assertEqual(created_ids, sorted(created_ids, reverse=True)[: len(created_ids)])

    def test_filters(self):
        self._login("root")
        default = self.client.get("/api/follow-ups/").json()
        titles = {item["title"] for item in default["results"]}
        self.assertIn("Send quote", titles)
        self.assertIn("Call customer", titles)
        self.assertNotIn("Completed check", titles)
        self.assertNotIn("Cancelled review", titles)

        pending = self.client.get("/api/follow-ups/", {"status": "pending"}).json()
        self.assertTrue(all(item["status"] == "pending" for item in pending["results"]))
        overdue = self.client.get("/api/follow-ups/", {"status": "overdue"}).json()
        self.assertTrue(all(item["status"] == "overdue" for item in overdue["results"]))
        completed = self.client.get("/api/follow-ups/", {"status": "completed"}).json()
        self.assertEqual(completed["count"], 1)
        cancelled = self.client.get("/api/follow-ups/", {"status": "cancelled"}).json()
        self.assertEqual(cancelled["count"], 1)

        staff = self.client.get("/api/follow-ups/", {"status": "all", "assigned_staff": self.cairo_staff.pk}).json()
        self.assertTrue(all(item["assigned_to"]["id"] == self.cairo_staff.pk for item in staff["results"] if item["assigned_to"]))
        property_filter = self.client.get("/api/follow-ups/", {"status": "all", "property": self.alex.pk}).json()
        self.assertEqual(property_filter["count"], 1)
        self.assertEqual(property_filter["results"][0]["property"]["id"], self.alex.pk)
        type_filter = self.client.get("/api/follow-ups/", {"status": "all", "type": FollowUpType.SEND_QUOTE}).json()
        self.assertEqual(type_filter["count"], 1)
        stage = self.client.get("/api/follow-ups/", {"status": "all", "case_stage": "qualified"}).json()
        self.assertTrue(all(item["case"]["stage"] == "qualified" for item in stage["results"]))
        source = self.client.get("/api/follow-ups/", {"status": "all", "source": "website"}).json()
        self.assertEqual(source["count"], 1)
        today = self.client.get("/api/follow-ups/", {"status": "all", "due": "today"}).json()
        self.assertGreaterEqual(today["count"], 1)
        tomorrow = self.client.get("/api/follow-ups/", {"status": "all", "due": "tomorrow"}).json()
        self.assertEqual(tomorrow["count"], 1)
        combined = self.client.get(
            "/api/follow-ups/",
            {
                "status": "pending",
                "assigned_staff": self.cairo_staff.pk,
                "property": self.cairo.pk,
                "case_stage": "qualified",
            },
        ).json()
        self.assertEqual(combined["count"], 1)
        self.assertEqual(combined["results"][0]["title"], "Send quote")

    def test_permissions_and_staff_filter_scope(self):
        self._login("root")
        listing = self.client.get("/api/follow-ups/", {"status": "all"}).json()
        self.assertEqual(listing["count"], 5)
        staff_ids = {item["id"] for item in listing["staff"]}
        self.assertIn(self.cairo_staff.pk, staff_ids)
        self.assertIn(self.alex_staff.pk, staff_ids)

        self._login("staff.lee")
        scoped = self.client.get("/api/follow-ups/", {"status": "all"}).json()
        self.assertEqual(scoped["count"], 4)
        self.assertTrue(all(item["property"]["id"] == self.cairo.pk for item in scoped["results"]))
        self.assertTrue(all((item["assigned_to"] or {}).get("id") == self.cairo_staff.pk for item in scoped["results"]))
        scoped_staff = {item["id"] for item in scoped["staff"]}
        self.assertIn(self.cairo_staff.pk, scoped_staff)
        self.assertNotIn(self.alex_staff.pk, scoped_staff)
        self.assertEqual(self.client.get(f"/api/follow-ups/{self.alex_follow_up.pk}/").status_code, 403)
        self.assertEqual(
            self.client.post(f"/api/follow-ups/{self.alex_follow_up.pk}/complete/").status_code,
            403,
        )
        forbidden_create = self.client.post(
            "/api/follow-ups/",
            data={"case_id": self.alex_case.pk, "title": "Should fail"},
            content_type="application/json",
        )
        self.assertEqual(forbidden_create.status_code, 403)

    def test_global_staff_cannot_see_another_staff_follow_up(self):
        self._login("staff.global")
        self.assertEqual(self.client.get(f"/api/follow-ups/{self.pending.pk}/").status_code, 403)
        listing = self.client.get("/api/follow-ups/", {"status": "all"}).json()
        self.assertEqual(listing["count"], 0)

    def test_actions_and_relationships(self):
        self._login("root")
        detail = self.client.get(f"/api/follow-ups/{self.pending.pk}/")
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["case"]["id"], self.cairo_case.pk)
        self.assertEqual(body["customer"]["name"], "John Smith")
        self.assertEqual(body["property"]["name"], "Hotel KL")
        self.assertEqual(body["assigned_to"]["name"], "Aiman Rahman")

        edited = self.client.patch(
            f"/api/follow-ups/{self.pending.pk}/",
            data={"title": "Send quote (revised)", "description": "Updated notes"},
            content_type="application/json",
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["title"], "Send quote (revised)")
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.title, "Send quote (revised)")

        completed = self.client.post(f"/api/follow-ups/{self.pending.pk}/complete/")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], "completed")
        self.assertIsNotNone(completed.json()["completed_at"])
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, FollowUpStatus.COMPLETED)

        cancelled = self.client.delete(f"/api/follow-ups/{self.overdue.pk}/")
        self.assertEqual(cancelled.status_code, 200)
        self.overdue.refresh_from_db()
        self.assertEqual(self.overdue.status, FollowUpStatus.CANCELLED)

        created = self.client.post(
            "/api/follow-ups/",
            data={
                "case_id": self.cairo_case.pk,
                "type": FollowUpType.REQUEST_INFORMATION,
                "title": "Ask for dates",
                "assigned_to_id": self.cairo_staff.pk,
            },
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["case"]["id"], self.cairo_case.pk)
        self.assertTrue(CaseFollowUp.objects.filter(pk=created.json()["id"], case=self.cairo_case).exists())
        nested = self.client.get(f"/api/cases/{self.cairo_case.pk}/follow-ups/").json()
        self.assertTrue(any(item["title"] == "Ask for dates" for item in nested["results"]))
