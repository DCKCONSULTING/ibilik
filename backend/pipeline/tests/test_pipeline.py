from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.catalog import ROLE_STAFF
from accounts.models import Property, UserPropertyAccess
from accounts.services import create_user, initialize_access_control
from cases.models import Case
from cases.numbering import allocate_case_number, link_conversation
from crm.models import Channel, Conversation, Customer, Message, MessageDirection, SenderType
from pipeline.models import PIPELINE_STAGE_ORDER, FinanceStatus, PipelineStage
from pipeline.serializers import serialize_pipeline_stages
from pipeline.services import PipelineError, validate_stage


def make_case(**kwargs) -> Case:
    sequence, case_number = allocate_case_number()
    kwargs.setdefault("sequence", sequence)
    kwargs.setdefault("case_number", case_number)
    kwargs.setdefault("original_request", kwargs.get("description") or kwargs.get("title") or "")
    conversation = kwargs.get("originating_conversation")
    case = Case.objects.create(**kwargs)
    if conversation is not None:
        link_conversation(case, conversation, originating=True)
    return case


class PipelineModelTests(TestCase):
    def setUp(self):
        initialize_access_control()
        self.property = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.customer = Customer.objects.create(name="John Smith", email="john@example.com", property=self.property)

    def test_valid_stages_and_canonical_order(self):
        self.assertEqual(
            list(PIPELINE_STAGE_ORDER),
            [
                PipelineStage.NEW,
                PipelineStage.QUALIFIED,
                PipelineStage.QUOTED,
                PipelineStage.NEGOTIATING,
                PipelineStage.WON,
                PipelineStage.LOST,
            ],
        )
        self.assertEqual(
            [item["label"] for item in serialize_pipeline_stages()],
            ["New", "Qualified", "Quoted", "Negotiating", "Won", "Lost"],
        )

    def test_default_stage_is_new(self):
        case = make_case(customer=self.customer, title="Weekend booking")
        self.assertEqual(case.stage, PipelineStage.NEW)
        self.assertTrue(case.case_number.startswith("CASE-"))

    def test_invalid_stage_is_rejected(self):
        with self.assertRaises(PipelineError):
            validate_stage("closed_won")
        sequence, case_number = allocate_case_number()
        case = Case(customer=self.customer, title="Bad stage", stage="negotiation", sequence=sequence, case_number=case_number)
        with self.assertRaises(ValidationError):
            case.full_clean()

    def test_customer_and_property_relationships(self):
        case = make_case(
            customer=self.customer,
            property=self.property,
            title="Weekend booking",
            value=Decimal("4500.00"),
        )
        self.assertEqual(case.customer.name, "John Smith")
        self.assertEqual(case.property.name, "Hotel KL")
        self.assertEqual(self.customer.cases.get().pk, case.pk)


