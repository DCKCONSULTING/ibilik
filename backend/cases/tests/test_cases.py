from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.catalog import ROLE_STAFF
from accounts.models import Property, UserPropertyAccess
from accounts.services import create_user, initialize_access_control
from cases.models import ActivityEvent, Case, FollowUpStatus, FollowUpType
from cases.services import CaseError, attach_inbound_message_to_case, create_case, create_follow_up, update_case
from crm.models import Channel, Conversation, Customer, Message, MessageDirection, SenderType
from crm.services import ingest_inbound_message
from pipeline.models import PipelineStage


class CaseServiceTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.superuser = User.objects.create_superuser("root", "root@example.com", "super-secret-pass")
        self.property = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.other_property = Property.objects.create(name="Hotel Penang", region="Penang", city="George Town", rate="120.00")
        self.customer = Customer.objects.create(
            name="John Smith",
            email="john@example.com",
            phone="+201001234567",
            property=self.property,
        )
        self.staff = create_user(
            username="staff.lee",
            password="staff-pass-123",
            first_name="Aiman",
            last_name="Rahman",
            role=ROLE_STAFF,
        )
        self.other_staff = create_user(username="staff.other", password="staff-pass-123", role=ROLE_STAFF)
        self.property.staff.add(self.staff)
        self.other_property.staff.add(self.other_staff)

    def test_case_creation_number_and_relationships(self):
        first = create_case(
            actor=self.superuser,
            payload={
                "title": "Family room — 3 nights",
                "customer_id": self.customer.pk,
                "property_id": self.property.pk,
                "assigned_to_id": self.staff.pk,
                "original_request": "I need a family room for 3 nights.",
                "source": "whatsapp",
            },
        )
        second = create_case(
            actor=self.superuser,
            payload={"title": "Airport transfer", "customer_id": self.customer.pk, "property_id": self.property.pk},
        )
        self.assertEqual(first.case_number, "CASE-1001")
        self.assertEqual(second.case_number, "CASE-1002")
        self.assertNotEqual(first.case_number, second.case_number)
        self.assertEqual(first.customer_id, second.customer_id)
        self.assertEqual(first.property_id, self.property.pk)
        self.assertEqual(first.assigned_to_id, self.staff.pk)
        self.assertEqual(first.stage, PipelineStage.NEW)
        self.assertEqual(self.customer.cases.count(), 2)
        self.assertEqual(first.original_request, "I need a family room for 3 nights.")
        update_case(first, {"description": "Updated later details."}, actor=self.superuser)
        first.refresh_from_db()
        self.assertEqual(first.original_request, "I need a family room for 3 nights.")
        self.assertEqual(first.description, "Updated later details.")
        self.assertEqual(Case.objects.filter(case_number="CASE-1001").count(), 1)

    def test_cases_remain_independent_for_the_same_customer(self):
        first = create_case(
            actor=self.superuser,
            payload={"title": "Room booking", "customer_id": self.customer.pk, "property_id": self.property.pk, "stage": "new"},
        )
        second = create_case(
            actor=self.superuser,
            payload={"title": "Airport transfer", "customer_id": self.customer.pk, "property_id": self.property.pk, "stage": "quoted"},
        )
        update_case(first, {"stage": "won", "value": "4500.00"}, actor=self.superuser)
        second.refresh_from_db()
        self.assertEqual(second.stage, PipelineStage.QUOTED)
        self.assertIsNone(second.value)
        self.assertEqual(first.activities.filter(event_type=ActivityEvent.STAGE_CHANGED).count(), 1)
        self.assertFalse(second.activities.filter(event_type=ActivityEvent.STAGE_CHANGED).exists())


class CaseFollowUpAndActivityTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.superuser = User.objects.create_superuser("root", "root@example.com", "super-secret-pass")
        self.property = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.customer = Customer.objects.create(name="John Smith", email="john@example.com", property=self.property)
        self.staff = create_user(
            username="staff.lee",
            password="staff-pass-123",
            first_name="Aiman",
            last_name="Rahman",
            role=ROLE_STAFF,
        )
        self.other_staff = create_user(username="staff.other", password="staff-pass-123", role=ROLE_STAFF)
        self.property.staff.add(self.staff)
        self.case = create_case(
            actor=self.superuser,
            payload={
                "title": "Family room",
                "customer_id": self.customer.pk,
                "property_id": self.property.pk,
                "assigned_to_id": self.staff.pk,
            },
        )

    def test_follow_up_create_complete_cancel_overdue_and_assignment(self):
        due = timezone.now() + timedelta(hours=2)
        follow_up = create_follow_up(
            self.case,
            {
                "type": FollowUpType.SEND_QUOTE,
                "title": "Send quote",
                "assigned_to_id": self.staff.pk,
                "due_at": due.isoformat(),
            },
            actor=self.superuser,
        )
        self.assertEqual(follow_up.status, FollowUpStatus.PENDING)
        self.assertTrue(self.case.activities.filter(event_type=ActivityEvent.FOLLOW_UP_CREATED).exists())

        with self.assertRaises(CaseError):
            create_follow_up(self.case, {"title": "Bad assign", "assigned_to_id": self.other_staff.pk}, actor=self.superuser)

        overdue = create_follow_up(
            self.case,
            {"title": "Overdue call", "type": FollowUpType.CALL_CUSTOMER, "due_at": (timezone.now() - timedelta(hours=1)).isoformat()},
            actor=self.superuser,
        )
        self.assertTrue(overdue.is_overdue())

        self._login()
        listed = self.client.get(f"/api/cases/{self.case.pk}/follow-ups/").json()["results"]
        overdue_row = next(item for item in listed if item["id"] == overdue.pk)
        self.assertEqual(overdue_row["status"], "overdue")

        completed = self.client.post(f"/api/cases/{self.case.pk}/follow-ups/{follow_up.pk}/complete/")
        self.assertEqual(completed.status_code, 200)
        body = completed.json()
        self.assertEqual(body["status"], "completed")
        self.assertIsNotNone(body["completed_at"])
        follow_up.refresh_from_db()
        self.assertEqual(follow_up.status, FollowUpStatus.COMPLETED)
        self.assertIsNotNone(follow_up.completed_at)
        self.assertTrue(self.case.activities.filter(event_type=ActivityEvent.FOLLOW_UP_COMPLETED).exists())

        cancelled = self.client.delete(f"/api/cases/{self.case.pk}/follow-ups/{overdue.pk}/")
        self.assertEqual(cancelled.status_code, 200)
        overdue.refresh_from_db()
        self.assertEqual(overdue.status, FollowUpStatus.CANCELLED)
        self.assertTrue(self.case.activities.filter(event_type=ActivityEvent.FOLLOW_UP_CANCELLED).exists())

        edited = self.client.patch(
            f"/api/cases/{self.case.pk}/follow-ups/{follow_up.pk}/",
            data={"title": "Send quote (revised)"},
            content_type="application/json",
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["title"], "Send quote (revised)")

    def _login(self):
        response = self.client.post(
            "/api/auth/login/",
            data={"username": "root", "password": "super-secret-pass"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)


class CaseConversationAndPermissionTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.superuser = User.objects.create_superuser("root", "root@example.com", "super-secret-pass")
        self.cairo_staff = create_user(
            username="staff.lee",
            password="staff-pass-123",
            first_name="Aiman",
            last_name="Rahman",
            role=ROLE_STAFF,
        )
        self.other_staff = create_user(username="staff.other", password="staff-pass-123", role=ROLE_STAFF)
        self.cairo = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.alex = Property.objects.create(name="Hotel Penang", region="Penang", city="George Town", rate="120.00")
        self.cairo.staff.add(self.cairo_staff)
        self.alex.staff.add(self.other_staff)
        self.customer = Customer.objects.create(name="John Smith", email="john@example.com", phone="+20100", property=self.cairo)

    def _login(self, username, password="staff-pass-123"):
        if username == "root":
            password = "super-secret-pass"
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def _conversation(self, *, subject, content):
        conversation = Conversation.objects.create(
            customer=self.customer,
            property=self.cairo,
            channel=Channel.WHATSAPP,
            subject=subject,
        )
        Message.objects.create(
            conversation=conversation,
            channel=Channel.WHATSAPP,
            direction=MessageDirection.INBOUND,
            sender_type=SenderType.CUSTOMER,
            sender_name=self.customer.name,
            content=content,
        )
        return conversation

    def test_case_only_returns_related_conversation_messages(self):
        room = self._conversation(subject="Room", content="I need a family room.")
        transfer = self._conversation(subject="Transfer", content="I also need an airport transfer.")
        case_one = create_case(
            actor=self.superuser,
            payload={
                "title": "Family room",
                "customer_id": self.customer.pk,
                "property_id": self.cairo.pk,
                "conversation_id": room.pk,
                "original_request": "I need a family room.",
            },
        )
        case_two = create_case(
            actor=self.superuser,
            payload={
                "title": "Airport transfer",
                "customer_id": self.customer.pk,
                "property_id": self.cairo.pk,
                "conversation_id": transfer.pk,
                "original_request": "I also need an airport transfer.",
            },
        )
        self._login("root")
        first = self.client.get(f"/api/cases/{case_one.pk}/").json()
        second = self.client.get(f"/api/cases/{case_two.pk}/").json()
        self.assertEqual([item["content"] for item in first["messages"]], ["I need a family room."])
        self.assertEqual([item["content"] for item in second["messages"]], ["I also need an airport transfer."])
        self.assertNotIn("I also need an airport transfer.", [item["content"] for item in first["messages"]])

    def test_property_permissions_on_cases_and_follow_ups(self):
        cairo_case = create_case(
            actor=self.superuser,
            payload={"title": "KL case", "customer_id": self.customer.pk, "property_id": self.cairo.pk},
        )
        alex_customer = Customer.objects.create(name="Nour Khaled", email="nour@example.com", property=self.alex)
        alex_case = create_case(
            actor=self.superuser,
            payload={"title": "Alex case", "customer_id": alex_customer.pk, "property_id": self.alex.pk},
        )
        follow_up = create_follow_up(alex_case, {"title": "Call Nour"}, actor=self.superuser)

        self._login("root")
        self.assertEqual(self.client.get("/api/cases/").json()["count"], 2)

        self._login("staff.lee")
        listing = self.client.get("/api/cases/").json()
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["results"][0]["id"], cairo_case.pk)
        self.assertEqual(self.client.get(f"/api/cases/{alex_case.pk}/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/cases/{alex_case.pk}/follow-ups/").status_code, 403)
        self.assertEqual(
            self.client.post(
                f"/api/cases/{alex_case.pk}/follow-ups/",
                data={"title": "Should fail"},
                content_type="application/json",
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(f"/api/cases/{alex_case.pk}/follow-ups/{follow_up.pk}/complete/").status_code,
            403,
        )

    def test_search_covers_case_number_customer_and_title(self):
        case = create_case(
            actor=self.superuser,
            payload={
                "title": "Family room — 3 nights",
                "customer_id": self.customer.pk,
                "property_id": self.cairo.pk,
            },
        )
        self._login("root")
        for query in (case.case_number, "John Smith", "+20100", "john@example.com", "Family room"):
            listing = self.client.get("/api/cases/", {"search": query}).json()
            self.assertEqual(listing["count"], 1, query)

    def test_ingest_attaches_messages_to_one_open_case(self):
        first, _ = ingest_inbound_message(
            channel=Channel.WHATSAPP,
            content="I need a room.",
            name="John Smith",
            phone="+201001234567",
            property_id=self.cairo.pk,
            external_conversation_id="wa-john-1",
        )
        second, _ = ingest_inbound_message(
            channel=Channel.WHATSAPP,
            content="For 2 people.",
            name="John Smith",
            phone="+201001234567",
            property_id=self.cairo.pk,
            external_conversation_id="wa-john-1",
        )
        self.assertEqual(first.conversation_id, second.conversation_id)
        self.assertEqual(Case.objects.filter(conversations=first.conversation).count(), 1)
        case = Case.objects.get(conversations=first.conversation)
        self.assertEqual(case.original_request, "I need a room.")
        attach_inbound_message_to_case(second)
        self.assertEqual(Case.objects.filter(conversations=first.conversation).count(), 1)

        case.stage = PipelineStage.WON
        case.closed_at = timezone.now()
        case.save(update_fields=["stage", "closed_at", "updated_at"])
        third, _ = ingest_inbound_message(
            channel=Channel.WHATSAPP,
            content="I also need an airport transfer.",
            name="John Smith",
            phone="+201001234567",
            property_id=self.cairo.pk,
            external_conversation_id="wa-john-1",
        )
        self.assertEqual(Case.objects.filter(conversations=first.conversation).count(), 2)
        new_case = Case.objects.filter(conversations=first.conversation).exclude(pk=case.pk).get()
        self.assertEqual(new_case.original_request, "I also need an airport transfer.")
        self.assertEqual(third.conversation_id, first.conversation_id)
