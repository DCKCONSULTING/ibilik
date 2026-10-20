from django.contrib.auth.models import User
from django.test import TestCase

from accounts.authorization import get_effective_permissions, user_has_permission
from accounts.catalog import ROLE_MANAGER, ROLE_STAFF, ROLE_SUPERUSER, ROLE_TOP_MANAGER, STAFF_PERMISSIONS
from accounts.models import Property, PropertyStaffAssignment, Role
from accounts.roles import group_permission_codenames
from accounts.services import create_user, initialize_access_control, set_individual_permissions


class RoleInheritanceTests(TestCase):
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
            email="lee@example.com",
            role=ROLE_STAFF,
        )
        self.kl = Property.objects.create(name="Kuala Lumpur City Centre", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.jb = Property.objects.create(name="Hotel JB", region="Johor", city="Johor Bahru", rate="120.00")
        self.kl.staff.add(self.manager, self.staff)
        PropertyStaffAssignment.objects.create(
            property=self.kl,
            user=self.staff,
            reports_to=self.manager,
            role=ROLE_STAFF,
        )

    def _login(self, username, password):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def test_create_user_with_role_inherits_role_permissions(self):
        self._login("root", "super-secret-pass")
        created = self.client.post(
            "/api/users/",
            data={
                "username": "staff.kl",
                "password": "staff-pass-123",
                "first_name": "Aiman",
                "last_name": "Rahman",
                "email": "manager@example.com",
                "role": ROLE_STAFF,
                "property_ids": [self.kl.pk],
                "is_active": True,
            },
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        payload = created.json()
        self.assertEqual(payload["role"], ROLE_STAFF)
        self.assertEqual(payload["role_name"], "Staff")
        self.assertEqual(payload["permissions_source"], "role")
        self.assertEqual(payload["individual_permissions"], [])
        self.assertEqual(set(payload["permissions"]), set(payload["effective_permissions"]))
        self.assertEqual(set(payload["permissions"]), set(STAFF_PERMISSIONS))
        self.assertEqual(payload["assigned_properties"][0]["name"], "Kuala Lumpur City Centre")
        user = User.objects.get(username="staff.kl")
        self.assertEqual(get_effective_permissions(user), sorted(STAFF_PERMISSIONS))
        self.assertEqual(user.groups.count(), 1)

    def test_edit_user_role_replaces_effective_permissions(self):
        self._login("root", "super-secret-pass")
        response = self.client.patch(
            f"/api/users/{self.staff.pk}/",
            data={"role": ROLE_MANAGER},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["role"], ROLE_MANAGER)
        self.assertEqual(payload["role_name"], "Manager")
        self.assertIn("reports.view_report", payload["permissions"])
        self.assertIn("match.assign_request", payload["permissions"])
        self.assertNotIn("users.manage_user", payload["permissions"])
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.groups.count(), 1)
        self.assertTrue(user_has_permission(self.staff, "reports.view_report"))

    def test_user_level_permission_assignment_is_rejected(self):
        self._login("root", "super-secret-pass")
        created = self.client.post(
            "/api/users/",
            data={
                "username": "forged.staff",
                "password": "staff-pass-123",
                "role": ROLE_STAFF,
                "permissions": ["users.manage_roles", "quotes.approve_quote"],
            },
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 400)
        self.assertEqual(created.json()["code"], "user_permissions_not_allowed")
        self.assertFalse(User.objects.filter(username="forged.staff").exists())

        patched = self.client.patch(
            f"/api/users/{self.staff.pk}/",
            data={"individual_permissions": ["quotes.approve_quote"]},
            content_type="application/json",
        )
        self.assertEqual(patched.status_code, 400)
        self.assertEqual(patched.json()["code"], "user_permissions_not_allowed")
        self.assertFalse(user_has_permission(self.staff, "quotes.approve_quote"))

    def test_legacy_user_permissions_do_not_grant_access(self):
        set_individual_permissions(self.staff, ["quotes.approve_quote", "users.manage_user"])
        self.assertFalse(user_has_permission(self.staff, "quotes.approve_quote"))
        self.assertNotIn("quotes.approve_quote", get_effective_permissions(self.staff))
        self._login("staff.lee", "staff-pass-123")
        self.assertEqual(self.client.post("/api/quotes/approve/", content_type="application/json").status_code, 403)
        self.assertEqual(self.client.get("/api/users/").status_code, 403)

    def test_changing_role_clears_legacy_user_permissions(self):
        set_individual_permissions(self.staff, ["users.manage_roles"])
        self.assertTrue(self.staff.user_permissions.exists())
        self._login("root", "super-secret-pass")
        response = self.client.patch(
            f"/api/users/{self.staff.pk}/",
            data={"role": ROLE_MANAGER},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.user_permissions.exists())
        self.assertNotIn("users.manage_roles", get_effective_permissions(self.staff))
        self.assertIn("reports.view_report", get_effective_permissions(self.staff))

    def test_role_permission_updates_change_user_access(self):
        self._login("root", "super-secret-pass")
        self.assertFalse(user_has_permission(self.staff, "reports.view_report"))
        updated = self.client.patch(
            f"/api/roles/{ROLE_STAFF}/",
            data={"permissions": list(STAFF_PERMISSIONS) + ["reports.view_report"]},
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertIn("reports.view_report", get_effective_permissions(self.staff))
        self.client.logout()
        self._login("staff.lee", "staff-pass-123")
        me = self.client.get("/api/auth/me/").json()
        self.assertIn("reports.view_report", me["permissions"])
        self.assertEqual(self.client.get("/api/reports/").status_code, 200)

    def test_system_admin_retains_full_authority(self):
        self._login("root", "super-secret-pass")
        me = self.client.get("/api/auth/me/").json()
        self.assertEqual(me["role_name"], "System Admin")
        self.assertTrue(me["is_superuser"])
        self.assertEqual(me["permissions"], [])
        self.assertEqual(self.client.get("/api/roles/").status_code, 200)
        self.assertEqual(self.client.get("/api/permissions/").status_code, 200)
        self.assertEqual(self.client.get("/api/users/").status_code, 200)

    def test_staff_cannot_assign_manager_role(self):
        self._login("staff.lee", "staff-pass-123")
        response = self.client.patch(
            f"/api/users/{self.staff.pk}/",
            data={"role": ROLE_MANAGER},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_cannot_assign_top_manager(self):
        self._login("manager.pat", "manager-pass-123")
        response = self.client.patch(
            f"/api/users/{self.staff.pk}/",
            data={"role": ROLE_TOP_MANAGER},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.groups.filter(name="Top Manager").exists())

    def test_users_cannot_grant_themselves_permissions(self):
        self._login("staff.lee", "staff-pass-123")
        response = self.client.patch(
            f"/api/users/{self.staff.pk}/",
            data={"permissions": ["users.manage_roles"]},
            content_type="application/json",
        )
        self.assertIn(response.status_code, {400, 403})
        self.assertFalse(user_has_permission(self.staff, "users.manage_roles"))

    def test_property_scope_assignment_is_enforced(self):
        self._login("manager.pat", "manager-pass-123")
        response = self.client.patch(
            f"/api/users/{self.staff.pk}/",
            data={"property_ids": [self.jb.pk], "property_access": "ASSIGNED"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.staff.assigned_properties.filter(pk=self.jb.pk).exists())

    def test_reporting_hierarchy_is_serialized(self):
        self._login("root", "super-secret-pass")
        payload = self.client.get(f"/api/users/{self.staff.pk}/").json()
        self.assertEqual(payload["reporting_managers"][0]["name"], "Pat Manager")

    def test_unauthorized_role_id_is_blocked(self):
        self._login("top.mina", "top-pass-12345")
        response = self.client.patch(
            f"/api/users/{self.staff.pk}/",
            data={"role": ROLE_SUPERUSER},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        unknown = self.client.patch(
            f"/api/users/{self.staff.pk}/",
            data={"role": "NOT_A_ROLE"},
            content_type="application/json",
        )
        self.assertEqual(unknown.status_code, 400)

    def test_assigning_role_does_not_duplicate_groups(self):
        self._login("root", "super-secret-pass")
        self.client.patch(f"/api/users/{self.staff.pk}/", data={"role": ROLE_MANAGER}, content_type="application/json")
        self.client.patch(f"/api/users/{self.staff.pk}/", data={"role": ROLE_STAFF}, content_type="application/json")
        self.client.patch(f"/api/users/{self.staff.pk}/", data={"role": ROLE_STAFF}, content_type="application/json")
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.groups.count(), 1)
        self.assertEqual(Role.objects.filter(code=ROLE_STAFF).count(), 1)

    def test_existing_users_keep_role_access_after_reinitialize(self):
        initialize_access_control()
        initialize_access_control()
        self.assertIn("customers.view_customer", get_effective_permissions(self.staff))
        self.assertIn("users.view_user", get_effective_permissions(self.manager))
        self.assertTrue(self.superuser.is_superuser)
        staff_role = Role.objects.get(code=ROLE_STAFF)
        self.assertEqual(set(group_permission_codenames(staff_role.group)), set(STAFF_PERMISSIONS))

    def test_managed_user_list_uses_property_names(self):
        self._login("root", "super-secret-pass")
        listing = self.client.get("/api/users/").json()["results"]
        staff = next(item for item in listing if item["username"] == "staff.lee")
        self.assertEqual([item["name"] for item in staff["assigned_properties"]], ["Kuala Lumpur City Centre"])
        self.assertNotIn(str(self.kl.pk), staff["assigned_properties"][0]["name"])
        self.assertEqual(staff["permissions_source"], "role")
