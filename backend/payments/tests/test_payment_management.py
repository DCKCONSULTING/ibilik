from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF
from accounts.models import Property
from accounts.services import create_user, initialize_access_control
from cases.models import Case
from cases.services import create_case
from crm.models import Customer
from locations.models import Location, LocationStatus, LocationType
from payments.models import CaseCharge, ChargeKind, ChargeStatus, Payment, PaymentStatus, RefundStatus
from payments.services import case_balance, create_payment
from pipeline.models import PipelineStage


class PaymentManagementTests(TestCase):
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
        self.staff = create_user(
            username="staff.lee",
            password="staff-pass-123",
            first_name="Aiman",
            last_name="Rahman",
            role=ROLE_STAFF,
        )
        self.hotel = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.hotel.staff.add(self.staff, self.manager)
        self.customer = Customer.objects.create(
            name="John Smith",
            email="john@example.com",
            phone="+201001234567",
            property=self.hotel,
        )
        self.location = Location.objects.create(
            property=self.hotel,
            name="Deluxe Room 103",
            code="103",
            location_type=LocationType.ROOM,
            status=LocationStatus.AVAILABLE,
            is_bookable=True,
            active=True,
        )
        self.case = create_case(
            actor=self.superuser,
            payload={
                "title": "Family room",
                "customer_id": self.customer.pk,
                "property_id": self.hotel.pk,
                "assigned_to_id": self.staff.pk,
                "source": "whatsapp",
                "stage": PipelineStage.WON,
                "value": "300.00",
            },
        )
        self.case.location = self.location
        self.case.save(update_fields=["location", "updated_at"])

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

    def _seed_payment(self, *, amount="100.00", received=True, actor="manager.pat"):
        self._login(actor)
        response = self.client.post(
            "/api/payments/",
            data={
                "case_id": self.case.pk,
                "payment_type": "payment",
                "amount": amount,
                "currency": "MYR",
                "payment_method": "cash",
                "received": received,
                "notes": "Front desk cash",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_open_payment_shows_reservation_and_balance(self):
        created = self._seed_payment()
        self._login("staff.lee")
        detail = self.client.get(f"/api/payments/{created['id']}/")
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["customer"]["name"], "John Smith")
        self.assertEqual(body["case"]["case_number"], self.case.case_number)
        self.assertEqual(body["property"]["name"], "Hotel KL")
        self.assertEqual(body["location"]["name"], "Deluxe Room 103")
        self.assertEqual(body["balance"]["room_charges"], "300.00")
        self.assertEqual(body["balance"]["paid"], "100.00")
        self.assertEqual(body["balance"]["outstanding"], "200.00")
        self.assertEqual(body["balance"]["account_status"], "partially_paid")
        self.assertTrue(any(row["type"] == "charge" and row["description"] == "Room booking" for row in body["ledger"]))

    def test_add_received_payment_updates_paid_and_status(self):
        first = self._seed_payment(amount="100.00")
        self._login("manager.pat")
        second = self.client.post(
            "/api/payments/",
            data={
                "case_id": self.case.pk,
                "payment_type": "payment",
                "amount": "200.00",
                "payment_method": "cash",
                "received": True,
                "idempotency_key": "pay-once",
            },
            content_type="application/json",
        )
        self.assertEqual(second.status_code, 201, second.content)
        refreshed = self.client.get(f"/api/payments/{first['id']}/").json()
        self.assertEqual(refreshed["balance"]["paid"], "300.00")
        self.assertEqual(refreshed["balance"]["outstanding"], "0.00")
        self.assertEqual(refreshed["balance"]["account_status"], "paid")
        self.assertEqual(Payment.objects.filter(case=self.case, status=PaymentStatus.APPROVED).count(), 2)

    def test_add_charge_increases_total_and_balance(self):
        payment = self._seed_payment()
        self._login("staff.lee")
        response = self.client.post(
            f"/api/payments/{payment['id']}/charges/",
            data={
                "category": "extra_bed",
                "description": "Extra bed",
                "quantity": "1",
                "unit_price": "50.00",
                "tax": "0",
                "idempotency_key": "charge-bed",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        balance = response.json()["balance"]
        self.assertEqual(balance["extra_charges"], "50.00")
        self.assertEqual(balance["total_charges"], "350.00")
        self.assertEqual(balance["outstanding"], "250.00")
        self.assertTrue(any(row["type"] == "charge" and row["description"] == "Extra bed" for row in response.json()["ledger"]))
        self.assertEqual(CaseCharge.objects.filter(case=self.case, kind=ChargeKind.CHARGE).count(), 1)

    def test_add_penalty_requires_reason_and_updates_balance(self):
        payment = self._seed_payment()
        self._login("staff.lee")
        missing = self.client.post(
            f"/api/payments/{payment['id']}/penalties/",
            data={"category": "late_checkout", "amount": "25.00"},
            content_type="application/json",
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()["code"], "invalid_reason")
        created = self.client.post(
            f"/api/payments/{payment['id']}/penalties/",
            data={
                "category": "late_checkout",
                "description": "Late checkout",
                "amount": "25.00",
                "reason": "Checked out after 2pm",
            },
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        balance = created.json()["balance"]
        self.assertEqual(balance["penalties"], "25.00")
        self.assertEqual(balance["outstanding"], "225.00")
        row = next(item for item in created.json()["ledger"] if item["type"] == "penalty")
        self.assertEqual(row["reason"], "Checked out after 2pm")

    def test_refund_preserves_original_and_recalculates(self):
        payment = self._seed_payment(amount="200.00")
        self._login("manager.pat")
        refund = self.client.post(
            f"/api/payments/{payment['id']}/refund/",
            data={"amount": "50.00", "reason": "Deposit refund", "complete": True},
            content_type="application/json",
        )
        self.assertEqual(refund.status_code, 201, refund.content)
        self.assertEqual(refund.json()["status"], RefundStatus.COMPLETED)
        original = Payment.objects.get(pk=payment["id"])
        self.assertEqual(original.status, PaymentStatus.APPROVED)
        self.assertEqual(original.amount, Decimal("200.00"))
        detail = self.client.get(f"/api/payments/{payment['id']}/").json()
        self.assertEqual(detail["balance"]["paid"], "200.00")
        self.assertEqual(detail["balance"]["refunded"], "50.00")
        self.assertEqual(detail["balance"]["outstanding"], "150.00")
        self.assertTrue(any(row["type"] == "refund" and row["reason"] == "Deposit refund" for row in detail["ledger"]))

    def test_duplicate_payment_idempotency(self):
        self._login("manager.pat")
        payload = {
            "case_id": self.case.pk,
            "amount": "80.00",
            "payment_method": "cash",
            "received": True,
            "idempotency_key": "same-click",
        }
        first = self.client.post("/api/payments/", data=payload, content_type="application/json")
        second = self.client.post("/api/payments/", data=payload, content_type="application/json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(Payment.objects.filter(case=self.case).count(), 1)

    def test_invalid_refund_amount_is_rejected(self):
        payment = self._seed_payment(amount="100.00")
        self._login("manager.pat")
        overflow = self.client.post(
            f"/api/payments/{payment['id']}/refund/",
            data={"amount": "150.00", "reason": "Too much"},
            content_type="application/json",
        )
        self.assertEqual(overflow.status_code, 400)
        self.assertEqual(overflow.json()["code"], "invalid_refund_amount")
        self.assertEqual(Payment.objects.get(pk=payment["id"]).refunds.count(), 0)

    def test_staff_cannot_void_or_complete_refund(self):
        payment = self._seed_payment()
        self._login("staff.lee")
        charge = self.client.post(
            f"/api/payments/{payment['id']}/charges/",
            data={"category": "laundry", "unit_price": "20.00", "description": "Laundry"},
            content_type="application/json",
        )
        self.assertEqual(charge.status_code, 201, charge.content)
        charge_id = charge.json()["charges"][0]["id"]
        voided = self.client.post(
            f"/api/charges/{charge_id}/void/",
            data={"reason": "Entered by mistake"},
            content_type="application/json",
        )
        self.assertEqual(voided.status_code, 403)
        refund = self.client.post(
            f"/api/payments/{payment['id']}/refund/",
            data={"amount": "10.00", "reason": "Guest request", "complete": True},
            content_type="application/json",
        )
        self.assertEqual(refund.status_code, 201, refund.content)
        self.assertEqual(refund.json()["status"], RefundStatus.PENDING_APPROVAL)
        self.assertEqual(case_balance(self.case)["refunded"], Decimal("0.00"))

    def test_manager_void_preserves_history_and_updates_balance(self):
        payment = self._seed_payment()
        self._login("staff.lee")
        charge = self.client.post(
            f"/api/payments/{payment['id']}/charges/",
            data={"category": "damage", "unit_price": "40.00", "description": "Damage charge"},
            content_type="application/json",
        )
        charge_id = charge.json()["charges"][0]["id"]
        self._login("manager.pat")
        voided = self.client.post(
            f"/api/charges/{charge_id}/void/",
            data={"reason": "Charged the wrong room"},
            content_type="application/json",
        )
        self.assertEqual(voided.status_code, 200, voided.content)
        record = CaseCharge.objects.get(pk=charge_id)
        self.assertEqual(record.status, ChargeStatus.VOIDED)
        self.assertEqual(record.void_reason, "Charged the wrong room")
        self.assertIsNotNone(record.voided_at)
        self.assertEqual(voided.json()["balance"]["extra_charges"], "0.00")
        self.assertEqual(voided.json()["balance"]["outstanding"], "200.00")
        self.assertTrue(CaseCharge.objects.filter(pk=charge_id).exists())

    def test_pending_payment_is_excluded_from_paid(self):
        created = create_payment(
            actor=self.superuser,
            payload={"case_id": self.case.pk, "amount": "80.00", "payment_method": "bank_transfer"},
        )
        self.assertEqual(created.status, PaymentStatus.PENDING)
        balance = case_balance(self.case)
        self.assertEqual(balance["paid"], Decimal("0.00"))
        self.assertEqual(balance["outstanding"], Decimal("300.00"))
        self.assertEqual(balance["account_status"], "unpaid")

    def test_checkout_requires_settled_balance_or_override(self):
        stay = Case.objects.get(pk=self.case.pk)
        stay.actual_check_in = timezone.now()
        stay.save(update_fields=["actual_check_in", "updated_at"])
        self._login("staff.lee")
        blocked = self.client.post(
            f"/api/locations/{self.location.pk}/check-out/",
            data={"case_id": stay.pk},
            content_type="application/json",
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["code"], "payment_required")
        staff_override = self.client.post(
            f"/api/locations/{self.location.pk}/check-out/",
            data={"case_id": stay.pk, "override": True},
            content_type="application/json",
        )
        self.assertEqual(staff_override.status_code, 403)
        self._login("manager.pat")
        allowed = self.client.post(
            f"/api/locations/{self.location.pk}/check-out/",
            data={"case_id": stay.pk, "override": True},
            content_type="application/json",
        )
        self.assertEqual(allowed.status_code, 200, allowed.content)
        stay.refresh_from_db()
        self.assertIsNotNone(stay.actual_check_out)
        self.assertEqual(case_balance(stay)["account_status"], "unpaid")
