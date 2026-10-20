from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF, ROLE_TOP_MANAGER
from accounts.models import Property
from accounts.services import create_user, initialize_access_control
from cases.services import create_case, update_case
from crm.models import Customer
from match.models import (
    MatchHistoryAction,
    MatchRequest,
    MatchRequestPriority,
    MatchRequestStatus,
    MatchRequestType,
)
from match.services import ensure_match_request
from payments.models import PaymentMethod, PaymentStatus, PaymentType
from payments.services import create_payment, reject_payment, submit_payment
from pipeline.models import PipelineStage
from quotes.services import record_quote_from_case


class MatchApiTests(TestCase):
    def setUp(self):
        initialize_access_control()
        from match.assignment import get_match_settings

        settings = get_match_settings()
        settings.auto_assign_enabled = False
        settings.save(update_fields=["auto_assign_enabled"])
        self.superuser = User.objects.create_superuser("root", "root@example.com", "super-secret-pass")
        self.top = create_user(
            username="top.mina",
            password="top-pass-12345",
            first_name="Mina",
            last_name="Top",
            role=ROLE_TOP_MANAGER,
        )
        self.manager = create_user(
            username="manager.pat",
            password="manager-pass-123",
            first_name="Pat",
            last_name="Manager",
            role=ROLE_MANAGER,
        )
        self.staff = create_user(
            username="staff.lee",
            password="staff-pass-123",
            first_name="Aiman",
            last_name="Rahman",
            role=ROLE_STAFF,
        )
        self.other_staff = create_user(
            username="staff.other",
            password="staff-pass-123",
            first_name="Sara",
            last_name="Ali",
            role=ROLE_STAFF,
        )
        self.kl = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.jb = Property.objects.create(name="Hotel JB", region="Johor", city="Johor Bahru", rate="120.00")
        self.kl.staff.add(self.manager, self.staff)
        self.jb.staff.add(self.other_staff)
        self.customer = Customer.objects.create(
            name="John Smith",
            email="john@example.com",
            phone="+201001234567",
            property=self.kl,
        )
        self.jb_customer = Customer.objects.create(
            name="Nour Khaled",
            email="nour@example.com",
            phone="+201009999999",
            property=self.jb,
        )
        self.kl_case = create_case(
            actor=self.superuser,
            payload={
                "title": "Family room",
                "customer_id": self.customer.pk,
                "property_id": self.kl.pk,
                "original_request": "Need a family room for 3 nights.",
                "source": "website",
            },
        )
        self.jb_case = create_case(
            actor=self.superuser,
            payload={
                "title": "Beach stay",
                "customer_id": self.jb_customer.pk,
                "property_id": self.jb.pk,
                "original_request": "Looking for a sea view room.",
                "source": "whatsapp",
            },
        )

    def _login(self, username, password=None):
        passwords = {
            "root": "super-secret-pass",
            "top.mina": "top-pass-12345",
            "manager.pat": "manager-pass-123",
            "staff.lee": "staff-pass-123",
            "staff.other": "staff-pass-123",
        }
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password or passwords[username]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def _create_manual(self, **payload):
        body = {
            "subject": "Walk-in inquiry",
            "description": "Guest asked about availability.",
            "customer_id": self.customer.pk,
            "property_id": self.kl.pk,
            "request_type": MatchRequestType.INQUIRY,
            "source_module": "match",
            "source_ref": payload.pop("source_ref", f"manual-{timezone.now().timestamp()}"),
        }
        body.update(payload)
        return self.client.post("/api/match/requests/", data=body, content_type="application/json")

    def test_unauthenticated_access_is_rejected(self):
        self.assertEqual(self.client.get("/api/match/requests/").status_code, 401)
        self.assertEqual(self.client.get("/api/match/summary/").status_code, 401)

    def test_case_creation_creates_new_unassigned_request(self):
        item = MatchRequest.objects.get(source_module="cases", source_ref=f"case:{self.kl_case.pk}")
        self.assertEqual(item.request_type, MatchRequestType.INQUIRY)
        self.assertEqual(item.status, MatchRequestStatus.NEW)
        self.assertIsNone(item.assigned_to_id)
        self.assertEqual(item.customer_id, self.customer.pk)
        self.assertEqual(item.property_id, self.kl.pk)
        self.assertEqual(item.subject, "Family room")
        self.assertTrue(item.history.filter(action=MatchHistoryAction.CREATED).exists())

    def test_duplicate_source_is_idempotent(self):
        first, created = ensure_match_request(
            source_module="cases",
            source_ref=f"case:{self.kl_case.pk}",
            request_type=MatchRequestType.INQUIRY,
            subject="Duplicate",
            customer=self.customer,
            property_obj=self.kl,
            related_case=self.kl_case,
        )
        self.assertFalse(created)
        self.assertEqual(MatchRequest.objects.filter(source_module="cases", source_ref=f"case:{self.kl_case.pk}").count(), 1)
        self.assertEqual(first.subject, "Family room")

    def test_quote_and_payment_create_match_requests(self):
        quote = record_quote_from_case(self.kl_case, actor=self.superuser)
        payment = create_payment(
            actor=self.superuser,
            payload={
                "case_id": self.kl_case.pk,
                "amount": "500.00",
                "payment_type": PaymentType.DEPOSIT,
                "payment_method": PaymentMethod.BANK_TRANSFER,
            },
        )
        self.assertTrue(MatchRequest.objects.filter(source_ref=f"quote:{quote.pk}").exists())
        self.assertTrue(MatchRequest.objects.filter(source_ref=f"payment:{payment.pk}").exists())
        quote_request = MatchRequest.objects.get(source_ref=f"quote:{quote.pk}")
        self.assertEqual(quote_request.request_type, MatchRequestType.QUOTE)
        self.assertEqual(quote_request.related_quote_id, quote.pk)
        self.assertEqual(quote_request.status, MatchRequestStatus.NEW)

    def test_rejected_payment_creates_high_priority_request(self):
        payment = create_payment(
            actor=self.superuser,
            payload={
                "case_id": self.kl_case.pk,
                "amount": "200.00",
                "payment_type": PaymentType.PAYMENT,
                "payment_method": PaymentMethod.BANK_TRANSFER,
            },
        )
        from django.core.files.uploadedfile import SimpleUploadedFile
        from payments.services import add_attachment

        add_attachment(
            payment,
            uploaded_file=SimpleUploadedFile("proof.png", b"fake", content_type="image/png"),
            actor=self.superuser,
        )
        submit_payment(payment, actor=self.superuser)
        reject_payment(payment, actor=self.superuser, reason="Unclear transfer slip")
        item = MatchRequest.objects.get(source_ref=f"payment:{payment.pk}:rejected")
        self.assertEqual(item.priority, MatchRequestPriority.HIGH)
        self.assertEqual(item.request_type, MatchRequestType.PAYMENT)

    def test_booking_cancellation_creates_request(self):
        self.kl_case.check_in = timezone.now() + timedelta(days=3)
        self.kl_case.check_out = timezone.now() + timedelta(days=6)
        self.kl_case.save(update_fields=["check_in", "check_out", "updated_at"])
        update_case(self.kl_case, {"stage": PipelineStage.LOST}, actor=self.superuser)
        item = MatchRequest.objects.get(source_ref=f"case:{self.kl_case.pk}:cancelled")
        self.assertEqual(item.request_type, MatchRequestType.CANCELLATION)
        self.assertEqual(item.priority, MatchRequestPriority.HIGH)

    def test_superuser_lists_and_summarizes_requests(self):
        self._login("root")
        listing = self.client.get("/api/match/requests/")
        self.assertEqual(listing.status_code, 200)
        body = listing.json()
        self.assertEqual(body["resource"], "match-requests")
        self.assertGreaterEqual(body["count"], 2)
        self.assertGreaterEqual(body["summary"]["new"], 2)
        self.assertGreaterEqual(body["summary"]["unassigned"], 2)
        summary = self.client.get("/api/match/summary/").json()
        self.assertEqual(summary["new"], body["summary"]["new"])
        self.assertIn("new_unassigned_count", summary)
        first = body["results"][0]
        self.assertIn("request_number", first)
        self.assertNotEqual(first["customer"]["name"], str(first["customer"]["id"]))
        self.assertEqual(first["assigned_to"], None)

    def test_pagination_and_filters(self):
        self._login("root")
        page = self.client.get("/api/match/requests/", {"page": 1, "page_size": 1, "ordering": "created_at"})
        self.assertEqual(page.status_code, 200)
        body = page.json()
        self.assertEqual(len(body["results"]), 1)
        self.assertTrue(body["has_next"])
        filtered = self.client.get(
            "/api/match/requests/",
            {"type": "inquiry", "priority": "normal", "property": self.kl.pk, "search": "Family"},
        )
        self.assertEqual(filtered.status_code, 200)
        results = filtered.json()["results"]
        self.assertTrue(results)
        self.assertTrue(all(item["request_type"] == "inquiry" for item in results))
        self.assertTrue(all(item["property"]["id"] == self.kl.pk for item in results))
        unassigned = self.client.get("/api/match/requests/", {"unassigned_only": "1"}).json()
        self.assertTrue(all(item["assigned_to"] is None for item in unassigned["results"]))

    def test_manual_create_and_detail(self):
        self._login("root")
        created = self._create_manual(source_ref="manual-unique-1", priority="high")
        self.assertEqual(created.status_code, 201, created.content)
        payload = created.json()
        self.assertEqual(payload["status"], "new")
        self.assertEqual(payload["priority"], "high")
        detail = self.client.get(f"/api/match/requests/{payload['id']}/")
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["customer"]["name"], "John Smith")
        self.assertEqual(body["property"]["name"], "Hotel KL")
        self.assertIn("history", body)
        self.assertIn("assignable_staff", body)
        self.assertTrue(any(user["id"] == self.staff.pk for user in body["assignable_staff"]))

    def test_assign_reassign_unassign_and_history(self):
        item = MatchRequest.objects.get(source_ref=f"case:{self.kl_case.pk}")
        self._login("manager.pat")
        assigned = self.client.post(
            f"/api/match/requests/{item.pk}/assign/",
            data={"assigned_to_id": self.staff.pk},
            content_type="application/json",
        )
        self.assertEqual(assigned.status_code, 200, assigned.content)
        body = assigned.json()
        self.assertEqual(body["status"], "assigned")
        self.assertEqual(body["assigned_to"]["id"], self.staff.pk)
        self.assertEqual(body["assigned_to"]["display_name"], "Aiman Rahman")
        self.assertEqual(body["assigned_to"]["role_name"], "Staff")
        again = self.client.post(
            f"/api/match/requests/{item.pk}/assign/",
            data={"assigned_to_id": self.staff.pk},
            content_type="application/json",
        )
        self.assertEqual(again.status_code, 400)
        reassigned = self.client.post(
            f"/api/match/requests/{item.pk}/reassign/",
            data={"assigned_to_id": self.manager.pk},
            content_type="application/json",
        )
        self.assertEqual(reassigned.status_code, 200, reassigned.content)
        self.assertEqual(reassigned.json()["assigned_to"]["id"], self.manager.pk)
        unassigned = self.client.post(f"/api/match/requests/{item.pk}/unassign/", content_type="application/json")
        self.assertEqual(unassigned.status_code, 200)
        self.assertIsNone(unassigned.json()["assigned_to"])
        self.assertEqual(unassigned.json()["status"], "unassigned")
        history = self.client.get(f"/api/match/requests/{item.pk}/history/").json()
        actions = {entry["action"] for entry in history["results"]}
        self.assertIn("created", actions)
        self.assertIn("assigned", actions)
        self.assertIn("reassigned", actions)
        self.assertIn("unassigned", actions)

    def test_status_priority_notes_persist(self):
        item = MatchRequest.objects.get(source_ref=f"case:{self.kl_case.pk}")
        self._login("manager.pat")
        self.client.post(
            f"/api/match/requests/{item.pk}/assign/",
            data={"assigned_to_id": self.staff.pk},
            content_type="application/json",
        )
        status = self.client.patch(
            f"/api/match/requests/{item.pk}/",
            data={"status": "in_progress"},
            content_type="application/json",
        )
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["status"], "in_progress")
        priority = self.client.patch(
            f"/api/match/requests/{item.pk}/",
            data={"priority": "urgent"},
            content_type="application/json",
        )
        self.assertEqual(priority.status_code, 200)
        self.assertEqual(priority.json()["priority"], "urgent")
        notes = self.client.post(
            f"/api/match/requests/{item.pk}/notes/",
            data={"note": "Called the guest; waiting for dates."},
            content_type="application/json",
        )
        self.assertEqual(notes.status_code, 200)
        self.assertIn("Called the guest", notes.json()["internal_notes"])
        resolved = self.client.patch(
            f"/api/match/requests/{item.pk}/",
            data={"status": "resolved", "resolution_notes": "Booked the family room."},
            content_type="application/json",
        )
        self.assertEqual(resolved.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, MatchRequestStatus.RESOLVED)
        self.assertEqual(item.priority, MatchRequestPriority.URGENT)
        self.assertIn("Called the guest", item.internal_notes)
        self.assertEqual(item.resolution_notes, "Booked the family room.")

    def test_manager_is_property_scoped(self):
        kl_item = MatchRequest.objects.get(source_ref=f"case:{self.kl_case.pk}")
        jb_item = MatchRequest.objects.get(source_ref=f"case:{self.jb_case.pk}")
        self._login("manager.pat")
        listing = self.client.get("/api/match/requests/").json()
        ids = {item["id"] for item in listing["results"]}
        self.assertIn(kl_item.pk, ids)
        self.assertNotIn(jb_item.pk, ids)
        self.assertEqual(self.client.get(f"/api/match/requests/{jb_item.pk}/").status_code, 403)
        denied = self.client.post(
            f"/api/match/requests/{jb_item.pk}/assign/",
            data={"assigned_to_id": self.staff.pk},
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

    def test_staff_sees_only_assigned_requests(self):
        kl_item = MatchRequest.objects.get(source_ref=f"case:{self.kl_case.pk}")
        jb_item = MatchRequest.objects.get(source_ref=f"case:{self.jb_case.pk}")
        self._login("root")
        self.client.post(
            f"/api/match/requests/{kl_item.pk}/assign/",
            data={"assigned_to_id": self.staff.pk},
            content_type="application/json",
        )
        self._login("staff.lee")
        listing = self.client.get("/api/match/requests/").json()
        ids = {item["id"] for item in listing["results"]}
        self.assertIn(kl_item.pk, ids)
        self.assertNotIn(jb_item.pk, ids)
        unassigned = MatchRequest.objects.get(source_ref=f"case:{self.jb_case.pk}")
        self.assertEqual(self.client.get(f"/api/match/requests/{unassigned.pk}/").status_code, 403)
        other_unassigned = MatchRequest.objects.exclude(pk=kl_item.pk).filter(property=self.kl).first()
        if other_unassigned:
            self.assertEqual(self.client.get(f"/api/match/requests/{other_unassigned.pk}/").status_code, 403)

    def test_staff_cannot_assign_or_change_priority(self):
        item = MatchRequest.objects.get(source_ref=f"case:{self.kl_case.pk}")
        self._login("staff.lee")
        assign = self.client.post(
            f"/api/match/requests/{item.pk}/assign/",
            data={"assigned_to_id": self.staff.pk},
            content_type="application/json",
        )
        self.assertIn(assign.status_code, {400, 403})
        self._login("root")
        self.client.post(
            f"/api/match/requests/{item.pk}/assign/",
            data={"assigned_to_id": self.staff.pk},
            content_type="application/json",
        )
        self._login("staff.lee")
        priority = self.client.patch(
            f"/api/match/requests/{item.pk}/",
            data={"priority": "urgent"},
            content_type="application/json",
        )
        self.assertEqual(priority.status_code, 403)
        status = self.client.patch(
            f"/api/match/requests/{item.pk}/",
            data={"status": "in_progress"},
            content_type="application/json",
        )
        self.assertEqual(status.status_code, 200)
        notes = self.client.post(
            f"/api/match/requests/{item.pk}/notes/",
            data={"note": "Following up today."},
            content_type="application/json",
        )
        self.assertEqual(notes.status_code, 200)

    def test_staff_cannot_assign_to_manager(self):
        from accounts.catalog import STAFF_PERMISSIONS
        from accounts.models import Role
        from accounts.roles import set_role_permissions

        set_role_permissions(
            Role.objects.get(code=ROLE_STAFF),
            list(STAFF_PERMISSIONS)
            + ["match.view_all_requests", "match.assign_request"],
        )
        item = MatchRequest.objects.get(source_ref=f"case:{self.kl_case.pk}")
        self._login("staff.lee")
        denied = self.client.post(
            f"/api/match/requests/{item.pk}/assign/",
            data={"assigned_to_id": self.manager.pk},
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)
        allowed = self.client.post(
            f"/api/match/requests/{item.pk}/assign/",
            data={"assigned_to_id": self.staff.pk},
            content_type="application/json",
        )
        self.assertEqual(allowed.status_code, 200, allowed.content)

    def test_cannot_assign_inactive_or_cross_property_staff(self):
        item = MatchRequest.objects.get(source_ref=f"case:{self.kl_case.pk}")
        self.other_staff.is_active = False
        self.other_staff.save(update_fields=["is_active"])
        self._login("manager.pat")
        inactive = self.client.post(
            f"/api/match/requests/{item.pk}/assign/",
            data={"assigned_to_id": self.other_staff.pk},
            content_type="application/json",
        )
        self.assertIn(inactive.status_code, {400, 403})
        self.other_staff.is_active = True
        self.other_staff.save(update_fields=["is_active"])
        cross = self.client.post(
            f"/api/match/requests/{item.pk}/assign/",
            data={"assigned_to_id": self.other_staff.pk},
            content_type="application/json",
        )
        self.assertEqual(cross.status_code, 403)

    def test_top_manager_sees_all_properties(self):
        self._login("top.mina")
        listing = self.client.get("/api/match/requests/").json()
        properties = {item["property"]["name"] for item in listing["results"] if item["property"]}
        self.assertIn("Hotel KL", properties)
        self.assertIn("Hotel JB", properties)

    def test_delete_requires_permission(self):
        item = MatchRequest.objects.get(source_ref=f"case:{self.kl_case.pk}")
        self._login("staff.lee")
        self.assertEqual(self.client.delete(f"/api/match/requests/{item.pk}/").status_code, 403)
        self._login("manager.pat")
        self.assertEqual(self.client.delete(f"/api/match/requests/{item.pk}/").status_code, 200)
        self.assertFalse(MatchRequest.objects.filter(pk=item.pk).exists())
