from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF
from accounts.models import Property
from accounts.services import create_user, initialize_access_control
from cases.models import Case
from crm.models import Customer
from locations.models import Location, LocationStatus, LocationType, MaintenanceIssue
from pipeline.models import PipelineStage


class LocationOperationsTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.superuser = User.objects.create_superuser(
            username="root",
            email="root@example.com",
            password="super-secret-pass",
        )
        self.manager = create_user(
            username="manager.kl",
            password="staff-pass-123",
            first_name="Mina",
            last_name="Manager",
            role=ROLE_MANAGER,
        )
        self.staff = create_user(
            username="staff.kl",
            password="staff-pass-123",
            first_name="Lee",
            last_name="Staff",
            role=ROLE_STAFF,
        )
        self.other = create_user(
            username="staff.other",
            password="staff-pass-123",
            first_name="Omar",
            last_name="Other",
            role=ROLE_STAFF,
        )
        self.hotel = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.other_hotel = Property.objects.create(name="Hotel Penang", region="Penang", city="George Town", rate="120.00")
        self.hotel.staff.add(self.manager, self.staff)
        self.customer = Customer.objects.create(name="John Smith", email="john@example.com", property=self.hotel)
        self.guest = Customer.objects.create(name="Ahmed Ali", email="ahmed@example.com", property=self.hotel)
        self.now = timezone.now()

    def _login(self, username="root", password="super-secret-pass"):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def _room(self, name="Room 101", code="101", status=LocationStatus.AVAILABLE, **kwargs):
        return Location.objects.create(
            property=self.hotel,
            name=name,
            code=code,
            location_type=LocationType.ROOM,
            status=status,
            is_bookable=True,
            active=True,
            **kwargs,
        )

    def _reservation(self, location, *, customer=None, hours_from=24, nights=2, actual_in=False, number="CASE-2001"):
        check_in = self.now + timedelta(hours=hours_from)
        check_out = check_in + timedelta(days=nights)
        return Case.objects.create(
            sequence=int(number.split("-")[-1]),
            case_number=number,
            customer=customer or self.customer,
            property=self.hotel,
            location=location,
            title="Stay",
            stage=PipelineStage.WON,
            check_in=check_in,
            check_out=check_out,
            actual_check_in=check_in if actual_in else None,
        )

    def test_free_available_is_bookable_without_guest(self):
        room = self._room()
        self._login()
        payload = self.client.get(f"/api/locations/{room.pk}/").json()
        self.assertEqual(payload["occupancy"], "free")
        self.assertEqual(payload["status"], "available")
        self.assertTrue(payload["is_bookable_now"])
        self.assertIsNone(payload["current_booking"])
        self.assertIsNone(payload["upcoming_booking"])

    def test_reserved_available_shows_future_guest_and_blocks_conflict(self):
        room = self._room(name="Room 102", code="102")
        self._reservation(room, hours_from=48)
        self._login()
        payload = self.client.get(f"/api/locations/{room.pk}/").json()
        self.assertEqual(payload["occupancy"], "reserved")
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["upcoming_booking"]["customer"]["name"], "John Smith")
        self.assertTrue(payload["is_bookable_now"])
        reserved = self.client.get("/api/availability/", {"occupancy": "reserved", "property": self.hotel.pk}).json()
        self.assertEqual(reserved["count"], 1)
        bookable = self.client.get(
            "/api/availability/",
            {"available_for_booking": "true", "property": self.hotel.pk},
        ).json()
        self.assertNotIn(room.pk, {item["id"] for item in bookable["results"]})

    def test_in_house_available_shows_guest_and_checkout(self):
        room = self._room(name="Room 103", code="103")
        stay = self._reservation(room, customer=self.guest, hours_from=-12, actual_in=True, number="CASE-2002")
        self._login()
        payload = self.client.get(f"/api/locations/{room.pk}/").json()
        self.assertEqual(payload["occupancy"], "in_house")
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["current_booking"]["customer"]["name"], "Ahmed Ali")
        self.assertIn("check_out", payload["allowed_actions"])
        self.assertNotIn("check_in", payload["allowed_actions"])
        blocked = self.client.post(
            f"/api/locations/{room.pk}/check-in/",
            data={"case_id": stay.pk},
            content_type="application/json",
        )
        self.assertEqual(blocked.status_code, 409)

    def test_free_dirty_is_not_bookable_and_can_start_cleaning(self):
        room = self._room(name="Room 104", code="104", status=LocationStatus.DIRTY)
        self._login()
        payload = self.client.get(f"/api/locations/{room.pk}/").json()
        self.assertEqual(payload["occupancy"], "free")
        self.assertEqual(payload["status"], "dirty")
        self.assertFalse(payload["is_bookable_now"])
        self.assertIn("start_cleaning", payload["allowed_actions"])
        free = self.client.get("/api/availability/", {"occupancy": "free", "property": self.hotel.pk}).json()
        self.assertIn(room.pk, {item["id"] for item in free["results"]})

    def test_free_maintenance_is_not_bookable(self):
        room = self._room(name="Room 105", code="105", status=LocationStatus.MAINTENANCE)
        self._login()
        payload = self.client.get(f"/api/locations/{room.pk}/").json()
        self.assertEqual(payload["occupancy"], "free")
        self.assertEqual(payload["status"], "maintenance")
        self.assertFalse(payload["is_bookable_now"])
        self.assertIsNone(payload["current_booking"])

    def test_check_in_makes_occupancy_in_house(self):
        room = self._room()
        reservation = self._reservation(room, hours_from=2, number="CASE-2003")
        self._login()
        response = self.client.post(
            f"/api/locations/{room.pk}/check-in/",
            data={"case_id": reservation.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["occupancy"], "in_house")
        self.assertEqual(payload["current_booking"]["id"], reservation.pk)
        reservation.refresh_from_db()
        self.assertIsNotNone(reservation.actual_check_in)

    def test_check_out_closes_stay_and_marks_dirty(self):
        room = self._room(name="Room 103", code="103")
        stay = self._reservation(room, customer=self.guest, hours_from=-10, actual_in=True, number="CASE-2004")
        self._login()
        response = self.client.post(
            f"/api/locations/{room.pk}/check-out/",
            data={"case_id": stay.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["occupancy"], "free")
        self.assertEqual(payload["status"], "dirty")
        self.assertIsNone(payload["current_booking"])
        self.assertFalse(payload["is_bookable_now"])
        stay.refresh_from_db()
        self.assertIsNotNone(stay.actual_check_out)

    def test_cleaning_complete_keeps_occupancy(self):
        room = self._room(name="Room 103", code="103", status=LocationStatus.DIRTY)
        self._reservation(room, hours_from=36, number="CASE-2005")
        self._login()
        started = self.client.post(
            f"/api/locations/{room.pk}/cleaning/start/",
            data={"notes": "Housekeeping started"},
            content_type="application/json",
        )
        self.assertEqual(started.status_code, 200, started.content)
        self.assertEqual(started.json()["status"], "cleaning")
        self.assertEqual(started.json()["occupancy"], "reserved")
        completed = self.client.post(
            f"/api/locations/{room.pk}/cleaning/complete/",
            data={"notes": "Ready"},
            content_type="application/json",
        )
        self.assertEqual(completed.status_code, 200, completed.content)
        self.assertEqual(completed.json()["status"], "available")
        self.assertEqual(completed.json()["occupancy"], "reserved")
        self.assertEqual(completed.json()["upcoming_booking"]["customer"]["name"], "John Smith")

    def test_maintenance_blocks_booking_and_preserves_reservation(self):
        room = self._room()
        reservation = self._reservation(room, hours_from=72, number="CASE-2006")
        self._login()
        response = self.client.post(
            f"/api/locations/{room.pk}/maintenance/",
            data={"title": "AC repair", "description": "No cooling", "priority": "high"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["status"], "maintenance")
        self.assertEqual(payload["occupancy"], "reserved")
        self.assertFalse(payload["is_bookable_now"])
        self.assertEqual(payload["upcoming_booking"]["id"], reservation.pk)
        self.assertEqual(MaintenanceIssue.objects.filter(location=room).count(), 1)
        reservation.refresh_from_db()
        self.assertEqual(reservation.stage, PipelineStage.WON)
        self.assertIsNone(reservation.actual_check_out)
        resolved = self.client.post(
            f"/api/locations/{room.pk}/maintenance/resolve/",
            data={"notes": "Fixed"},
            content_type="application/json",
        )
        self.assertEqual(resolved.status_code, 200, resolved.content)
        self.assertEqual(resolved.json()["status"], "available")
        self.assertEqual(resolved.json()["occupancy"], "reserved")

    def test_maintenance_blocks_check_in_without_override(self):
        room = self._room(status=LocationStatus.MAINTENANCE)
        reservation = self._reservation(room, hours_from=1, number="CASE-2007")
        self._login("staff.kl", "staff-pass-123")
        blocked = self.client.post(
            f"/api/locations/{room.pk}/check-in/",
            data={"case_id": reservation.pk},
            content_type="application/json",
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["code"], "status_blocked")
        override = self.client.post(
            f"/api/locations/{room.pk}/check-in/",
            data={"case_id": reservation.pk, "override": True},
            content_type="application/json",
        )
        self.assertEqual(override.status_code, 403)

    def test_permissions_scope_locations_to_assigned_properties(self):
        room = self._room()
        other = Location.objects.create(
            property=self.other_hotel,
            name="Villa 01",
            code="V01",
            location_type=LocationType.VILLA,
            status=LocationStatus.AVAILABLE,
        )
        self._login("staff.kl", "staff-pass-123")
        self.assertEqual(self.client.get(f"/api/locations/{room.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/locations/{other.pk}/").status_code, 403)
        self._login("staff.other", "staff-pass-123")
        self.assertEqual(self.client.get(f"/api/locations/{room.pk}/").status_code, 403)
        self._login("manager.kl", "staff-pass-123")
        self.assertEqual(self.client.get(f"/api/locations/{room.pk}/").status_code, 200)
        self._login()
        self.assertEqual(self.client.get(f"/api/locations/{other.pk}/").status_code, 200)
