from django.contrib.auth.models import User
from django.test import TestCase

from accounts.authorization import can_access_property, has_global_property_access
from accounts.catalog import ROLE_MANAGER, ROLE_STAFF
from accounts.models import Property, UserPropertyAccess
from accounts.services import create_user, initialize_access_control, set_individual_permissions


class PropertyAccessTests(TestCase):
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
        self.global_staff = create_user(
            username="staff.global",
            password="staff-pass-123",
            first_name="Sara",
            last_name="Global",
            role=ROLE_STAFF,
            property_access=UserPropertyAccess.Mode.GLOBAL,
            actor=self.superuser,
        )
        self.assigned_staff = create_user(
            username="staff.lee",
            password="staff-pass-123",
            first_name="Lee",
            last_name="Staff",
            role=ROLE_STAFF,
        )
        self.other_staff = create_user(
            username="staff.other",
            password="staff-pass-123",
            first_name="Omar",
            last_name="Other",
            role=ROLE_STAFF,
        )
        self.cairo = Property.objects.create(
            name="Hotel KL",
            region="Kuala Lumpur",
            city="Kuala Lumpur",
            rate="150.00",
        )
        self.alex = Property.objects.create(
            name="Hotel Penang",
            region="Penang",
            city="George Town",
            rate="120.00",
        )
        self.cairo.staff.add(self.assigned_staff, self.manager)

    def _login(self, username: str, password: str):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def test_authorized_user_can_create_property(self):
        self._login("staff.lee", "staff-pass-123")
        response = self.client.post(
            "/api/properties/",
            data={
                "name": "Example Hotel",
                "region": "Kuala Lumpur",
                "city": "Kuala Lumpur",
                "rate": "150.00",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["name"], "Example Hotel")
        self.assertEqual(payload["region"], "Kuala Lumpur")
        self.assertEqual(payload["city"], "Kuala Lumpur")
        self.assertEqual(payload["rate"], "150.00")
        self.assertTrue(Property.objects.filter(pk=payload["id"]).exists())

    def test_unauthorized_user_cannot_create_property(self):
        viewer = create_user(
            username="viewer.only",
            password="staff-pass-123",
            role=ROLE_STAFF,
        )
        viewer.groups.clear()
        self._login("viewer.only", "staff-pass-123")
        response = self.client.post(
            "/api/properties/",
            data={
                "name": "Blocked Hotel",
                "region": "Kuala Lumpur",
                "city": "Kuala Lumpur",
                "rate": "10.00",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Property.objects.filter(name="Blocked Hotel").exists())

    def test_property_validation(self):
        self._login("root", "super-secret-pass")
        missing = self.client.post(
            "/api/properties/",
            data={"name": "", "region": "Kuala Lumpur", "city": "Kuala Lumpur", "rate": "10.00"},
            content_type="application/json",
        )
        self.assertEqual(missing.status_code, 400)

        invalid_rate = self.client.post(
            "/api/properties/",
            data={"name": "Bad Rate", "region": "Kuala Lumpur", "city": "Kuala Lumpur", "rate": "not-a-number"},
            content_type="application/json",
        )
        self.assertEqual(invalid_rate.status_code, 400)

        nan_rate = self.client.post(
            "/api/properties/",
            data={"name": "NaN Rate", "region": "Kuala Lumpur", "city": "Kuala Lumpur", "rate": "NaN"},
            content_type="application/json",
        )
        self.assertEqual(nan_rate.status_code, 400)

    def test_superuser_sees_all_properties(self):
        self._login("root", "super-secret-pass")
        response = self.client.get("/api/properties/")
        self.assertEqual(response.status_code, 200)
        names = {item["name"] for item in response.json()["results"]}
        self.assertEqual(names, {"Hotel KL", "Hotel Penang"})

    def test_global_user_sees_all_properties(self):
        self._login("staff.global", "staff-pass-123")
        me = self.client.get("/api/auth/me/").json()
        self.assertEqual(me["property_access"], "GLOBAL")
        self.assertFalse(me["is_superuser"])
        response = self.client.get("/api/properties/")
        names = {item["name"] for item in response.json()["results"]}
        self.assertEqual(names, {"Hotel KL", "Hotel Penang"})

    def test_assigned_user_sees_only_assigned_properties(self):
        self._login("staff.lee", "staff-pass-123")
        me = self.client.get("/api/auth/me/").json()
        self.assertEqual(me["property_access"], "ASSIGNED")
        self.assertEqual(me["property_ids"], [self.cairo.pk])
        response = self.client.get("/api/properties/")
        results = response.json()["results"]
        self.assertEqual([item["name"] for item in results], ["Hotel KL"])

    def test_assigned_user_does_not_see_unrelated_properties(self):
        self._login("staff.other", "staff-pass-123")
        response = self.client.get("/api/properties/")
        self.assertEqual(response.json()["results"], [])

    def test_authorized_detail_access(self):
        self._login("staff.lee", "staff-pass-123")
        response = self.client.get(f"/api/properties/{self.cairo.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Hotel KL")
        self.assertIn("staff", response.json())
        summary = response.json()["summary"]
        self.assertEqual(summary["location_count"], 0)
        self.assertEqual(summary["open_cases_count"], 0)
        self.assertEqual(summary["pending_quotes_count"], 0)
        listing = self.client.get("/api/properties/").json()["results"][0]
        self.assertNotIn("summary", listing)

    def test_unauthorized_detail_is_forbidden(self):
        self._login("staff.lee", "staff-pass-123")
        response = self.client.get(f"/api/properties/{self.alex.pk}/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "property_forbidden")
        self.assertNotIn("name", response.json())

    def test_manager_can_assign_staff(self):
        self._login("manager.pat", "manager-pass-123")
        response = self.client.post(
            f"/api/properties/{self.cairo.pk}/staff/",
            data={"user_id": self.other_staff.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.cairo.staff.filter(pk=self.other_staff.pk).exists())

    def test_unauthorized_staff_cannot_assign(self):
        self._login("staff.lee", "staff-pass-123")
        response = self.client.post(
            f"/api/properties/{self.cairo.pk}/staff/",
            data={"user_id": self.other_staff.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.cairo.staff.filter(pk=self.other_staff.pk).exists())

        self_assign = self.client.post(
            f"/api/properties/{self.alex.pk}/staff/",
            data={"user_id": self.assigned_staff.pk},
            content_type="application/json",
        )
        self.assertEqual(self_assign.status_code, 403)
        self.assertFalse(self.alex.staff.filter(pk=self.assigned_staff.pk).exists())

    def test_user_cannot_escalate_themselves_to_global(self):
        set_individual_permissions(self.assigned_staff, ["users.manage_user"])
        self._login("staff.lee", "staff-pass-123")
        response = self.client.patch(
            f"/api/users/{self.assigned_staff.pk}/",
            data={"property_access": "GLOBAL"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assigned_staff.refresh_from_db()
        self.assertFalse(has_global_property_access(self.assigned_staff))

    def test_global_user_sees_newly_created_property(self):
        self._login("staff.global", "staff-pass-123")
        created = self.client.post(
            "/api/properties/",
            data={
                "name": "Hotel Langkawi",
                "region": "Kedah",
                "city": "Langkawi",
                "rate": "180.00",
            },
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        listing = self.client.get("/api/properties/")
        names = {item["name"] for item in listing.json()["results"]}
        self.assertIn("Hotel Langkawi", names)
        self.assertTrue(can_access_property(self.global_staff, Property.objects.get(name="Hotel Langkawi")))

    def test_superuser_me_reports_global_access(self):
        self._login("root", "super-secret-pass")
        me = self.client.get("/api/auth/me/").json()
        self.assertTrue(me["is_superuser"])
        self.assertEqual(me["property_access"], "GLOBAL")

    def test_global_access_is_independent_of_role(self):
        self.assertFalse(self.manager.is_superuser)
        self.assertFalse(has_global_property_access(self.manager))
        self.assertTrue(has_global_property_access(self.global_staff))
        self.assertEqual(self.global_staff.groups.first().name, "Staff")

    def test_staff_without_user_management_cannot_change_another_users_access(self):
        self._login("staff.lee", "staff-pass-123")
        response = self.client.patch(
            f"/api/users/{self.other_staff.pk}/",
            data={"property_access": "GLOBAL"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_set_user_property_access(self):
        self._login("root", "super-secret-pass")
        response = self.client.patch(
            f"/api/users/{self.other_staff.pk}/",
            data={"property_access": "ASSIGNED", "property_ids": [self.alex.pk]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["property_access"], "ASSIGNED")
        self.assertEqual(payload["property_ids"], [self.alex.pk])
        self.assertEqual(payload["assigned_properties"][0]["name"], "Hotel Penang")

    def test_assigned_user_cannot_update_inaccessible_property(self):
        self._login("staff.lee", "staff-pass-123")
        response = self.client.patch(
            f"/api/properties/{self.alex.pk}/",
            data={"name": "Hacked"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.alex.refresh_from_db()
        self.assertEqual(self.alex.name, "Hotel Penang")

    def test_manager_can_update_accessible_property(self):
        self._login("manager.pat", "manager-pass-123")
        response = self.client.patch(
            f"/api/properties/{self.cairo.pk}/",
            data={"rate": "175.50"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rate"], "175.50")

    def test_global_access_does_not_grant_user_management(self):
        self._login("staff.global", "staff-pass-123")
        self.assertEqual(self.client.get("/api/users/").status_code, 403)
        self.assertEqual(
            self.client.patch(
                f"/api/users/{self.assigned_staff.pk}/",
                data={"property_access": "GLOBAL"},
                content_type="application/json",
            ).status_code,
            403,
        )

    def test_create_and_retrieve_malaysian_hotel_fields(self):
        self._login("root", "super-secret-pass")
        created = self.client.post(
            "/api/properties/",
            data={
                "name": "iBilik Test Hotel",
                "code": "TST",
                "property_type": "boutique_hotel",
                "description": "Fictional demo hotel for tests.",
                "country": "Malaysia",
                "region": "Kuala Lumpur",
                "city": "Kuala Lumpur",
                "address_line1": "Jalan Sultan Ismail, Bukit Bintang",
                "address_line2": "Kuala Lumpur, Malaysia",
                "postal_code": "50250",
                "phone": "+603-0000-9999",
                "email": "reservations.test@demo.ibilik.local",
                "website": "https://demo.ibilik.local/test",
                "currency": "MYR",
                "rate": "220.00",
                "status": "active",
                "check_in_time": "15:00",
                "check_out_time": "12:00",
                "timezone": "Asia/Kuala_Lumpur",
                "star_rating": 4,
            },
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        payload = created.json()
        self.assertEqual(payload["country"], "Malaysia")
        self.assertEqual(payload["address_line1"], "Jalan Sultan Ismail, Bukit Bintang")
        self.assertEqual(payload["property_type"], "boutique_hotel")
        self.assertEqual(payload["property_type_label"], "Boutique Hotel")
        self.assertEqual(payload["currency"], "MYR")
        self.assertEqual(payload["rate"], "220.00")
        self.assertEqual(payload["base_rate"], "220.00")
        self.assertEqual(payload["timezone"], "Asia/Kuala_Lumpur")
        self.assertEqual(payload["status"], "active")

        detail = self.client.get(f"/api/properties/{payload['id']}/")
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["city"], "Kuala Lumpur")
        self.assertEqual(body["check_in_time"], "15:00")
        self.assertEqual(body["email"], "reservations.test@demo.ibilik.local")

        listing = self.client.get("/api/properties/")
        names = {item["name"] for item in listing.json()["results"]}
        self.assertIn("iBilik Test Hotel", names)
        listed = next(item for item in listing.json()["results"] if item["id"] == payload["id"])
        self.assertEqual(listed["currency"], "MYR")
        self.assertEqual(listed["property_type"], "boutique_hotel")

    def test_property_defaults_to_malaysian_commercial_settings(self):
        self._login("root", "super-secret-pass")
        created = self.client.post(
            "/api/properties/",
            data={
                "name": "Default Hotel",
                "region": "Johor",
                "city": "Johor Bahru",
                "rate": "160.00",
            },
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        payload = created.json()
        self.assertEqual(payload["country"], "Malaysia")
        self.assertEqual(payload["currency"], "MYR")
        self.assertEqual(payload["timezone"], "Asia/Kuala_Lumpur")
        self.assertEqual(payload["property_type"], "hotel")
        self.assertEqual(payload["status"], "active")

    def test_invalid_property_type_and_timezone_are_rejected(self):
        self._login("root", "super-secret-pass")
        bad_type = self.client.post(
            "/api/properties/",
            data={
                "name": "Bad Type Hotel",
                "region": "Penang",
                "city": "George Town",
                "rate": "100.00",
                "property_type": "spaceship",
            },
            content_type="application/json",
        )
        self.assertEqual(bad_type.status_code, 400)

        bad_zone = self.client.post(
            "/api/properties/",
            data={
                "name": "Bad Zone Hotel",
                "region": "Penang",
                "city": "George Town",
                "rate": "100.00",
                "timezone": "Not/AZone",
            },
            content_type="application/json",
        )
        self.assertEqual(bad_zone.status_code, 400)
