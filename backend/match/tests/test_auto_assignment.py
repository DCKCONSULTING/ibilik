from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF
from accounts.models import Property, UserPropertyAccess
from accounts.services import create_user, initialize_access_control
from cases.services import create_case
from crm.models import Customer
from match.assignment import assign_request_automatically, get_match_settings
from payments.models import PaymentMethod, PaymentType
from payments.services import create_payment
from quotes.services import record_quote_from_case
from match.models import (
    MatchAssignmentMethod,
    MatchHistoryAction,
    MatchRequest,
    MatchRequestStatus,
    MatchRequestType,
)
from match.services import assign_request, ensure_match_request, reassign_request


class AutoAssignmentTests(TestCase):
    def setUp(self):
        initialize_access_control()
        settings = get_match_settings()
        settings.auto_assign_enabled = True
        settings.save(update_fields=["auto_assign_enabled"])
        self.superuser = User.objects.create_superuser("root", "root@example.com", "super-secret-pass")
        self.manager = create_user(
            username="manager.pat",
            password="manager-pass-123",
            first_name="Pat",
            last_name="Manager",
            role=ROLE_MANAGER,
            property_access=UserPropertyAccess.Mode.GLOBAL,
        )
        self.staff_a = create_user(username="staff.a", password="staff-pass-123", first_name="Staff", last_name="A", role=ROLE_STAFF)
        self.staff_b = create_user(username="staff.b", password="staff-pass-123", first_name="Staff", last_name="B", role=ROLE_STAFF)
        self.staff_c = create_user(username="staff.c", password="staff-pass-123", first_name="Staff", last_name="C", role=ROLE_STAFF)
        self.jb_staff = create_user(username="staff.jb", password="staff-pass-123", first_name="Staff", last_name="JB", role=ROLE_STAFF)
        self.kl = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.jb = Property.objects.create(name="Hotel JB", region="Johor", city="Johor Bahru", rate="120.00")
        self.kl.staff.add(self.staff_a, self.staff_b, self.staff_c)
        self.jb.staff.add(self.jb_staff)
        self.customer = Customer.objects.create(name="John Smith", email="john@example.com", phone="+201001234567", property=self.kl)
        self.jb_customer = Customer.objects.create(name="Nour Khaled", email="nour@example.com", phone="+201009999999", property=self.jb)

    def _seed_active(self, staff, count, *, status=MatchRequestStatus.ASSIGNED, offset=0):
        settings = get_match_settings()
        previous = settings.auto_assign_enabled
        settings.auto_assign_enabled = False
        settings.save(update_fields=["auto_assign_enabled"])
        now = timezone.now()
        for index in range(count):
            request, _ = ensure_match_request(
                source_module="match",
                source_ref=f"seed-{staff.username}-{index}-{offset}",
                request_type=MatchRequestType.INQUIRY,
                subject=f"Seed {staff.username} {index}",
                customer=self.customer,
                property_obj=self.kl,
            )
            request.assigned_to = staff
            request.assigned_at = now - timedelta(hours=3, minutes=index)
            request.assignment_method = MatchAssignmentMethod.MANUAL
            request.status = status
            request.save()
        settings.auto_assign_enabled = previous
        settings.save(update_fields=["auto_assign_enabled"])

    def _new_kl_request(self, key):
        request, created = ensure_match_request(
            source_module="match",
            source_ref=f"live-{key}",
            request_type=MatchRequestType.INQUIRY,
            subject=f"New KL request {key}",
            customer=self.customer,
            property_obj=self.kl,
        )
        return request, created

    def test_new_request_is_automatically_assigned_to_lowest_workload(self):
        self._seed_active(self.staff_a, 5)
        self._seed_active(self.staff_b, 2)
        self._seed_active(self.staff_c, 2)
        MatchRequest.objects.filter(assigned_to=self.staff_b).update(assigned_at=timezone.now() - timedelta(minutes=10))
        MatchRequest.objects.filter(assigned_to=self.staff_c).update(assigned_at=timezone.now() - timedelta(hours=2))
        request, created = self._new_kl_request("lowest")
        self.assertTrue(created)
        request.refresh_from_db()
        self.assertEqual(request.assigned_to_id, self.staff_c.pk)
        self.assertEqual(request.assignment_method, MatchAssignmentMethod.AUTOMATIC)
        self.assertEqual(request.status, MatchRequestStatus.ASSIGNED)
        self.assertEqual(request.workload_at_assignment, 2)
        self.assertTrue(request.history.filter(action=MatchHistoryAction.AUTO_ASSIGNED).exists())

    def test_resolved_and_cancelled_are_not_counted(self):
        self._seed_active(self.staff_a, 1, status=MatchRequestStatus.RESOLVED)
        self._seed_active(self.staff_b, 1, status=MatchRequestStatus.CANCELLED)
        self._seed_active(self.staff_c, 2, status=MatchRequestStatus.ASSIGNED)
        request, _ = self._new_kl_request("closed-ignored")
        self.assertIn(request.assigned_to_id, {self.staff_a.pk, self.staff_b.pk})

    def test_other_property_staff_excluded(self):
        self._seed_active(self.staff_a, 4)
        request, _ = self._new_kl_request("property-scope")
        self.assertNotEqual(request.assigned_to_id, self.jb_staff.pk)
        self.assertEqual(request.property_id, self.kl.pk)

    def test_inactive_staff_excluded(self):
        self.staff_a.is_active = False
        self.staff_a.save(update_fields=["is_active"])
        self.staff_b.is_active = False
        self.staff_b.save(update_fields=["is_active"])
        self.staff_c.is_active = False
        self.staff_c.save(update_fields=["is_active"])
        request, _ = self._new_kl_request("inactive")
        self.assertIsNone(request.assigned_to_id)
        self.assertEqual(request.status, MatchRequestStatus.UNASSIGNED)
        self.assertEqual(request.unassigned_reason, "No active staff member is assigned to this property.")

    def test_unauthorized_role_cannot_receive_assignment(self):
        outsider = User.objects.create_user("outsider", password="staff-pass-123", first_name="No", last_name="Perms")
        self.kl.staff.add(outsider)
        self.staff_a.is_active = False
        self.staff_a.save(update_fields=["is_active"])
        self.staff_b.is_active = False
        self.staff_b.save(update_fields=["is_active"])
        self.staff_c.is_active = False
        self.staff_c.save(update_fields=["is_active"])
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        request, _ = self._new_kl_request("no-role")
        self.assertIsNone(request.assigned_to_id)
        self.assertNotEqual(request.assigned_to_id, outsider.pk)

    def test_tie_break_uses_oldest_last_assignment_then_id(self):
        now = timezone.now()
        self._seed_active(self.staff_a, 1)
        self._seed_active(self.staff_b, 1)
        self._seed_active(self.staff_c, 1)
        MatchRequest.objects.filter(assigned_to=self.staff_a).update(assigned_at=now - timedelta(minutes=5))
        MatchRequest.objects.filter(assigned_to=self.staff_b).update(assigned_at=now - timedelta(minutes=10))
        MatchRequest.objects.filter(assigned_to=self.staff_c).update(assigned_at=now - timedelta(hours=2))
        request, _ = self._new_kl_request("tie")
        self.assertEqual(request.assigned_to_id, self.staff_c.pk)

    def test_manual_assignment_is_not_overwritten(self):
        settings = get_match_settings()
        settings.auto_assign_enabled = False
        settings.save(update_fields=["auto_assign_enabled"])
        request, _ = self._new_kl_request("manual")
        assign_request(request, actor=self.manager, assigned_to_id=self.staff_a.pk)
        settings.auto_assign_enabled = True
        settings.save(update_fields=["auto_assign_enabled"])
        again = assign_request_automatically(request)
        self.assertEqual(again.assigned_to_id, self.staff_a.pk)
        self.assertEqual(again.assignment_method, MatchAssignmentMethod.MANUAL)

    def test_manual_reassignment_is_preserved(self):
        self._seed_active(self.staff_a, 4)
        request, _ = self._new_kl_request("reassign")
        self.assertNotEqual(request.assigned_to_id, self.staff_a.pk)
        reassign_request(request, actor=self.manager, assigned_to_id=self.staff_a.pk)
        request.refresh_from_db()
        self.assertEqual(request.assigned_to_id, self.staff_a.pk)
        self.assertEqual(request.assignment_method, MatchAssignmentMethod.REASSIGNED)
        again = assign_request_automatically(request)
        self.assertEqual(again.assigned_to_id, self.staff_a.pk)
        self.assertEqual(again.assignment_method, MatchAssignmentMethod.REASSIGNED)

    def test_duplicate_source_does_not_reassign(self):
        first, created = self._new_kl_request("dup")
        self.assertTrue(created)
        assignee = first.assigned_to_id
        second, created = self._new_kl_request("dup")
        self.assertFalse(created)
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.assigned_to_id, assignee)

    def test_no_eligible_staff_leaves_unassigned(self):
        self.kl.staff.clear()
        request, _ = self._new_kl_request("empty-property")
        self.assertIsNone(request.assigned_to_id)
        self.assertEqual(request.status, MatchRequestStatus.UNASSIGNED)
        self.assertIn("staff", request.unassigned_reason.lower())

    def test_auto_assign_can_be_disabled(self):
        settings = get_match_settings()
        settings.auto_assign_enabled = False
        settings.save(update_fields=["auto_assign_enabled"])
        request, _ = self._new_kl_request("disabled")
        self.assertIsNone(request.assigned_to_id)
        self.assertEqual(request.status, MatchRequestStatus.NEW)

    def test_case_creation_triggers_shared_auto_assign(self):
        self._seed_active(self.staff_a, 3)
        case = create_case(
            actor=self.superuser,
            payload={
                "title": "Auto booking",
                "customer_id": self.customer.pk,
                "property_id": self.kl.pk,
                "original_request": "Need a room tonight.",
            },
        )
        item = MatchRequest.objects.get(source_ref=f"case:{case.pk}")
        self.assertIsNotNone(item.assigned_to_id)
        self.assertEqual(item.assignment_method, MatchAssignmentMethod.AUTOMATIC)
        self.assertNotEqual(item.assigned_to_id, self.jb_staff.pk)

    def test_second_request_updates_workload(self):
        self._seed_active(self.staff_a, 5)
        self._seed_active(self.staff_b, 2)
        self._seed_active(self.staff_c, 2)
        MatchRequest.objects.filter(assigned_to=self.staff_b).update(assigned_at=timezone.now() - timedelta(hours=2))
        MatchRequest.objects.filter(assigned_to=self.staff_c).update(assigned_at=timezone.now() - timedelta(minutes=5))
        first, _ = self._new_kl_request("spread-1")
        second, _ = self._new_kl_request("spread-2")
        self.assertEqual(first.assigned_to_id, self.staff_b.pk)
        self.assertEqual(second.assigned_to_id, self.staff_c.pk)

    def test_api_auto_assign_workload_and_settings(self):
        self._seed_active(self.staff_a, 5)
        self._seed_active(self.staff_b, 1)
        self.client.force_login(self.manager)
        listing = self.client.get("/api/match/staff-workload/", {"property": self.kl.pk})
        self.assertEqual(listing.status_code, 200)
        rows = {item["display_name"]: item for item in listing.json()["results"]}
        self.assertEqual(rows["Staff A"]["active_requests"], 5)
        self.assertTrue(rows["Staff B"]["eligible"])
        settings = self.client.get("/api/match/settings/")
        self.assertEqual(settings.status_code, 200)
        self.assertTrue(settings.json()["auto_assign_enabled"])
        disabled = self.client.patch(
            "/api/match/settings/",
            data={"auto_assign_enabled": False},
            content_type="application/json",
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.json()["auto_assign_enabled"])
        request, _ = self._new_kl_request("api-disabled")
        self.assertIsNone(request.assigned_to_id)
        forced = self.client.post(f"/api/match/requests/{request.pk}/assign-automatically/", content_type="application/json")
        self.assertEqual(forced.status_code, 400)
        self.client.patch("/api/match/settings/", data={"auto_assign_enabled": True}, content_type="application/json")
        assigned = self.client.post(f"/api/match/requests/{request.pk}/assign-automatically/", content_type="application/json")
        self.assertEqual(assigned.status_code, 200, assigned.content)
        self.assertEqual(assigned.json()["assignment_method"], "automatic")
        self.assertEqual(assigned.json()["assigned_to"]["display_name"], "Staff C")

    def test_staff_cannot_change_settings(self):
        self.client.force_login(self.staff_a)
        response = self.client.patch(
            "/api/match/settings/",
            data={"auto_assign_enabled": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_settings_are_account_wide_singleton(self):
        first = get_match_settings()
        first.auto_assign_enabled = False
        first.save(update_fields=["auto_assign_enabled"])
        second = get_match_settings()
        self.assertEqual(first.pk, second.pk)
        self.assertFalse(second.auto_assign_enabled)

    def test_no_property_uses_org_wide_staff_when_enabled(self):
        self._seed_active(self.staff_a, 4)
        request, _ = ensure_match_request(
            source_module="match",
            source_ref="no-property",
            request_type=MatchRequestType.INQUIRY,
            subject="Website inquiry",
            customer=self.customer,
            property_obj=None,
        )
        self.assertIsNotNone(request.assigned_to_id)
        self.assertNotEqual(request.assigned_to_id, self.staff_a.pk)

    def test_no_property_stays_unassigned_when_org_wide_disabled(self):
        settings = get_match_settings()
        settings.org_wide_when_no_property = False
        settings.save(update_fields=["org_wide_when_no_property"])
        request, _ = ensure_match_request(
            source_module="match",
            source_ref="no-property-disabled",
            request_type=MatchRequestType.INQUIRY,
            subject="Website inquiry",
            customer=self.customer,
            property_obj=None,
        )
        self.assertIsNone(request.assigned_to_id)
        self.assertEqual(request.status, MatchRequestStatus.UNASSIGNED)

    def test_quote_and_payment_workflows_auto_assign(self):
        self._seed_active(self.staff_a, 3)
        case = create_case(
            actor=self.superuser,
            payload={
                "title": "Quote stay",
                "customer_id": self.customer.pk,
                "property_id": self.kl.pk,
                "original_request": "Need a quote.",
            },
        )
        quote = record_quote_from_case(case, actor=self.superuser)
        payment = create_payment(
            actor=self.superuser,
            payload={
                "case_id": case.pk,
                "amount": "250.00",
                "payment_type": PaymentType.DEPOSIT,
                "payment_method": PaymentMethod.BANK_TRANSFER,
            },
        )
        quote_request = MatchRequest.objects.get(source_ref=f"quote:{quote.pk}")
        payment_request = MatchRequest.objects.get(source_ref=f"payment:{payment.pk}")
        self.assertEqual(quote_request.assignment_method, MatchAssignmentMethod.AUTOMATIC)
        self.assertEqual(payment_request.assignment_method, MatchAssignmentMethod.AUTOMATIC)
        self.assertIsNotNone(quote_request.assigned_to_id)
        self.assertIsNotNone(payment_request.assigned_to_id)
        self.assertNotEqual(quote_request.assigned_to_id, self.jb_staff.pk)


class ConcurrentAutoAssignmentTests(TestCase):
    def setUp(self):
        initialize_access_control()
        settings = get_match_settings()
        settings.auto_assign_enabled = True
        settings.save(update_fields=["auto_assign_enabled"])
        self.superuser = User.objects.create_superuser("root", "root@example.com", "super-secret-pass")
        self.staff_b = create_user(username="staff.b", password="staff-pass-123", first_name="Staff", last_name="B", role=ROLE_STAFF)
        self.staff_c = create_user(username="staff.c", password="staff-pass-123", first_name="Staff", last_name="C", role=ROLE_STAFF)
        self.kl = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.kl.staff.add(self.staff_b, self.staff_c)
        self.customer = Customer.objects.create(name="John Smith", email="john@example.com", phone="+201001234567", property=self.kl)

    def test_serialized_assignments_do_not_duplicate_the_same_lowest_staff(self):
        created = []
        settings = get_match_settings()
        settings.auto_assign_enabled = False
        settings.save(update_fields=["auto_assign_enabled"])
        for key in ("one", "two"):
            item, _ = ensure_match_request(
                source_module="match",
                source_ref=f"concurrent-{key}",
                request_type=MatchRequestType.INQUIRY,
                subject=key,
                customer=self.customer,
                property_obj=self.kl,
            )
            created.append(item.pk)
        settings.auto_assign_enabled = True
        settings.save(update_fields=["auto_assign_enabled"])
        first = assign_request_automatically(MatchRequest.objects.get(pk=created[0]), force=True)
        second = assign_request_automatically(MatchRequest.objects.get(pk=created[1]), force=True)
        self.assertIsNotNone(first.assigned_to_id)
        self.assertIsNotNone(second.assigned_to_id)
        self.assertNotEqual(first.assigned_to_id, second.assigned_to_id)
