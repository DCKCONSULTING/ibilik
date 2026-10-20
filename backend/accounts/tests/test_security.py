from django.contrib.auth.models import User
from django.test import Client, TestCase

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF
from accounts.services import create_user, initialize_access_control, set_individual_permissions


class SecurityTests(TestCase):
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
            role=ROLE_MANAGER,
        )
        self.staff = create_user(
            username="staff.lee",
            password="staff-pass-123",
            role=ROLE_STAFF,
        )

    def test_password_is_never_returned(self):
        self.client.force_login(self.superuser)
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, 200)
        raw = response.content.decode("utf-8")
        self.assertNotIn("password", raw)
        self.assertNotIn("super-secret-pass", raw)
        self.assertNotIn("staff-pass-123", raw)
        for item in response.json()["results"]:
            self.assertNotIn("password", item)

        me = self.client.get("/api/auth/me/")
        self.assertNotIn("password", me.json())

    def test_unauthorized_api_access_is_blocked(self):
        response = self.client.get("/api/customers/")
        self.assertEqual(response.status_code, 401)

        self.client.force_login(self.staff)
        forbidden = self.client.get("/api/users/")
        self.assertEqual(forbidden.status_code, 403)

    def test_staff_cannot_escalate_to_superuser(self):
        set_individual_permissions(self.staff, ["users.manage_user", "users.manage_roles"])
        self.client.force_login(self.staff)
        response = self.client.post(
            "/api/users/",
            data={
                "username": "evil",
                "password": "evil-pass-123",
                "role": "SUPERUSER",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="evil").exists())

    def test_superuser_can_create_and_update_users(self):
        self.client.force_login(self.superuser)
        created = self.client.post(
            "/api/users/",
            data={
                "username": "new.staff",
                "password": "new-staff-pass",
                "first_name": "New",
                "last_name": "Staff",
                "role": "STAFF",
            },
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        payload = created.json()
        self.assertEqual(payload["username"], "new.staff")
        self.assertEqual(payload["role"], "STAFF")
        self.assertNotIn("quotes.approve_quote", payload["permissions"])
        self.assertNotIn("password", payload)

        user_id = payload["id"]
        updated = self.client.patch(
            f"/api/users/{user_id}/",
            data={"is_active": False, "role": "MANAGER"},
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(updated.json()["is_active"])
        self.assertEqual(updated.json()["role"], "MANAGER")

        password_reset = self.client.post(
            f"/api/users/{user_id}/password/",
            data={"password": "reset-pass-123"},
            content_type="application/json",
        )
        self.assertEqual(password_reset.status_code, 200)

        self.client.logout()
        login = self.client.post(
            "/api/auth/login/",
            data={"username": "new.staff", "password": "reset-pass-123"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 401)

        user = User.objects.get(pk=user_id)
        user.is_active = True
        user.save(update_fields=["is_active"])
        login = self.client.post(
            "/api/auth/login/",
            data={"username": "new.staff", "password": "reset-pass-123"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)

    def test_csrf_is_required_for_login(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            "/api/auth/login/",
            data={"username": "staff.lee", "password": "staff-pass-123"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_user_password_hash_is_not_plaintext(self):
        user = User.objects.get(username="staff.lee")
        self.assertTrue(user.password)
        self.assertFalse(user.password.startswith("staff-pass-123"))
        self.assertTrue(user.check_password("staff-pass-123"))
