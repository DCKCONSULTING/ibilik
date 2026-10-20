from django.contrib.auth.models import User
from django.test import TestCase

from accounts.catalog import PERMISSION_BY_API, ROLE_MANAGER, ROLE_STAFF
from accounts.models import Property
from accounts.services import create_user, initialize_access_control, set_individual_permissions


class AuthorizationTests(TestCase):
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
        self.staff = create_user(
            username="staff.lee",
            password="staff-pass-123",
            first_name="Lee",
            last_name="Staff",
            role=ROLE_STAFF,
        )
        self.kl = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.kl.staff.add(self.manager, self.staff)

    def _login(self, username: str, password: str):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def test_superuser_can_access_everything(self):
        self._login("root", "super-secret-pass")
        me = self.client.get("/api/auth/me/").json()
        self.assertTrue(me["is_superuser"])
        self.assertEqual(me["role"], "SUPERUSER")
        self.assertEqual(me["permissions"], [])

        endpoints = [
            "/api/dashboard/",
            "/api/customers/",
            "/api/users/",
            "/api/roles/",
            "/api/permissions/",
            "/api/payments/",
            "/api/reports/",
            "/api/settings/",
        ]
        for path in endpoints:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)

        self.assertEqual(self.client.post("/api/quotes/approve/", content_type="application/json").status_code, 200)
        self.assertEqual(self.client.post("/api/bookings/cancel/", content_type="application/json").status_code, 200)

    def test_manager_has_manager_permissions_but_is_not_superuser(self):
        self._login("manager.pat", "manager-pass-123")
        me = self.client.get("/api/auth/me/").json()
        self.assertFalse(me["is_superuser"])
        self.assertEqual(me["role"], "MANAGER")
        self.assertIn("customers.view_customer", me["permissions"])
        self.assertIn("reports.view_report", me["permissions"])
        self.assertIn("users.view_user", me["permissions"])
        self.assertNotIn("users.manage_user", me["permissions"])

        self.assertEqual(self.client.get("/api/customers/").status_code, 200)
        self.assertEqual(self.client.get("/api/reports/").status_code, 200)
        self.assertEqual(self.client.get("/api/users/").status_code, 200)
        self.assertEqual(self.client.post("/api/users/", data={}, content_type="application/json").status_code, 403)
        self.assertEqual(self.client.get("/api/settings/").status_code, 200)

    def test_staff_can_access_staff_permissions(self):
        self._login("staff.lee", "staff-pass-123")
        me = self.client.get("/api/auth/me/").json()
        self.assertEqual(me["role"], "STAFF")
        self.assertIn("customers.view_customer", me["permissions"])
        self.assertIn("bookings.view_booking", me["permissions"])
        self.assertNotIn("users.manage_user", me["permissions"])
        self.assertNotIn("reports.view_report", me["permissions"])

        self.assertEqual(self.client.get("/api/customers/").status_code, 200)
        self.assertEqual(self.client.get("/api/bookings/").status_code, 200)
        self.assertEqual(self.client.get("/api/inbox/").status_code, 200)

    def test_staff_cannot_access_management_apis(self):
        self._login("staff.lee", "staff-pass-123")
        self.assertEqual(self.client.get("/api/users/").status_code, 403)
        self.assertEqual(self.client.get("/api/roles/").status_code, 403)
        self.assertEqual(self.client.get("/api/settings/").status_code, 403)
        self.assertEqual(self.client.get("/api/reports/").status_code, 403)
        self.assertEqual(self.client.post("/api/quotes/approve/", content_type="application/json").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/users/",
                data={
                    "username": "new.user",
                    "password": "new-user-pass",
                    "role": "STAFF",
                },
                content_type="application/json",
            ).status_code,
            403,
        )

    def test_user_level_permissions_are_not_effective(self):
        set_individual_permissions(self.staff, ["quotes.approve_quote"])
        self._login("staff.lee", "staff-pass-123")
        me = self.client.get("/api/auth/me/").json()
        self.assertNotIn("quotes.approve_quote", me["permissions"])
        self.assertEqual(self.client.post("/api/quotes/approve/", content_type="application/json").status_code, 403)
        self.assertEqual(self.client.get("/api/users/").status_code, 403)

    def test_user_without_permission_receives_403(self):
        self._login("staff.lee", "staff-pass-123")
        listing = self.client.get("/api/payments/")
        self.assertEqual(listing.status_code, 200)
        response = self.client.post("/api/payments/1/approve/", content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["message"], "You do not have permission to perform this action.")

    def test_authorization_is_not_based_on_username(self):
        admin_named_staff = create_user(
            username="admin",
            password="staff-pass-123",
            role=ROLE_STAFF,
        )
        self.assertFalse(admin_named_staff.is_superuser)
        self._login("admin", "staff-pass-123")
        self.assertEqual(self.client.get("/api/users/").status_code, 403)
        self.assertEqual(self.client.get("/api/settings/").status_code, 403)

    def test_manager_can_view_users_but_not_create_without_manage_permission(self):
        self._login("manager.pat", "manager-pass-123")
        listing = self.client.get("/api/users/")
        self.assertEqual(listing.status_code, 200)
        self.assertTrue(any(item["username"] == "staff.lee" for item in listing.json()["results"]))
        create = self.client.post(
            "/api/users/",
            data={"username": "extra", "password": "extra-pass-123", "role": "STAFF"},
            content_type="application/json",
        )
        self.assertEqual(create.status_code, 403)
