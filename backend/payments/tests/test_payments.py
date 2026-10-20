from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF
from accounts.models import Property, UserPropertyAccess
from accounts.services import create_user, initialize_access_control
from cases.models import ActivityEvent, CaseActivity
from cases.services import create_case
from crm.models import Channel, Conversation, Customer, Message
from payments.models import Payment, PaymentRefund, PaymentStatus, PaymentType, RefundStatus
from payments.services import case_balance, create_payment, refundable_amount
from pipeline.models import PipelineStage


TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
    b"\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


class PaymentApiTests(TestCase):
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
                "stage": PipelineStage.WON,
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
        self.conversation = Conversation.objects.create(
            customer=self.customer,
            property=self.cairo,
            channel=Channel.WHATSAPP,
            subject="Weekend stay",
        )
        self.cairo_case.originating_conversation = self.conversation
        self.cairo_case.save(update_fields=["originating_conversation", "updated_at"])

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

    def _create(self, actor="root", **payload):
        self._login(actor)
        body = {
            "case_id": self.cairo_case.pk,
            "payment_type": "deposit",
            "amount": "5000.00",
            "currency": "MYR",
            "payment_method": "bank_transfer",
            "expected_date": (timezone.now() + timedelta(days=2)).isoformat(),
            "notes": "Booking deposit",
        }
        body.update(payload)
        return self.client.post("/api/payments/", data=body, content_type="application/json")

    def _proof(self, payment_id, actor="staff.lee"):
        self._login(actor)
        uploaded = SimpleUploadedFile("receipt.png", TINY_PNG, content_type="image/png")
        return self.client.post(
            f"/api/payments/{payment_id}/attachments/",
            data={"file": uploaded, "description": "Bank transfer screenshot"},
        )

    def _submit_ready(self, **payload):
        created = self._create(**payload)
        self.assertEqual(created.status_code, 201, created.content)
        payment_id = created.json()["id"]
        upload = self._proof(payment_id)
        self.assertEqual(upload.status_code, 201, upload.content)
        self._login("staff.lee")
        submitted = self.client.post(f"/api/payments/{payment_id}/submit/", content_type="application/json")
        self.assertEqual(submitted.status_code, 200, submitted.content)
        return payment_id

    def test_create_payment_relationships_and_positive_amount(self):
        response = self._create()
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["payment_number"], "PAY-1001")
        self.assertEqual(body["payment_type"], PaymentType.DEPOSIT)
        self.assertEqual(body["amount"], "5000.00")
        self.assertEqual(body["case"]["id"], self.cairo_case.pk)
        self.assertEqual(body["customer"]["id"], self.customer.pk)
        self.assertEqual(body["customer"]["name"], "John Smith")
        self.assertEqual(body["property"]["id"], self.cairo.pk)
        self.assertEqual(body["workflow_status"], PaymentStatus.PENDING)
        payment = Payment.objects.get(pk=body["id"])
        self.assertEqual(payment.case_id, self.cairo_case.pk)
        self.assertEqual(payment.case.customer_id, self.customer.pk)
        self.assertTrue(
            CaseActivity.objects.filter(case=self.cairo_case, event_type=ActivityEvent.PAYMENT_CREATED).exists()
        )
        invalid = self._create(amount="0")
        self.assertEqual(invalid.status_code, 400)
        negative = self._create(amount="-10")
        self.assertEqual(negative.status_code, 400)

    def test_approval_reject_and_audit_fields(self):
        payment_id = self._submit_ready()
        self._login("staff.lee")
        forbidden = self.client.post(f"/api/payments/{payment_id}/approve/", content_type="application/json")
        self.assertEqual(forbidden.status_code, 403)
        self._login("manager.pat")
        approved = self.client.post(f"/api/payments/{payment_id}/approve/", content_type="application/json")
        self.assertEqual(approved.status_code, 200, approved.content)
        body = approved.json()
        self.assertEqual(body["workflow_status"], PaymentStatus.APPROVED)
        self.assertEqual(body["approved_by"]["username"], "manager.pat")
        self.assertIsNotNone(body["approved_at"])
        payment = Payment.objects.get(pk=payment_id)
        self.assertEqual(payment.approved_by_id, self.manager.pk)
        self.assertIsNotNone(payment.approved_at)
        self.assertIsNotNone(payment.paid_at)
        other_id = self._submit_ready(amount="2500.00", payment_type="payment")
        self._login("manager.pat")
        rejected = self.client.post(
            f"/api/payments/{other_id}/reject/",
            data={"rejection_reason": "Receipt is unreadable."},
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 200, rejected.content)
        reject_body = rejected.json()
        self.assertEqual(reject_body["workflow_status"], PaymentStatus.REJECTED)
        self.assertEqual(reject_body["rejected_by"]["username"], "manager.pat")
        self.assertEqual(reject_body["rejection_reason"], "Receipt is unreadable.")
        missing_reason = self._submit_ready(amount="1200.00")
        self._login("manager.pat")
        bad = self.client.post(f"/api/payments/{missing_reason}/reject/", data={}, content_type="application/json")
        self.assertEqual(bad.status_code, 400)

    def test_cannot_arbitrarily_set_status_or_delete_approved(self):
        payment_id = self._submit_ready()
        self._login("manager.pat")
        self.client.post(f"/api/payments/{payment_id}/approve/", content_type="application/json")
        self._login("staff.lee")
        patched = self.client.patch(
            f"/api/payments/{payment_id}/",
            data={"status": "rejected", "amount": "1.00"},
            content_type="application/json",
        )
        self.assertEqual(patched.status_code, 400)
        payment = Payment.objects.get(pk=payment_id)
        self.assertEqual(payment.status, PaymentStatus.APPROVED)
        self.assertEqual(payment.amount, Decimal("5000.00"))
        deleted = self.client.delete(f"/api/payments/{payment_id}/")
        self.assertEqual(deleted.status_code, 400)
        self.assertTrue(Payment.objects.filter(pk=payment_id, status=PaymentStatus.APPROVED).exists())

    def test_deposit_balance_excludes_unapproved(self):
        deposit = create_payment(
            actor=self.superuser,
            payload={"case_id": self.cairo_case.pk, "payment_type": "deposit", "amount": "5000.00"},
        )
        payment = create_payment(
            actor=self.superuser,
            payload={"case_id": self.cairo_case.pk, "payment_type": "payment", "amount": "10000.00"},
        )
        pending = create_payment(
            actor=self.superuser,
            payload={"case_id": self.cairo_case.pk, "payment_type": "payment", "amount": "8000.00"},
        )
        for item in (deposit, payment):
            item.status = PaymentStatus.APPROVED
            item.save(update_fields=["status", "updated_at"])
        pending.status = PaymentStatus.PENDING_APPROVAL
        pending.save(update_fields=["status", "updated_at"])
        balance = case_balance(self.cairo_case)
        self.assertEqual(balance["case_value"], Decimal("30000.00"))
        self.assertEqual(balance["paid"], Decimal("15000.00"))
        self.assertEqual(balance["deposits"], Decimal("5000.00"))
        self.assertEqual(balance["outstanding"], Decimal("15000.00"))
        self._login("root")
        listing = self.client.get("/api/payments/", {"case": self.cairo_case.pk})
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["balance"]["paid"], "15000.00")
        self.assertEqual(listing.json()["balance"]["outstanding"], "15000.00")

    def test_attachments_and_authorization(self):
        created = self._create(actor="staff.lee")
        payment_id = created.json()["id"]
        upload = self._proof(payment_id)
        self.assertEqual(upload.status_code, 201, upload.content)
        self.assertTrue(upload.json()["is_image"])
        self.assertTrue(
            CaseActivity.objects.filter(case=self.cairo_case, event_type=ActivityEvent.PAYMENT_PROOF_UPLOADED).exists()
        )
        self._login("staff.lee")
        download = self.client.get(f"/api/payments/{payment_id}/attachments/{upload.json()['id']}/download/")
        self.assertEqual(download.status_code, 200)
        self._login("staff.other")
        hidden = self.client.get(f"/api/payments/{payment_id}/")
        self.assertEqual(hidden.status_code, 403)
        blocked = self.client.get(f"/api/payments/{payment_id}/attachments/{upload.json()['id']}/download/")
        self.assertEqual(blocked.status_code, 403)
        create_other = self.client.post(
            "/api/payments/",
            data={"case_id": self.cairo_case.pk, "amount": "100.00"},
            content_type="application/json",
        )
        self.assertEqual(create_other.status_code, 403)

    def test_reminders_success_failure_and_activity(self):
        created = self._create(actor="staff.lee")
        payment_id = created.json()["id"]
        self._login("staff.lee")
        with override_settings(WHATSAPP_PROVIDER="test"):
            sent = self.client.post(
                f"/api/payments/{payment_id}/remind/",
                data={"channel": "whatsapp"},
                content_type="application/json",
            )
        self.assertEqual(sent.status_code, 200, sent.content)
        self.assertEqual(sent.json()["status"], "sent")
        self.assertEqual(sent.json()["channel"], "whatsapp")
        self.assertTrue(Message.objects.filter(conversation=self.conversation, direction="outbound").exists())
        self.assertTrue(
            CaseActivity.objects.filter(
                case=self.cairo_case,
                event_type=ActivityEvent.PAYMENT_REMINDER_SENT,
                message__contains="WhatsApp",
            ).exists()
        )
        failed_message = Message(
            conversation=self.conversation,
            channel=Channel.WHATSAPP,
            content="failed",
            status="failed",
            error_message="WhatsApp delivery is not configured.",
        )
        with patch("payments.services.send_outbound_message", return_value=failed_message):
            failed = self.client.post(
                f"/api/payments/{payment_id}/remind/",
                data={"channel": "whatsapp"},
                content_type="application/json",
            )
        self.assertEqual(failed.status_code, 502)
        self.assertEqual(failed.json()["code"], "reminder_failed")
        website = self.client.post(
            f"/api/payments/{payment_id}/remind/",
            data={"channel": "website"},
            content_type="application/json",
        )
        self.assertEqual(website.status_code, 403)
        self._login("staff.other")
        other = self.client.post(
            f"/api/payments/{payment_id}/remind/",
            data={"channel": "whatsapp"},
            content_type="application/json",
        )
        self.assertEqual(other.status_code, 403)

    def test_refunds_limits_and_workflow(self):
        payment_id = self._submit_ready()
        self._login("manager.pat")
        self.client.post(f"/api/payments/{payment_id}/approve/", content_type="application/json")
        self._login("staff.lee")
        first = self.client.post(
            f"/api/payments/{payment_id}/refund/",
            data={"amount": "3000.00", "reason": "Guest shortened stay."},
            content_type="application/json",
        )
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(first.json()["refund_number"], "REF-1001")
        self.assertEqual(first.json()["status"], RefundStatus.PENDING_APPROVAL)
        overflow = self.client.post(
            f"/api/payments/{payment_id}/refund/",
            data={"amount": "2500.00", "reason": "Too much"},
            content_type="application/json",
        )
        self.assertEqual(overflow.status_code, 400)
        self.assertEqual(overflow.json()["code"], "invalid_refund_amount")
        refund_id = first.json()["id"]
        self._login("staff.lee")
        staff_approve = self.client.post(f"/api/refunds/{refund_id}/approve/", content_type="application/json")
        self.assertEqual(staff_approve.status_code, 403)
        self._login("manager.pat")
        approved = self.client.post(f"/api/refunds/{refund_id}/approve/", content_type="application/json")
        self.assertEqual(approved.status_code, 200)
        completed = self.client.post(f"/api/refunds/{refund_id}/complete/", content_type="application/json")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], RefundStatus.COMPLETED)
        payment = Payment.objects.get(pk=payment_id)
        self.assertEqual(payment.status, PaymentStatus.APPROVED)
        self.assertEqual(refundable_amount(payment), Decimal("2000.00"))
        second = self.client.post(
            "/api/refunds/",
            data={"payment_id": payment_id, "amount": "2000.00", "reason": "Final adjustment"},
            content_type="application/json",
        )
        self.assertEqual(second.status_code, 201, second.content)
        rejected = self.client.post(
            f"/api/refunds/{second.json()['id']}/reject/",
            data={"reason": "Keep the remaining amount."},
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.json()["status"], RefundStatus.REJECTED)
        self.assertEqual(refundable_amount(Payment.objects.get(pk=payment_id)), Decimal("2000.00"))
        balance = case_balance(self.cairo_case)
        self.assertEqual(balance["refunded"], Decimal("3000.00"))
        self.assertEqual(balance["outstanding"], Decimal("28000.00"))

    def test_list_search_filters_pagination_and_overdue(self):
        overdue = create_payment(
            actor=self.superuser,
            payload={
                "case_id": self.cairo_case.pk,
                "payment_type": "deposit",
                "amount": "1111.00",
                "expected_date": (timezone.now() - timedelta(days=2)).isoformat(),
            },
        )
        create_payment(
            actor=self.superuser,
            payload={
                "case_id": self.alex_case.pk,
                "amount": "2222.00",
                "expected_date": (timezone.now() + timedelta(days=1)).isoformat(),
            },
        )
        for index in range(12):
            create_payment(
                actor=self.superuser,
                payload={"case_id": self.cairo_case.pk, "amount": f"{100 + index}.00"},
            )
        self._login("root")
        listing = self.client.get("/api/payments/", {"page_size": 10, "page": 1})
        self.assertEqual(listing.status_code, 200)
        body = listing.json()
        self.assertEqual(body["resource"], "payments")
        self.assertGreaterEqual(body["count"], 14)
        self.assertEqual(len(body["results"]), 10)
        self.assertTrue(body["has_next"])
        self.assertIn("expected_label", body["summary"])
        search = self.client.get("/api/payments/", {"search": "PAY-1001"}).json()
        self.assertEqual(search["count"], 1)
        self.assertEqual(search["results"][0]["payment_number"], "PAY-1001")
        by_case = self.client.get("/api/payments/", {"search": self.cairo_case.case_number}).json()
        self.assertGreaterEqual(by_case["count"], 13)
        by_name = self.client.get("/api/payments/", {"search": "John Smith"}).json()
        self.assertTrue(all(item["customer"]["name"] == "John Smith" for item in by_name["results"]))
        by_phone = self.client.get("/api/payments/", {"search": "201001234567"}).json()
        self.assertGreaterEqual(by_phone["count"], 1)
        deposits = self.client.get("/api/payments/", {"payment_type": "deposit"}).json()
        self.assertTrue(all(item["payment_type"] == "deposit" for item in deposits["results"]))
        overdue_list = self.client.get("/api/payments/", {"status": "overdue"}).json()
        self.assertGreaterEqual(overdue_list["count"], 1)
        self.assertTrue(any(item["id"] == overdue.pk and item["status"] == "overdue" for item in overdue_list["results"]))
        by_property = self.client.get("/api/payments/", {"property": self.alex.pk}).json()
        self.assertTrue(all(item["property"]["id"] == self.alex.pk for item in by_property["results"]))
        by_staff = self.client.get("/api/payments/", {"staff": self.cairo_staff.pk}).json()
        self.assertTrue(all(item["staff"]["id"] == self.cairo_staff.pk for item in by_staff["results"]))
        self._login("staff.lee")
        scoped = self.client.get("/api/payments/").json()
        self.assertTrue(all(item["property"]["id"] == self.cairo.pk for item in scoped["results"]))
        detail = self.client.get(f"/api/payments/{overdue.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["workflow_status"], PaymentStatus.PENDING)
        self.assertTrue(detail.json()["is_overdue"])

    def test_superuser_unrestricted_and_staff_property_scope(self):
        created = self._create(actor="root", case_id=self.alex_case.pk, amount="900.00")
        self.assertEqual(created.status_code, 201)
        payment_id = created.json()["id"]
        self._login("root")
        self.assertEqual(self.client.get(f"/api/payments/{payment_id}/").status_code, 200)
        self._login("staff.lee")
        self.assertEqual(self.client.get(f"/api/payments/{payment_id}/").status_code, 403)
        self._login("staff.other")
        self.assertEqual(self.client.get(f"/api/payments/{payment_id}/").status_code, 200)
        global_staff = create_user(
            username="staff.global",
            password="staff-pass-123",
            role=ROLE_STAFF,
            property_access=UserPropertyAccess.Mode.GLOBAL,
            actor=self.superuser,
        )
        self._login("staff.global")
        self.assertEqual(self.client.get(f"/api/payments/{payment_id}/").status_code, 200)
        self.assertGreaterEqual(self.client.get("/api/payments/").json()["count"], 1)
        self.assertIsNotNone(global_staff.pk)
