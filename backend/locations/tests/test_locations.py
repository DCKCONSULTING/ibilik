from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.catalog import ROLE_STAFF
from accounts.models import Property, UserPropertyAccess
from accounts.services import create_user, initialize_access_control
from cases.models import Case
from crm.models import Customer
from locations.models import Location, LocationStatus, LocationType
from locations.services import delete_location
from pipeline.models import PipelineStage


class LocationApiTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.superuser = User.objects.create_superuser(
            username="root",
            email="root@example.com",
            password="super-secret-pass",
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
        self.cairo.staff.add(self.assigned_staff)
        self.customer = Customer.objects.create(name="John Smith", email="john@example.com", property=self.cairo)

    def _login(self, username: str, password: str):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def _create(self, property_id: int, payload: dict, expected=201):
        response = self.client.post(
            f"/api/properties/{property_id}/locations/",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, expected, response.content)
        return response

    def test_create_room_table_meeting_room_and_other(self):
        self._login("root", "super-secret-pass")
        room = self._create(
            self.cairo.pk,
            {"name": "Room 101", "code": "101", "type": "room", "capacity": 2, "status": "available"},
        ).json()
        table = self._create(
            self.cairo.pk,
            {"name": "Restaurant Table 01", "code": "T01", "type": "table", "capacity": 4},
        ).json()
        meeting = self._create(
            self.cairo.pk,
            {"name": "Meeting Room A", "code": "MR-A", "type": "meeting_room", "capacity": 20},
        ).json()
        other = self._create(
            self.cairo.pk,
            {"name": "Spa Cabana", "code": "SPA-1", "type": "other", "description": "Poolside cabana."},
        ).json()

        self.assertEqual(room["type"], "room")
        self.assertEqual(room["type_label"], "Room")
        self.assertEqual(room["property"]["id"], self.cairo.pk)
        self.assertEqual(table["type"], "table")
        self.assertEqual(meeting["type"], "meeting_room")
        self.assertEqual(other["type"], "other")
        self.assertEqual(Location.objects.filter(property=self.cairo).count(), 4)

    def test_location_belongs_to_one_property(self):
        self._login("root", "super-secret-pass")
        payload = self._create(self.cairo.pk, {"name": "Room 101", "code": "101", "type": "room"}).json()
        location = Location.objects.get(pk=payload["id"])
        self.assertEqual(location.property_id, self.cairo.pk)
        self.assertEqual(list(self.cairo.locations.values_list("name", flat=True)), ["Room 101"])

    def test_code_is_unique_within_a_property_but_reusable_across_properties(self):
        self._login("root", "super-secret-pass")
        self._create(self.cairo.pk, {"name": "Room 101", "code": "101", "type": "room"})
        duplicate = self._create(
            self.cairo.pk,
            {"name": "Room 101 Deluxe", "code": "101", "type": "room"},
            expected=409,
        )
        self.assertEqual(duplicate.json()["code"], "duplicate_code")

        reused = self._create(self.alex.pk, {"name": "Room 101", "code": "101", "type": "room"}).json()
        self.assertEqual(reused["property"]["id"], self.alex.pk)
        self.assertEqual(reused["code"], "101")
        self.assertEqual(Location.objects.filter(code="101").count(), 2)

    def test_empty_codes_are_allowed_on_the_same_property(self):
        self._login("root", "super-secret-pass")
        self._create(self.cairo.pk, {"name": "Uncoded Lounge", "type": "other"})
        self._create(self.cairo.pk, {"name": "Uncoded Terrace", "type": "other"})
        self.assertEqual(Location.objects.filter(property=self.cairo, code="").count(), 2)

    def test_superuser_sees_all_locations(self):
        Location.objects.create(property=self.cairo, name="Room 101", code="101", location_type=LocationType.ROOM)
        Location.objects.create(property=self.alex, name="Villa 01", code="V01", location_type=LocationType.VILLA)
        self._login("root", "super-secret-pass")
        cairo = self.client.get(f"/api/properties/{self.cairo.pk}/locations/")
        alex = self.client.get(f"/api/properties/{self.alex.pk}/locations/")
        self.assertEqual(cairo.status_code, 200)
        self.assertEqual(alex.status_code, 200)
        self.assertEqual([item["name"] for item in cairo.json()["results"]], ["Room 101"])
        self.assertEqual([item["name"] for item in alex.json()["results"]], ["Villa 01"])

    def test_global_staff_sees_locations_across_properties(self):
        Location.objects.create(property=self.cairo, name="Room 101", code="101", location_type=LocationType.ROOM)
        Location.objects.create(property=self.alex, name="Villa 01", code="V01", location_type=LocationType.VILLA)
        self._login("staff.global", "staff-pass-123")
        self.assertEqual(self.client.get(f"/api/properties/{self.cairo.pk}/locations/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/properties/{self.alex.pk}/locations/").status_code, 200)

    def test_assigned_staff_only_sees_locations_for_assigned_properties(self):
        cairo_room = Location.objects.create(
            property=self.cairo,
            name="Room 101",
            code="101",
            location_type=LocationType.ROOM,
        )
        alex_villa = Location.objects.create(
            property=self.alex,
            name="Villa 01",
            code="V01",
            location_type=LocationType.VILLA,
        )
        self._login("staff.lee", "staff-pass-123")
        allowed = self.client.get(f"/api/properties/{self.cairo.pk}/locations/")
        blocked = self.client.get(f"/api/properties/{self.alex.pk}/locations/")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual([item["id"] for item in allowed.json()["results"]], [cairo_room.pk])
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(self.client.get(f"/api/locations/{cairo_room.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/locations/{alex_villa.pk}/").status_code, 403)

    def test_unauthorized_property_cannot_create_or_edit_locations(self):
        self._login("staff.other", "staff-pass-123")
        created = self._create(
            self.cairo.pk,
            {"name": "Room 101", "code": "101", "type": "room"},
            expected=403,
        )
        self.assertEqual(created.json()["code"], "property_forbidden")
        location = Location.objects.create(
            property=self.cairo,
            name="Room 101",
            code="101",
            location_type=LocationType.ROOM,
        )
        patched = self.client.patch(
            f"/api/locations/{location.pk}/",
            data={"name": "Hacked"},
            content_type="application/json",
        )
        self.assertEqual(patched.status_code, 403)
        location.refresh_from_db()
        self.assertEqual(location.name, "Room 101")

    def test_filters_type_status_active_and_search(self):
        Location.objects.create(
            property=self.cairo,
            name="Room 101",
            code="101",
            location_type=LocationType.ROOM,
            status=LocationStatus.AVAILABLE,
        )
        Location.objects.create(
            property=self.cairo,
            name="Restaurant Table 01",
            code="T01",
            location_type=LocationType.TABLE,
            status=LocationStatus.DIRTY,
        )
        Location.objects.create(
            property=self.cairo,
            name="Meeting Room A",
            code="MR-A",
            location_type=LocationType.MEETING_ROOM,
            status=LocationStatus.MAINTENANCE,
            active=False,
        )
        self._login("root", "super-secret-pass")
        by_type = self.client.get(f"/api/properties/{self.cairo.pk}/locations/", {"type": "table"})
        self.assertEqual([item["code"] for item in by_type.json()["results"]], ["T01"])

        by_status = self.client.get(f"/api/properties/{self.cairo.pk}/locations/", {"status": "available"})
        self.assertEqual([item["code"] for item in by_status.json()["results"]], ["101"])

        by_active = self.client.get(f"/api/properties/{self.cairo.pk}/locations/", {"active": "false"})
        self.assertEqual([item["code"] for item in by_active.json()["results"]], ["MR-A"])

        by_search = self.client.get(f"/api/properties/{self.cairo.pk}/locations/", {"search": "101"})
        self.assertEqual([item["name"] for item in by_search.json()["results"]], ["Room 101"])

        by_code = self.client.get(f"/api/properties/{self.cairo.pk}/locations/", {"search": "T01"})
        self.assertEqual([item["name"] for item in by_code.json()["results"]], ["Restaurant Table 01"])

    def test_deactivate_soft_disables_location(self):
        self._login("root", "super-secret-pass")
        payload = self._create(self.cairo.pk, {"name": "Room 101", "code": "101", "type": "room"}).json()
        response = self.client.post(f"/api/locations/{payload['id']}/deactivate/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["active"])
        self.assertEqual(body["status"], "inactive")
        self.assertTrue(Location.objects.filter(pk=payload["id"]).exists())

    def test_referenced_location_cannot_be_hard_deleted(self):
        location = Location.objects.create(
            property=self.cairo,
            name="Room 101",
            code="101",
            location_type=LocationType.ROOM,
        )
        Case.objects.create(
            sequence=1,
            case_number="CASE-1001",
            customer=self.customer,
            property=self.cairo,
            location=location,
            title="Weekend stay",
            stage=PipelineStage.WON,
        )
        self._login("root", "super-secret-pass")
        response = self.client.delete(f"/api/locations/{location.pk}/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "location_in_use")
        self.assertTrue(Location.objects.filter(pk=location.pk).exists())

        with self.assertRaises(Exception):
            delete_location(location)
        self.assertTrue(Location.objects.filter(pk=location.pk).exists())

        deactivated = self.client.post(f"/api/locations/{location.pk}/deactivate/")
        self.assertEqual(deactivated.status_code, 200)
        self.assertFalse(deactivated.json()["active"])

    def test_property_list_includes_location_count_not_the_collection(self):
        Location.objects.create(property=self.cairo, name="Room 101", code="101", location_type=LocationType.ROOM)
        Location.objects.create(property=self.cairo, name="Room 102", code="102", location_type=LocationType.ROOM)
        self._login("root", "super-secret-pass")
        response = self.client.get("/api/properties/")
        cairo = next(item for item in response.json()["results"] if item["id"] == self.cairo.pk)
        self.assertEqual(cairo["location_count"], 2)
        self.assertNotIn("locations", cairo)

    def test_viewer_without_change_permission_cannot_create(self):
        from accounts.services import assign_limited_permissions

        viewer = create_user(username="viewer.only", password="staff-pass-123", role=ROLE_STAFF)
        assign_limited_permissions(viewer, ["properties.view_property"], actor=self.superuser)
        self.cairo.staff.add(viewer)
        self._login("viewer.only", "staff-pass-123")
        response = self._create(
            self.cairo.pk,
            {"name": "Room 101", "code": "101", "type": "room"},
            expected=403,
        )
        self.assertEqual(response.json()["code"], "permission_denied")
        listing = self.client.get(f"/api/properties/{self.cairo.pk}/locations/")
        self.assertEqual(listing.status_code, 200)

    def test_availability_reuses_location_inventory(self):
        Location.objects.create(
            property=self.cairo,
            name="Room 101",
            code="101",
            location_type=LocationType.ROOM,
            status=LocationStatus.AVAILABLE,
        )
        Location.objects.create(
            property=self.alex,
            name="Villa 01",
            code="V01",
            location_type=LocationType.VILLA,
            status=LocationStatus.AVAILABLE,
        )
        self._login("staff.lee", "staff-pass-123")
        response = self.client.get("/api/availability/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["resource"], "availability")
        names = {item["name"] for item in payload["results"]}
        self.assertEqual(names, {"Room 101"})
        self.assertEqual(payload["results"][0]["status"], "available")
        self.assertEqual(payload["resource"], "availability")
        self.assertIn("properties", payload)
        self.assertIn("types", payload)
        self.assertIn("statuses", payload)
        self.assertEqual(payload["results"][0]["occupancy"], "free")

    def test_availability_filters_occupancy_and_property(self):
        now = timezone.now()
        free_room = Location.objects.create(
            property=self.cairo,
            name="Room 101",
            code="101",
            location_type=LocationType.ROOM,
            status=LocationStatus.AVAILABLE,
            floor="1",
            is_bookable=True,
        )
        occupied_room = Location.objects.create(
            property=self.cairo,
            name="Room 202",
            code="202",
            location_type=LocationType.ROOM,
            status=LocationStatus.AVAILABLE,
            floor="2",
        )
        desk = Location.objects.create(
            property=self.cairo,
            name="Lobby Desk",
            code="D01",
            location_type=LocationType.DESK,
            status=LocationStatus.AVAILABLE,
            is_bookable=False,
        )
        Location.objects.create(
            property=self.alex,
            name="Villa 01",
            code="V01",
            location_type=LocationType.VILLA,
            status=LocationStatus.AVAILABLE,
        )
        Case.objects.create(
            sequence=2,
            case_number="CASE-1002",
            customer=self.customer,
            property=self.cairo,
            location=occupied_room,
            title="In house stay",
            stage=PipelineStage.WON,
            check_in=now - timedelta(days=1),
            check_out=now + timedelta(days=1),
            actual_check_in=now - timedelta(days=1),
        )
        self._login("root", "super-secret-pass")
        listing = self.client.get("/api/availability/").json()
        self.assertGreaterEqual(listing["count"], 4)
        free = self.client.get("/api/availability/", {"occupancy": "free"}).json()
        self.assertTrue(all(item["occupancy"] == "free" for item in free["results"]))
        self.assertIn(free_room.pk, {item["id"] for item in free["results"]})
        in_house = self.client.get("/api/availability/", {"occupancy": "in_house"}).json()
        self.assertEqual(in_house["count"], 1)
        self.assertEqual(in_house["results"][0]["id"], occupied_room.pk)
        self.assertEqual(in_house["results"][0]["current_booking"]["case_number"], "CASE-1002")
        by_property = self.client.get("/api/availability/", {"property": self.cairo.pk}).json()
        self.assertTrue(all(item["property"]["id"] == self.cairo.pk for item in by_property["results"]))
        by_type = self.client.get("/api/availability/", {"type": "desk"}).json()
        self.assertEqual({item["id"] for item in by_type["results"]}, {desk.pk})
        bookable = self.client.get("/api/availability/", {"bookable": "true", "property": self.cairo.pk}).json()
        self.assertNotIn(desk.pk, {item["id"] for item in bookable["results"]})
        by_floor = self.client.get("/api/availability/", {"floor": "1"}).json()
        self.assertEqual({item["id"] for item in by_floor["results"]}, {free_room.pk})
        reserved_room = Location.objects.create(
            property=self.cairo,
            name="Suite 301",
            code="301",
            location_type=LocationType.SUITE,
            status=LocationStatus.DIRTY,
        )
        Case.objects.create(
            sequence=3,
            case_number="CASE-1003",
            customer=self.customer,
            property=self.cairo,
            location=reserved_room,
            title="Reserved stay",
            stage=PipelineStage.WON,
            check_in=now + timedelta(days=3),
            check_out=now + timedelta(days=6),
        )
        reserved = self.client.get("/api/availability/", {"occupancy": "reserved"}).json()
        self.assertEqual(reserved["count"], 1)
        self.assertEqual(reserved["results"][0]["id"], reserved_room.pk)
        self.assertEqual(reserved["results"][0]["occupancy"], "reserved")
        self.assertEqual(reserved["results"][0]["upcoming_booking"]["customer"]["name"], "John Smith")
        free = self.client.get("/api/availability/", {"occupancy": "free"}).json()
        self.assertNotIn(reserved_room.pk, {item["id"] for item in free["results"]})
        self.assertNotIn(occupied_room.pk, {item["id"] for item in free["results"]})
        by_search = self.client.get("/api/availability/", {"search": "Room 101"}).json()
        self.assertEqual(by_search["count"], 1)
        paged = self.client.get("/api/availability/", {"page_size": 2, "page": 1})
        self.assertEqual(paged.status_code, 200)
        self.assertEqual(len(paged.json()["results"]), 2)
        self.assertTrue(paged.json()["has_next"])

    def test_create_suite_with_hotel_location_fields(self):
        self._login("root", "super-secret-pass")
        payload = self._create(
            self.cairo.pk,
            {
                "name": "Executive Suite 301",
                "code": "301",
                "type": "suite",
                "capacity": 3,
                "max_adults": 2,
                "max_children": 1,
                "floor": "3",
                "bed_type": "king",
                "bed_count": 1,
                "base_rate": "380.00",
                "currency": "MYR",
                "is_bookable": True,
                "size_sqm": "48.00",
                "description": "City-view suite",
            },
        ).json()
        self.assertEqual(payload["type"], "suite")
        self.assertEqual(payload["type_label"], "Suite")
        self.assertEqual(payload["max_adults"], 2)
        self.assertEqual(payload["max_children"], 1)
        self.assertEqual(payload["floor"], "3")
        self.assertEqual(payload["bed_type"], "king")
        self.assertEqual(payload["base_rate"], "380.00")
        self.assertEqual(payload["currency"], "MYR")
        self.assertTrue(payload["is_bookable"])
        self.assertEqual(payload["size_sqm"], "48.00")

        listing = self.client.get(f"/api/properties/{self.cairo.pk}/locations/")
        self.assertEqual(listing.status_code, 200)
        suite = next(item for item in listing.json()["results"] if item["id"] == payload["id"])
        self.assertEqual(suite["type"], "suite")
        self.assertEqual(suite["base_rate"], "380.00")

        detail = self.client.get(f"/api/locations/{payload['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["capacity"], 3)
        self.assertEqual(detail.json()["currency"], "MYR")

    def test_location_currency_falls_back_to_property_currency(self):
        self.cairo.currency = "MYR"
        self.cairo.save(update_fields=["currency"])
        self._login("root", "super-secret-pass")
        payload = self._create(
            self.cairo.pk,
            {"name": "Deluxe Room 109", "code": "109", "type": "room", "capacity": 2},
        ).json()
        self.assertEqual(payload["currency"], "MYR")
        self.assertIsNone(payload["base_rate"])

    def test_location_capacity_must_be_positive(self):
        self._login("root", "super-secret-pass")
        response = self._create(
            self.cairo.pk,
            {"name": "Broken Room", "code": "000", "type": "room", "capacity": 0},
            expected=400,
        )
        self.assertIn("capacity", response.json()["message"].lower())
