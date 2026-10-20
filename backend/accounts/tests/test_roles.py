from django.contrib.auth.models import User
from django.test import TestCase

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF, ROLE_SUPERUSER, ROLE_TOP_MANAGER
from accounts.models import Property, Role
from accounts.services import create_user, initialize_access_control


class RoleHierarchyTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.superuser = User.objects.create_superuser(
            username="root",
            email="root@example.com",
            password="super-secret-pass",
        )
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
            first_name="Lee",
            last_name="Staff",
            role=ROLE_STAFF,
        )
        self.kl = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.jb = Property.objects.create(name="Hotel JB", region="Johor", city="Johor Bahru", rate="120.00")
        self.kl.staff.add(self.manager, self.staff)

    def _login(self, username, password):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def test_roles_display_system_admin_and_levels(self):
        self._login("root", "super-secret-pass")
        payload = self.client.get("/api/roles/").json()
        names = {item["code"]: item for item in payload["results"]}
        self.assertEqual(names[ROLE_SUPERUSER]["name"], "System Admin")
        self.assertTrue(names[ROLE_SUPERUSER]["protected"])
        self.assertEqual(names[ROLE_TOP_MANAGER]["name"], "Top Manager")
        self.assertEqual(names[ROLE_TOP_MANAGER]["level"], 1)
        self.assertEqual(names[ROLE_MANAGER]["level"], 2)
        self.assertEqual(names[ROLE_STAFF]["level"], 3)
        self.assertTrue(Role.objects.filter(code=ROLE_MANAGER).exists())
        self.assertEqual([item["id"] for item in payload["sections"]], [
            "workspace", "sales", "property", "reporting", "staff", "management", "settings"
        ])

    def test_superuser_me_uses_system_admin_label(self):
        self._login("root", "super-secret-pass")
        me = self.client.get("/api/auth/me/").json()
        self.assertEqual(me["role"], ROLE_SUPERUSER)
        self.assertEqual(me["role_name"], "System Admin")
        self.assertTrue(me["is_superuser"])

    def test_top_manager_sees_all_properties_and_cannot_grant_superuser(self):
        self._login("top.mina", "top-pass-12345")
        properties = self.client.get("/api/properties/").json()["results"]
        self.assertEqual({item["name"] for item in properties}, {"Hotel KL", "Hotel JB"})
        me = self.client.get("/api/auth/me/").json()
        self.assertEqual(me["role"], ROLE_TOP_MANAGER)
        self.assertFalse(me["is_superuser"])
        self.assertIn("users.manage_user", me["permissions"])
        self.assertNotIn("users.manage_roles", me["permissions"])
        denied = self.client.patch(
            f"/api/users/{self.staff.pk}/",
            data={"role": ROLE_SUPERUSER},
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_superuser)

    def test_top_manager_cannot_manage_system_admin(self):
        self._login("top.mina", "top-pass-12345")
        response = self.client.patch(
            f"/api/users/{self.superuser.pk}/",
            data={"first_name": "Nope"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_is_property_scoped(self):
        self._login("manager.pat", "manager-pass-123")
        listing = self.client.get("/api/properties/").json()["results"]
        self.assertEqual([item["name"] for item in listing], ["Hotel KL"])
        forbidden = self.client.get(f"/api/properties/{self.jb.pk}/")
        self.assertEqual(forbidden.status_code, 403)

    def test_manager_cannot_assign_higher_roles(self):
        self._login("manager.pat", "manager-pass-123")
        for role in (ROLE_SUPERUSER, ROLE_TOP_MANAGER, ROLE_MANAGER):
            response = self.client.patch(
                f"/api/users/{self.staff.pk}/",
                data={"role": role},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 403, role)

    def test_staff_cannot_manage_roles(self):
        self._login("staff.lee", "staff-pass-123")
        self.assertEqual(self.client.get("/api/roles/").status_code, 403)
        self.assertEqual(
            self.client.patch(
                f"/api/roles/{ROLE_STAFF}/",
                data={"permissions": ["dashboard.view_dashboard"]},
                content_type="application/json",
            ).status_code,
            403,
        )

    def test_system_admin_role_cannot_be_edited(self):
        self._login("root", "super-secret-pass")
        response = self.client.patch(
            f"/api/roles/{ROLE_SUPERUSER}/",
            data={"name": "Broken"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Role.objects.get(code=ROLE_SUPERUSER).name, "System Admin")

    def test_role_permission_updates_persist(self):
        self._login("root", "super-secret-pass")
        response = self.client.patch(
            f"/api/roles/{ROLE_STAFF}/",
            data={"permissions": ["dashboard.view_dashboard", "customers.view_customer"], "description": "Limited staff"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["description"], "Limited staff")
        self.assertEqual(set(payload["permissions"]), {"dashboard.view_dashboard", "customers.view_customer"})
        again = self.client.get(f"/api/roles/{ROLE_STAFF}/").json()
        self.assertEqual(set(again["permissions"]), {"dashboard.view_dashboard", "customers.view_customer"})

    def test_builtin_roles_are_seeded_once(self):
        initialize_access_control()
        initialize_access_control()
        self.assertEqual(Role.objects.filter(code=ROLE_TOP_MANAGER).count(), 1)
        self.assertEqual(Role.objects.filter(code=ROLE_MANAGER).count(), 1)
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)
