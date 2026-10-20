from django.contrib.auth.models import User
from django.test import Client, TestCase

from accounts.catalog import ROLE_STAFF
from accounts.services import create_user, initialize_access_control


class AuthenticationTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.user = create_user(
            username="john",
            password="correct-horse-battery",
            first_name="John",
            last_name="Smith",
            role=ROLE_STAFF,
        )
        self.client = Client(enforce_csrf_checks=True)

    def _csrf_headers(self):
        response = self.client.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        token = response.json()["csrfToken"]
        return {"HTTP_X_CSRFTOKEN": token}

    def test_valid_username_password_logs_in(self):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": "john", "password": "correct-horse-battery"},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["user"]
        self.assertEqual(payload["username"], "john")
        self.assertEqual(payload["role"], "STAFF")
        self.assertNotIn("password", payload)
        self.assertFalse(any("hash" in key for key in payload))

        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "john")

    def test_invalid_credentials_are_generic(self):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": "john", "password": "wrong-password"},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "Unable to sign in with the provided credentials.")

        missing_user = self.client.post(
            "/api/auth/login/",
            data={"username": "nobody", "password": "wrong-password"},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(missing_user.json()["message"], response.json()["message"])

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(
            "/api/auth/login/",
            data={"username": "john", "password": "correct-horse-battery"},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "Unable to sign in with the provided credentials.")

    def test_logout_invalidates_session(self):
        self.client.post(
            "/api/auth/login/",
            data={"username": "john", "password": "correct-horse-battery"},
            content_type="application/json",
            **self._csrf_headers(),
        )
        logout_response = self.client.post("/api/auth/logout/", content_type="application/json", **self._csrf_headers())
        self.assertEqual(logout_response.status_code, 200)

        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 401)

        protected = self.client.get("/api/customers/")
        self.assertEqual(protected.status_code, 401)

    def test_unauthenticated_api_request_is_401(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "Authentication is required.")

    def test_login_does_not_use_email(self):
        self.user.email = "john@example.com"
        self.user.save(update_fields=["email"])
        response = self.client.post(
            "/api/auth/login/",
            data={"username": "john@example.com", "password": "correct-horse-battery"},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 401)


class AccountSettingsTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.user = create_user(
            username="john",
            password="correct-horse-battery",
            first_name="John",
            last_name="Smith",
            email="john@example.com",
            role=ROLE_STAFF,
        )
        self.superuser = User.objects.create_superuser("root", "root@example.com", "super-secret-pass")

    def test_user_can_update_own_profile(self):
        self.client.force_login(self.user)
        response = self.client.patch(
            "/api/auth/me/",
            data={"first_name": "Aiman", "last_name": "Rahman", "email": "aiman@example.com"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["first_name"], "Aiman")
        self.assertEqual(payload["last_name"], "Rahman")
        self.assertEqual(payload["email"], "aiman@example.com")
        self.assertEqual(payload["display_name"], "Aiman Rahman")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Aiman")

    def test_user_cannot_change_role_from_settings(self):
        self.client.force_login(self.user)
        response = self.client.patch(
            "/api/auth/me/",
            data={"role": "MANAGER"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertFalse(self.user.groups.filter(name="Manager").exists())

    def test_user_can_change_password_with_current_password(self):
        self.client.force_login(self.user)
        denied = self.client.post(
            "/api/auth/password/",
            data={"current_password": "wrong-password", "password": "NewPass1234"},
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 400)
        changed = self.client.post(
            "/api/auth/password/",
            data={"current_password": "correct-horse-battery", "password": "NewPass1234"},
            content_type="application/json",
        )
        self.assertEqual(changed.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass1234"))

    def test_staff_can_deactivate_own_account(self):
        self.client.force_login(self.user)
        response = self.client.post("/api/auth/deactivate/", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 401)

    def test_system_admin_cannot_deactivate_from_settings(self):
        self.client.force_login(self.superuser)
        response = self.client.post("/api/auth/deactivate/", content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)
