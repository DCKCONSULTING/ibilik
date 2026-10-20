from django.contrib.auth.models import User
from django.test import TestCase

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF
from accounts.models import Property, PropertyStaffAssignment
from accounts.services import create_user, initialize_access_control


class PropertyStaffHierarchyTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.superuser = User.objects.create_superuser(
            username="root",
            email="root@example.com",
            password="super-secret-pass",
        )
        self.manager = create_user(
            username="manager.pat",
            password="manager-pass-123",
            first_name="Pat",
            last_name="Manager",
            role=ROLE_MANAGER,
        )
        self.lee = create_user(
            username="staff.lee",
            password="staff-pass-123",
            first_name="Lee",
            last_name="Staff",
            role=ROLE_STAFF,
        )
        self.omar = create_user(
            username="staff.omar",
            password="staff-pass-123",
            first_name="Omar",
            last_name="Other",
            role=ROLE_STAFF,
        )
        self.kl = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.penang = Property.objects.create(name="Hotel Penang", region="Penang", city="George Town", rate="120.00")
        self.kl.staff.add(self.manager, self.lee)
        self.penang.staff.add(self.omar)

    def _login(self, username, password):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def test_staff_list_returns_names_roles_and_preserves_assignments(self):
        self._login("manager.pat", "manager-pass-123")
        response = self.client.get(f"/api/properties/{self.kl.pk}/staff/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        names = {item["display_name"] for item in payload["results"]}
        self.assertEqual(names, {"Pat Manager", "Lee Staff"})
        self.assertTrue(all(item["role"] and item["role"]["name"] for item in payload["results"]))
        self.assertFalse(any(str(item["role"]["id"]) == item["display_name"] for item in payload["results"]))
        role_names = {item["name"] for item in payload["roles"]}
        self.assertIn("Manager", role_names)
        self.assertIn("Staff", role_names)
        self.assertTrue(self.kl.staff.filter(pk=self.manager.pk).exists())
        self.assertTrue(self.kl.staff.filter(pk=self.lee.pk).exists())

    def test_assign_staff_with_role_from_catalog(self):
        self._login("manager.pat", "manager-pass-123")
        response = self.client.post(
            f"/api/properties/{self.kl.pk}/staff/",
            data={"user_id": self.omar.pk, "role": "STAFF", "reports_to_id": self.manager.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        omar = next(item for item in response.json()["results"] if item["id"] == self.omar.pk)
        self.assertEqual(omar["display_name"], "Omar Other")
        self.assertEqual(omar["role"]["id"], "STAFF")
        self.assertEqual(omar["role"]["name"], "Staff")
        self.assertEqual(omar["reports_to"]["id"], self.manager.pk)
        self.assertEqual(omar["reports_to"]["name"], "Pat Manager")
        self.assertTrue(self.kl.staff.filter(pk=self.omar.pk).exists())

    def test_change_role_and_manager(self):
        self._login("root", "super-secret-pass")
        assigned = self.client.post(
            f"/api/properties/{self.kl.pk}/staff/",
            data={"user_id": self.omar.pk, "role": "STAFF"},
            content_type="application/json",
        )
        self.assertEqual(assigned.status_code, 201)
        updated = self.client.patch(
            f"/api/properties/{self.kl.pk}/staff/{self.omar.pk}/",
            data={"role": "MANAGER", "reports_to_id": self.lee.pk},
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        omar = next(item for item in updated.json()["results"] if item["id"] == self.omar.pk)
        self.assertEqual(omar["role"]["name"], "Manager")
        self.assertEqual(omar["reports_to"]["name"], "Lee Staff")

    def test_hierarchy_levels_and_no_manager(self):
        self._login("root", "super-secret-pass")
        self.client.post(
            f"/api/properties/{self.kl.pk}/staff/",
            data={"user_id": self.omar.pk, "role": "STAFF", "reports_to_id": self.lee.pk},
            content_type="application/json",
        )
        self.client.patch(
            f"/api/properties/{self.kl.pk}/staff/{self.lee.pk}/",
            data={"reports_to_id": self.manager.pk},
            content_type="application/json",
        )
        payload = self.client.get(f"/api/properties/{self.kl.pk}/staff/").json()
        hierarchy = payload["hierarchy"]
        self.assertEqual(len(hierarchy), 1)
        self.assertEqual(hierarchy[0]["display_name"], "Pat Manager")
        self.assertEqual(hierarchy[0]["reports"][0]["display_name"], "Lee Staff")
        self.assertEqual(hierarchy[0]["reports"][0]["reports"][0]["display_name"], "Omar Other")

    def test_self_and_circular_reporting_rejected(self):
        self._login("root", "super-secret-pass")
        self_report = self.client.patch(
            f"/api/properties/{self.kl.pk}/staff/{self.lee.pk}/",
            data={"reports_to_id": self.lee.pk},
            content_type="application/json",
        )
        self.assertEqual(self_report.status_code, 400)
        self.client.patch(
            f"/api/properties/{self.kl.pk}/staff/{self.lee.pk}/",
            data={"reports_to_id": self.manager.pk},
            content_type="application/json",
        )
        cycle = self.client.patch(
            f"/api/properties/{self.kl.pk}/staff/{self.manager.pk}/",
            data={"reports_to_id": self.lee.pk},
            content_type="application/json",
        )
        self.assertEqual(cycle.status_code, 400)
        self.assertIn("circular", cycle.json()["message"].lower())

    def test_cross_property_manager_rejected(self):
        self._login("root", "super-secret-pass")
        response = self.client.patch(
            f"/api/properties/{self.kl.pk}/staff/{self.lee.pk}/",
            data={"reports_to_id": self.omar.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("assigned to this property", response.json()["message"])

    def test_unknown_role_rejected_and_permissions_enforced(self):
        self._login("root", "super-secret-pass")
        bad = self.client.patch(
            f"/api/properties/{self.kl.pk}/staff/{self.lee.pk}/",
            data={"role": "HOTEL_MANAGER"},
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 400)
        self._login("staff.lee", "staff-pass-123")
        forbidden = self.client.patch(
            f"/api/properties/{self.kl.pk}/staff/{self.lee.pk}/",
            data={"role": "MANAGER"},
            content_type="application/json",
        )
        self.assertEqual(forbidden.status_code, 403)
        other = self.client.get(f"/api/properties/{self.penang.pk}/staff/")
        self.assertEqual(other.status_code, 403)

    def test_remove_assignment_keeps_other_staff(self):
        self._login("manager.pat", "manager-pass-123")
        removed = self.client.delete(f"/api/properties/{self.kl.pk}/staff/{self.lee.pk}/")
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(self.kl.staff.filter(pk=self.lee.pk).exists())
        self.assertTrue(self.kl.staff.filter(pk=self.manager.pk).exists())
        self.assertFalse(PropertyStaffAssignment.objects.filter(property=self.kl, user=self.lee).exists())

    def test_roles_endpoint_matches_staff_catalog(self):
        self._login("manager.pat", "manager-pass-123")
        roles = self.client.get("/api/roles/").json()["results"]
        staff = self.client.get(f"/api/properties/{self.kl.pk}/staff/").json()["roles"]
        self.assertEqual([item["id"] for item in roles], [item["id"] for item in staff])
        self.assertEqual([item["name"] for item in roles], [item["name"] for item in staff])

    def test_staff_detail_returns_names_not_ids(self):
        self._login("manager.pat", "manager-pass-123")
        response = self.client.get(f"/api/properties/{self.kl.pk}/staff/{self.lee.pk}/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["display_name"], "Lee Staff")
        self.assertEqual(payload["role"]["name"], "Staff")
        self.assertNotEqual(payload["display_name"], str(self.lee.pk))

    def test_missing_staff_returns_not_found(self):
        self._login("root", "super-secret-pass")
        response = self.client.get(f"/api/properties/{self.kl.pk}/staff/{self.omar.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_removing_manager_clears_reports(self):
        self._login("root", "super-secret-pass")
        self.client.patch(
            f"/api/properties/{self.kl.pk}/staff/{self.lee.pk}/",
            data={"reports_to_id": self.manager.pk},
            content_type="application/json",
        )
        removed = self.client.delete(f"/api/properties/{self.kl.pk}/staff/{self.manager.pk}/")
        self.assertEqual(removed.status_code, 200)
        payload = self.client.get(f"/api/properties/{self.kl.pk}/staff/").json()
        lee = next(item for item in payload["results"] if item["id"] == self.lee.pk)
        self.assertIsNone(lee["reports_to"])
        self.assertEqual(payload["hierarchy"][0]["id"], self.lee.pk)
