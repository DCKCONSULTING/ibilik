from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.catalog import ROLE_MANAGER, ROLE_STAFF
from accounts.models import Property
from accounts.services import create_user, initialize_access_control
from cases.services import create_case
from crm.models import Customer
from locations.models import Location, LocationType
from pipeline.models import PipelineStage


class BookingApiTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.superuser = User.objects.create_superuser("root", "root@example.com", "super-secret-pass")
        self.manager = create_user(
            username="manager.pat",
            password="manager-pass-123",
            first_name="Pat",
            last_name="Manager",
            role=ROLE_MANAGER,
        )
        self.cairo_staff = create_user(
            username="staff.lee",
            password="staff-pass-123",
            first_name="Aiman",
            last_name="Rahman",
            role=ROLE_STAFF,
        )
        self.alex_staff = create_user(
            username="staff.other",
            password="staff-pass-123",
            first_name="Sara",
            last_name="Ali",
            role=ROLE_STAFF,
        )
        self.cairo = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.alex = Property.objects.create(name="Hotel Penang", region="Penang", city="George Town", rate="120.00")
        self.cairo.staff.add(self.cairo_staff, self.manager)
        self.alex.staff.add(self.alex_staff)
        self.customer = Customer.objects.create(
            name="John Smith",
            email="john@example.com",
            phone="+201001234567",
            property=self.cairo,
        )
        self.alex_customer = Customer.objects.create(
            name="Nour Khaled",
            email="nour@example.com",
            phone="+201009999999",
            property=self.alex,
        )
        self.room = Location.objects.create(
            property=self.cairo,
            name="Deluxe 1201",
            code="KL-1201",
            location_type=LocationType.ROOM,
        )
        now = timezone.now()
        self.upcoming = self._make_stay(
            title="Weekend stay",
            customer=self.customer,
            property_obj=self.cairo,
            staff=self.cairo_staff,
            location=self.room,
            check_in=now + timedelta(days=2),
            check_out=now + timedelta(days=4),
            value="4500.00",
        )
        self.in_house = self._make_stay(
            title="Current guest",
            customer=self.customer,
            property_obj=self.cairo,
            staff=self.cairo_staff,
            location=self.room,
            check_in=now - timedelta(days=1),
            check_out=now + timedelta(days=1),
            value="3200.00",
        )
        self.completed = self._make_stay(
            title="Past stay",
            customer=self.customer,
            property_obj=self.cairo,
            staff=self.cairo_staff,
            check_in=now - timedelta(days=10),
            check_out=now - timedelta(days=7),
            value="2100.00",
        )
        self.cancelled = self._make_stay(
            title="Cancelled stay",
            customer=self.customer,
            property_obj=self.cairo,
            staff=self.cairo_staff,
            check_in=now + timedelta(days=8),
            check_out=now + timedelta(days=10),
            value="1800.00",
            stage=PipelineStage.LOST,
        )
        self.alex_booking = self._make_stay(
            title="Beach stay",
            customer=self.alex_customer,
            property_obj=self.alex,
            staff=self.alex_staff,
            check_in=now + timedelta(days=5),
            check_out=now + timedelta(days=8),
            value="8000.00",
        )
        self.enquiry = create_case(
            actor=self.superuser,
            payload={
                "title": "No stay yet",
                "customer_id": self.customer.pk,
                "property_id": self.cairo.pk,
                "assigned_to_id": self.cairo_staff.pk,
                "stage": PipelineStage.NEW,
                "value": "500.00",
            },
        )

    def _make_stay(self, *, title, customer, property_obj, staff, check_in, check_out, value, location=None, stage=PipelineStage.WON):
        case = create_case(
            actor=self.superuser,
            payload={
                "title": title,
                "customer_id": customer.pk,
                "property_id": property_obj.pk,
                "assigned_to_id": staff.pk,
                "source": "website",
                "stage": stage,
                "value": value,
            },
        )
        case.check_in = check_in
        case.check_out = check_out
        case.location = location
        case.save(update_fields=["check_in", "check_out", "location", "updated_at"])
        return case

    def _login(self, username, password="staff-pass-123"):
        if username == "root":
            password = "super-secret-pass"
        if username == "manager.pat":
            password = "manager-pass-123"
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_list_is_rejected(self):
        response = self.client.get("/api/bookings/")
        self.assertEqual(response.status_code, 401)

    def test_list_includes_only_stays(self):
        self._login("root")
        listing = self.client.get("/api/bookings/")
        self.assertEqual(listing.status_code, 200)
        body = listing.json()
        self.assertEqual(body["resource"], "bookings")
        self.assertEqual(body["count"], 5)
        ids = {item["id"] for item in body["results"]}
        self.assertIn(self.upcoming.pk, ids)
        self.assertNotIn(self.enquiry.pk, ids)
        upcoming = next(item for item in body["results"] if item["id"] == self.upcoming.pk)
        self.assertEqual(upcoming["booking_number"], self.upcoming.case_number)
        self.assertEqual(upcoming["status"], "upcoming")
        self.assertEqual(upcoming["nights"], 2)
        self.assertEqual(upcoming["location"]["name"], "Deluxe 1201")

    def test_staff_sees_only_accessible_property_bookings(self):
        self._login("staff.lee")
        listing = self.client.get("/api/bookings/").json()
        self.assertEqual(listing["count"], 4)
        self.assertTrue(all(item["property"]["id"] == self.cairo.pk for item in listing["results"]))
        self.assertEqual(self.client.get(f"/api/bookings/{self.alex_booking.pk}/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/bookings/{self.upcoming.pk}/").status_code, 200)

    def test_search_and_filters(self):
        self._login("root")
        self.assertEqual(self.client.get("/api/bookings/", {"search": self.upcoming.case_number}).json()["count"], 1)
        self.assertGreaterEqual(self.client.get("/api/bookings/", {"search": "John Smith"}).json()["count"], 1)
        self.assertGreaterEqual(self.client.get("/api/bookings/", {"search": "Hotel KL"}).json()["count"], 1)
        self.assertGreaterEqual(self.client.get("/api/bookings/", {"search": "KL-1201"}).json()["count"], 1)
        upcoming = self.client.get("/api/bookings/", {"status": "upcoming"}).json()
        self.assertTrue(all(item["status"] == "upcoming" for item in upcoming["results"]))
        self.assertIn(self.upcoming.pk, {item["id"] for item in upcoming["results"]})
        in_house = self.client.get("/api/bookings/", {"status": "in_house"}).json()
        self.assertEqual(in_house["count"], 1)
        self.assertEqual(in_house["results"][0]["id"], self.in_house.pk)
        completed = self.client.get("/api/bookings/", {"status": "completed"}).json()
        self.assertEqual(completed["count"], 1)
        self.assertEqual(completed["results"][0]["id"], self.completed.pk)
        cancelled = self.client.get("/api/bookings/", {"status": "cancelled"}).json()
        self.assertEqual(cancelled["count"], 1)
        self.assertEqual(cancelled["results"][0]["id"], self.cancelled.pk)
        by_property = self.client.get("/api/bookings/", {"property": self.alex.pk}).json()
        self.assertEqual(by_property["count"], 1)
        self.assertEqual(by_property["results"][0]["id"], self.alex_booking.pk)
        by_staff = self.client.get("/api/bookings/", {"staff": self.cairo_staff.pk}).json()
        self.assertTrue(all(item["staff"]["id"] == self.cairo_staff.pk for item in by_staff["results"]))
        by_customer = self.client.get("/api/bookings/", {"customer": self.alex_customer.pk}).json()
        self.assertEqual(by_customer["count"], 1)
        by_location = self.client.get("/api/bookings/", {"location": self.room.pk}).json()
        self.assertTrue(all(item["location"]["id"] == self.room.pk for item in by_location["results"]))
        by_case = self.client.get("/api/bookings/", {"case": self.upcoming.pk}).json()
        self.assertEqual(by_case["count"], 1)
        this_week = self.client.get("/api/bookings/", {"date_field": "check_in", "due": "this_week"}).json()
        self.assertGreaterEqual(this_week["count"], 1)

    def test_pagination_and_ordering(self):
        self._login("root")
        listing = self.client.get("/api/bookings/", {"page_size": 2, "page": 1, "ordering": "check_in"})
        self.assertEqual(listing.status_code, 200)
        body = listing.json()
        self.assertEqual(body["count"], 5)
        self.assertEqual(len(body["results"]), 2)
        self.assertTrue(body["has_next"])
        ordered = self.client.get("/api/bookings/", {"ordering": "check_in"}).json()
        check_ins = [item["check_in"] for item in ordered["results"]]
        self.assertEqual(check_ins, sorted(check_ins))

    def test_detail_and_missing_booking(self):
        self._login("root")
        detail = self.client.get(f"/api/bookings/{self.upcoming.pk}/")
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["booking_number"], self.upcoming.case_number)
        self.assertEqual(body["customer"]["name"], "John Smith")
        self.assertEqual(body["staff"]["username"], "staff.lee")
        self.assertEqual(body["case"]["case_number"], self.upcoming.case_number)
        self.assertEqual(self.client.get(f"/api/bookings/{self.enquiry.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/api/bookings/999999/").status_code, 404)
