from django.contrib.auth.models import User
from django.test import TestCase

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF, ROLE_TOP_MANAGER
from accounts.models import Property, PropertyStaffAssignment
from accounts.scope import get_subordinate_user_ids, get_visible_users, require_visible_property, ScopeError
from accounts.services import create_user, initialize_access_control
from cases.models import FollowUpType
from cases.services import create_case, create_follow_up
from crm.models import Customer
from pipeline.models import PipelineStage


class AuthorityScopeTests(TestCase):
    def setUp(self):
        initialize_access_control()
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
        self.other_manager = create_user(
            username="manager.other",
            password="manager-pass-123",
            first_name="Other",
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
        self.peer_staff = create_user(
            username="staff.peer",
            password="staff-pass-123",
            first_name="Peer",
            last_name="Staff",
            role=ROLE_STAFF,
        )
        self.kl = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.jb = Property.objects.create(name="Hotel JB", region="Johor", city="Johor Bahru", rate="120.00")
        self.kl.staff.add(self.manager, self.staff, self.peer_staff)
        self.jb.staff.add(self.other_manager, self.other_staff)
        PropertyStaffAssignment.objects.create(property=self.kl, user=self.staff, reports_to=self.manager, role=ROLE_STAFF)
        PropertyStaffAssignment.objects.create(property=self.kl, user=self.peer_staff, reports_to=self.manager, role=ROLE_STAFF)
        self.kl_customer = Customer.objects.create(name="John Smith", email="john@example.com", phone="+20100111", property=self.kl)
        self.jb_customer = Customer.objects.create(name="Nour Khaled", email="nour@example.com", phone="+20100999", property=self.jb)
        self.kl_case = create_case(
            actor=self.superuser,
            payload={
                "title": "KL stay",
                "customer_id": self.kl_customer.pk,
                "property_id": self.kl.pk,
                "assigned_to_id": self.staff.pk,
                "stage": PipelineStage.QUALIFIED,
            },
        )
        self.jb_case = create_case(
            actor=self.superuser,
            payload={
                "title": "JB stay",
                "customer_id": self.jb_customer.pk,
                "property_id": self.jb.pk,
                "assigned_to_id": self.other_staff.pk,
                "stage": PipelineStage.NEW,
            },
        )
        self.own_follow_up = create_follow_up(
            self.kl_case,
            {"type": FollowUpType.CALL_CUSTOMER, "title": "Call KL guest", "assigned_to_id": self.staff.pk},
            actor=self.superuser,
        )
        self.other_follow_up = create_follow_up(
            self.jb_case,
            {"type": FollowUpType.CALL_CUSTOMER, "title": "Call JB guest", "assigned_to_id": self.other_staff.pk},
            actor=self.superuser,
        )
        self.peer_follow_up = create_follow_up(
            self.kl_case,
            {"type": FollowUpType.FOLLOW_UP, "title": "Peer staff follow-up", "assigned_to_id": self.peer_staff.pk},
            actor=self.superuser,
        )

    def _login(self, username, password):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["user"]

    def test_system_admin_me_and_full_access(self):
        me = self._login("root", "super-secret-pass")
        self.assertEqual(me["role_name"], "System Admin")
        self.assertEqual(me["property_scope_label"], "All authorized properties")
        self.assertTrue(any(item["name"] == "Hotel KL" for item in me["visible_properties"]))
        self.assertEqual(self.client.get("/api/users/").status_code, 200)
        self.assertEqual(self.client.get("/api/roles/").status_code, 200)
        self.assertEqual(self.client.get("/api/follow-ups/", {"status": "all"}).json()["count"], 3)
        self.assertEqual(self.client.get(f"/api/follow-ups/{self.other_follow_up.pk}/").status_code, 200)

    def test_top_manager_sees_subordinate_managers_and_staff(self):
        me = self._login("top.mina", "top-pass-12345")
        self.assertEqual(me["role_name"], "Top Manager")
        self.assertEqual(me["property_scope_label"], "All authorized properties")
        users = {item["username"] for item in self.client.get("/api/users/").json()["results"]}
        self.assertIn("manager.pat", users)
        self.assertIn("staff.lee", users)
        self.assertIn("manager.other", users)
        self.assertNotIn("root", users)
        names = {item["name"] for item in self.client.get("/api/properties/").json()["results"]}
        self.assertEqual(names, {"Hotel KL", "Hotel JB"})

    def test_manager_sees_subordinate_staff_not_peer_manager(self):
        self._login("manager.pat", "manager-pass-123")
        users = {item["username"] for item in self.client.get("/api/users/").json()["results"]}
        self.assertIn("staff.lee", users)
        self.assertIn("manager.pat", users)
        self.assertNotIn("manager.other", users)
        self.assertNotIn("staff.other", users)
        properties = [item["name"] for item in self.client.get("/api/properties/").json()["results"]]
        self.assertEqual(properties, ["Hotel KL"])
        self.assertEqual(self.client.get(f"/api/properties/{self.jb.pk}/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/cases/{self.jb_case.pk}/").status_code, 403)
        follow_ups = self.client.get("/api/follow-ups/", {"status": "all"}).json()
        titles = {item["title"] for item in follow_ups["results"]}
        self.assertIn("Call KL guest", titles)
        self.assertIn("Peer staff follow-up", titles)
        self.assertNotIn("Call JB guest", titles)

    def test_staff_sees_own_assigned_follow_up_not_peer_workload(self):
        me = self._login("staff.lee", "staff-pass-123")
        self.assertEqual(me["role_name"], "Staff")
        self.assertEqual([item["name"] for item in me["assigned_properties"]], ["Hotel KL"])
        self.assertIsNone(me["property_scope_label"])
        self.assertEqual(self.client.get("/api/users/").status_code, 403)
        self.assertEqual(self.client.get("/api/roles/").status_code, 403)
        follow_ups = self.client.get("/api/follow-ups/", {"status": "all"}).json()
        self.assertEqual(follow_ups["count"], 1)
        self.assertEqual(follow_ups["results"][0]["title"], "Call KL guest")
        self.assertEqual(self.client.get(f"/api/follow-ups/{self.peer_follow_up.pk}/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/follow-ups/{self.other_follow_up.pk}/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/bookings/?property={self.jb.pk}").status_code, 403)
        self.assertEqual(self.client.get(f"/api/dashboard/?property={self.jb.pk}").status_code, 403)
        customers = self.client.get("/api/customers/").json()["results"]
        self.assertTrue(all(item["name"] != "Nour Khaled" for item in customers))

    def test_property_query_tampering_is_forbidden(self):
        self._login("manager.pat", "manager-pass-123")
        self.assertEqual(self.client.get("/api/customers/", {"property": self.jb.pk}).status_code, 403)
        self.assertEqual(self.client.get("/api/quotes/", {"property": self.jb.pk}).status_code, 403)
        self.assertEqual(self.client.get("/api/payments/", {"property": self.jb.pk}).status_code, 403)
        self.assertEqual(self.client.get("/api/match/requests/", {"property": self.jb.pk}).status_code, 403)

    def test_subordinate_ids_use_reports_to(self):
        self.assertIn(self.staff.pk, get_subordinate_user_ids(self.manager))
        self.assertNotIn(self.other_staff.pk, get_subordinate_user_ids(self.manager))
        self.assertNotIn(self.other_manager.pk, get_visible_users(self.manager).values_list("pk", flat=True))

    def test_require_visible_property_rejects_foreign_property(self):
        with self.assertRaises(ScopeError) as ctx:
            require_visible_property(self.staff, self.jb.pk)
        self.assertEqual(ctx.exception.status, 403)
        self.assertEqual(require_visible_property(self.staff, self.kl.pk).pk, self.kl.pk)