class PipelineApiTests(TestCase):
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
        self.other_staff = create_user(
            username="staff.other",
            password="staff-pass-123",
            role=ROLE_STAFF,
        )
        self.global_staff = create_user(
            username="staff.global",
            password="staff-pass-123",
            role=ROLE_STAFF,
            property_access=UserPropertyAccess.Mode.GLOBAL,
            actor=self.superuser,
        )
        self.cairo = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.alex = Property.objects.create(name="Hotel Penang", region="Penang", city="George Town", rate="120.00")
        self.cairo.staff.add(self.cairo_staff)
        self.alex.staff.add(self.other_staff)
        self.cairo_customer = Customer.objects.create(name="John Smith", email="john@example.com", property=self.cairo)
        self.alex_customer = Customer.objects.create(name="Nour Khaled", email="nour@example.com", property=self.alex)

    def _login(self, username: str, password: str = "staff-pass-123"):
        if username == "root":
            password = "super-secret-pass"
        response = self.client.post(
            "/api/auth/login/",
            data={"username": username, "password": password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def _create(self, **payload):
        return self.client.post("/api/pipeline/", data=payload, content_type="application/json")

    def _conversation(self, customer, property_obj, *, channel=Channel.WHATSAPP, request_text="I need a family room for 3 nights."):
        conversation = Conversation.objects.create(
            customer=customer,
            property=property_obj,
            channel=channel,
            subject="Room request",
            last_message_preview=request_text,
        )
        Message.objects.create(
            conversation=conversation,
            channel=channel,
            direction=MessageDirection.INBOUND,
            sender_type=SenderType.CUSTOMER,
            sender_name=customer.name,
            content=request_text,
        )
        Message.objects.create(
            conversation=conversation,
            channel=channel,
            direction=MessageDirection.OUTBOUND,
            sender_type=SenderType.BOT,
            sender_name="AI Bot",
            content="Which property are you interested in?",
        )
        Message.objects.create(
            conversation=conversation,
            channel=channel,
            direction=MessageDirection.INBOUND,
            sender_type=SenderType.CUSTOMER,
            sender_name=customer.name,
            content="KL City Centre.",
        )
        return conversation

    def test_list_create_retrieve_update_delete_and_stage_filter(self):
        self._login("staff.global")
        created = self._create(
            customer_id=self.cairo_customer.pk,
            property_id=self.cairo.pk,
            title="Weekend booking",
            value="4500.00",
        )
        self.assertEqual(created.status_code, 201, created.content)
        body = created.json()
        self.assertEqual(body["stage"], "new")
        self.assertEqual(body["customer"]["name"], "John Smith")
        self.assertEqual(body["property"]["name"], "Hotel KL")
        opportunity_id = body["id"]

        listing = self.client.get("/api/pipeline/").json()
        self.assertEqual(listing["count"], 1)
        self.assertEqual([item["id"] for item in listing["stages"]], list(PIPELINE_STAGE_ORDER))
        self.assertEqual(listing["stage_counts"]["new"], 1)

        detail = self.client.get(f"/api/pipeline/{opportunity_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["title"], "Weekend booking")

        updated = self.client.patch(
            f"/api/pipeline/{opportunity_id}/",
            data={"title": "Weekend hotel booking", "stage": "quoted"},
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["title"], "Weekend hotel booking")
        self.assertEqual(updated.json()["stage"], "quoted")

        filtered = self.client.get("/api/pipeline/", {"stage": "quoted"}).json()
        self.assertEqual(filtered["count"], 1)
        empty = self.client.get("/api/pipeline/", {"stage": "won"}).json()
        self.assertEqual(empty["count"], 0)

        deleted = self.client.delete(f"/api/pipeline/{opportunity_id}/")
        self.assertEqual(deleted.status_code, 403)

        self.client.post("/api/auth/logout/")
        self._login("root")
        deleted = self.client.delete(f"/api/pipeline/{opportunity_id}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get(f"/api/pipeline/{opportunity_id}/").status_code, 404)

    def test_stage_update_persists_and_rejects_invalid_values(self):
        self._login("staff.global")
        opportunity_id = self._create(
            customer_id=self.cairo_customer.pk,
            property_id=self.cairo.pk,
            title="Family room enquiry",
        ).json()["id"]

        moved = self.client.patch(
            f"/api/pipeline/{opportunity_id}/stage/",
            data={"stage": "qualified"},
            content_type="application/json",
        )
        self.assertEqual(moved.status_code, 200)
        self.assertEqual(moved.json()["stage"], "qualified")
        self.assertEqual(Case.objects.get(pk=opportunity_id).stage, PipelineStage.QUALIFIED)

        invalid = self.client.patch(
            f"/api/pipeline/{opportunity_id}/stage/",
            data={"stage": "closed_won"},
            content_type="application/json",
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(Case.objects.get(pk=opportunity_id).stage, PipelineStage.QUALIFIED)

        for stage in PIPELINE_STAGE_ORDER:
            response = self.client.patch(
                f"/api/pipeline/{opportunity_id}/stage/",
                data={"stage": stage},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, stage)
            self.assertEqual(Case.objects.get(pk=opportunity_id).stage, stage)

    def test_property_permissions(self):
        self._login("staff.global")
        cairo = self._create(
            customer_id=self.cairo_customer.pk,
            property_id=self.cairo.pk,
            title="KL deal",
        ).json()
        alex = self._create(
            customer_id=self.alex_customer.pk,
            property_id=self.alex.pk,
            title="Alex deal",
        ).json()

        self.client.post("/api/auth/logout/")
        self._login("root")
        listing = self.client.get("/api/pipeline/").json()
        self.assertEqual(listing["count"], 2)

        self.client.post("/api/auth/logout/")
        self._login("staff.global")
        listing = self.client.get("/api/pipeline/").json()
        self.assertEqual(listing["count"], 2)

        self.client.post("/api/auth/logout/")
        self._login("staff.lee")
        listing = self.client.get("/api/pipeline/").json()
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["results"][0]["property"]["id"], self.cairo.pk)
        self.assertEqual(self.client.get(f"/api/pipeline/{alex['id']}/").status_code, 403)
        self.assertEqual(
            self.client.patch(
                f"/api/pipeline/{alex['id']}/stage/",
                data={"stage": "won"},
                content_type="application/json",
            ).status_code,
            403,
        )
        allowed = self.client.get(f"/api/pipeline/{cairo['id']}/")
        self.assertEqual(allowed.status_code, 200)

    def test_opportunities_alias_uses_the_same_pipeline_api(self):
        self._login("staff.global")
        created = self.client.post(
            "/api/opportunities/",
            data={"customer_id": self.cairo_customer.pk, "title": "Alias create"},
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        listing = self.client.get("/api/opportunities/").json()
        self.assertEqual(listing["resource"], "pipeline")
        self.assertEqual(listing["count"], 1)

    def test_assigned_staff_and_unassigned_are_serialized(self):
        self._login("staff.global")
        assigned = self._create(
            customer_id=self.cairo_customer.pk,
            property_id=self.cairo.pk,
            title="Assigned deal",
            assigned_to_id=self.cairo_staff.pk,
        )
        self.assertEqual(assigned.status_code, 201, assigned.content)
        self.assertEqual(assigned.json()["assigned_user"]["name"], "Aiman Rahman")
        self.assertEqual(assigned.json()["assigned_to"]["display_name"], "Aiman Rahman")

        unassigned = self._create(
            customer_id=self.cairo_customer.pk,
            property_id=self.cairo.pk,
            title="Unassigned deal",
        )
        self.assertEqual(unassigned.status_code, 201)
        self.assertIsNone(unassigned.json()["assigned_user"])
        self.assertIsNone(unassigned.json()["assigned_to"])

        listing = self.client.get("/api/pipeline/").json()
        by_title = {item["title"]: item for item in listing["results"]}
        self.assertEqual(by_title["Assigned deal"]["assigned_user"]["name"], "Aiman Rahman")
        self.assertIsNone(by_title["Unassigned deal"]["assigned_user"])

    def test_retrieve_includes_customer_request_and_conversation(self):
        conversation = self._conversation(
            self.cairo_customer,
            self.cairo,
            channel=Channel.WEBSITE,
            request_text="I need a family room for 3 nights from September 15.",
        )
        opportunity = make_case(
            customer=self.cairo_customer,
            property=self.cairo,
            originating_conversation=conversation,
            title="Family room",
            description="Fallback description should not hide the inbound request.",
            original_request="I need a family room for 3 nights from September 15.",
            source=Channel.WEBSITE,
            assigned_to=self.cairo_staff,
        )
        self._login("staff.global")
        listing = self.client.get("/api/pipeline/").json()
        card = next(item for item in listing["results"] if item["id"] == opportunity.pk)
        self.assertEqual(card["request"], "I need a family room for 3 nights from September 15.")
        self.assertEqual(card["source"], "website")
        self.assertEqual(card["source_label"], "Website")
        self.assertEqual(card["assigned_user"]["name"], "Aiman Rahman")
        self.assertNotIn("messages", card["conversation"])

        detail = self.client.get(f"/api/pipeline/{opportunity.pk}/")
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["customer"]["name"], "John Smith")
        self.assertEqual(body["customer"]["email"], "john@example.com")
        self.assertEqual(body["request"], "I need a family room for 3 nights from September 15.")
        self.assertEqual(body["source_label"], "Website")
        self.assertEqual(len(body["conversation"]["messages"]), 3)
        self.assertEqual(body["conversation"]["messages"][0]["sender_type"], "customer")
        self.assertEqual(body["conversation"]["messages"][1]["sender_type"], "bot")

        noted = self.client.patch(
            f"/api/pipeline/{opportunity.pk}/",
            data={"staff_notes": "Called the guest about weekend dates."},
            content_type="application/json",
        )
        self.assertEqual(noted.status_code, 200)
        self.assertEqual(noted.json()["staff_notes"], "Called the guest about weekend dates.")
        self.assertEqual(Case.objects.get(pk=opportunity.pk).staff_notes, "Called the guest about weekend dates.")

    def test_workflow_actions_and_invalid_transitions(self):
        self._login("staff.global")
        opportunity_id = self._create(
            customer_id=self.cairo_customer.pk,
            property_id=self.cairo.pk,
            title="Workflow deal",
            value="1500.00",
        ).json()["id"]

        invalid = self.client.post(
            f"/api/pipeline/{opportunity_id}/actions/",
            data={"action": "approve"},
            content_type="application/json",
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["code"], "invalid_transition")
        self.assertEqual(Case.objects.get(pk=opportunity_id).stage, PipelineStage.NEW)

        qualified = self.client.post(
            f"/api/pipeline/{opportunity_id}/actions/",
            data={"action": "qualify"},
            content_type="application/json",
        )
        self.assertEqual(qualified.status_code, 200)
        self.assertEqual(qualified.json()["stage"], "qualified")
        self.assertEqual(qualified.json()["allowed_actions"], ["quote"])

        still_invalid = self.client.post(
            f"/api/pipeline/{opportunity_id}/actions/",
            data={"action": "approve"},
            content_type="application/json",
        )
        self.assertEqual(still_invalid.status_code, 400)

        quoted = self.client.post(
            f"/api/pipeline/{opportunity_id}/actions/",
            data={"action": "quote", "value": "4500.00", "notes": "Family room rate"},
            content_type="application/json",
        )
        self.assertEqual(quoted.status_code, 200)
        self.assertEqual(quoted.json()["stage"], "quoted")
        self.assertEqual(quoted.json()["value"], "4500.00")
        self.assertEqual(quoted.json()["quote_notes"], "Family room rate")
        self.assertEqual(quoted.json()["allowed_actions"], ["approve"])

        approved = self.client.post(
            f"/api/pipeline/{opportunity_id}/actions/",
            data={"action": "approve"},
            content_type="application/json",
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["stage"], "negotiating")
        self.assertIn("approve", approved.json()["allowed_actions"])
        self.assertIn("move_to_finance", approved.json()["allowed_actions"])

        finance = self.client.post(
            f"/api/pipeline/{opportunity_id}/actions/",
            data={"action": "move_to_finance"},
            content_type="application/json",
        )
        self.assertEqual(finance.status_code, 200)
        self.assertEqual(finance.json()["stage"], "negotiating")
        self.assertEqual(finance.json()["finance_status"], FinanceStatus.SENT)
        self.assertNotIn("move_to_finance", finance.json()["allowed_actions"])

        won = self.client.post(
            f"/api/pipeline/{opportunity_id}/actions/",
            data={"action": "approve"},
            content_type="application/json",
        )
        self.assertEqual(won.status_code, 200)
        self.assertEqual(won.json()["stage"], "won")
        persisted = Case.objects.get(pk=opportunity_id)
        self.assertEqual(persisted.stage, PipelineStage.WON)
        self.assertEqual(persisted.finance_status, FinanceStatus.SENT)

    def test_unauthorized_staff_cannot_act_on_foreign_opportunity(self):
        self._login("staff.global")
        alex_id = self._create(
            customer_id=self.alex_customer.pk,
            property_id=self.alex.pk,
            title="Alex workflow",
        ).json()["id"]

        self.client.post("/api/auth/logout/")
        self._login("staff.lee")
        self.assertEqual(self.client.get(f"/api/pipeline/{alex_id}/").status_code, 403)
        forbidden = self.client.post(
            f"/api/pipeline/{alex_id}/actions/",
            data={"action": "qualify"},
            content_type="application/json",
        )
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(Case.objects.get(pk=alex_id).stage, PipelineStage.NEW)
