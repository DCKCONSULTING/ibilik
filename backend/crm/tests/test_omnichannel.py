import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from accounts.catalog import ROLE_STAFF
from accounts.models import Property, UserPropertyAccess
from accounts.services import create_user, initialize_access_control
from crm.models import Channel, Conversation, Customer, Message, SenderType
from crm.security import sign_payload


INGEST_KEY = "test-ingest-key"
WA_SECRET = "wa-app-secret"
FB_SECRET = "fb-app-secret"


@override_settings(
    WEBSITE_INGEST_API_KEY=INGEST_KEY,
    WHATSAPP_INGEST_API_KEY=INGEST_KEY,
    FACEBOOK_INGEST_API_KEY=INGEST_KEY,
    WHATSAPP_APP_SECRET=WA_SECRET,
    WHATSAPP_VERIFY_TOKEN="wa-verify",
    WHATSAPP_PROVIDER="test",
    FACEBOOK_APP_SECRET=FB_SECRET,
    FACEBOOK_VERIFY_TOKEN="fb-verify",
    FACEBOOK_PROVIDER="test",
)
class OmnichannelTests(TestCase):
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
        self.cairo = Property.objects.create(name="Hotel KL", region="Kuala Lumpur", city="Kuala Lumpur", rate="150.00")
        self.alex = Property.objects.create(name="Hotel Penang", region="Penang", city="George Town", rate="120.00")
        self.cairo.staff.add(self.assigned_staff)
        self.alex.staff.add(self.other_staff)

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

    def _ingest_website(self, payload, expected=201):
        response = self.client.post(
            "/api/integrations/website/messages/",
            data=payload,
            content_type="application/json",
            headers={"X-API-Key": INGEST_KEY},
        )
        self.assertEqual(response.status_code, expected, response.content)
        return response.json()

    def _signed_post(self, path, payload, secret):
        body = json.dumps(payload).encode("utf-8")
        return self.client.generic(
            "POST",
            path,
            data=body,
            content_type="application/json",
            headers={"X-Hub-Signature-256": sign_payload(body, secret)},
        )

    def test_website_valid_submission_creates_customer_conversation_and_message(self):
        payload = self._ingest_website(
            {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "+201001234567",
                "message": "I want to know the room rate.",
                "source": "website",
                "source_reference": "website-form",
                "external_id": "form-submission-123",
                "property_id": self.cairo.pk,
            }
        )
        self.assertEqual(payload["customer"]["name"], "John Smith")
        self.assertEqual(payload["customer"]["email"], "john@example.com")
        self.assertEqual(payload["customer"]["phone"], "+201001234567")
        self.assertEqual(payload["conversation"]["channel"], "website")
        self.assertEqual(payload["conversation"]["property"]["id"], self.cairo.pk)
        self.assertEqual(payload["message"]["content"], "I want to know the room rate.")
        self.assertEqual(payload["message"]["direction"], "inbound")
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 1)

    def test_website_matches_existing_customer_by_email_and_phone(self):
        self._ingest_website(
            {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "+201001234567",
                "message": "First enquiry",
                "external_id": "web-1",
            }
        )
        self._ingest_website(
            {
                "name": "John",
                "email": "john@example.com",
                "phone": "201001234567",
                "message": "Second enquiry",
                "external_id": "web-2",
            }
        )
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Conversation.objects.filter(channel="website").count(), 1)
        self.assertEqual(Message.objects.count(), 2)

    def test_website_duplicate_submission_is_idempotent(self):
        first = self._ingest_website(
            {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "+201001234567",
                "message": "I need a room",
                "external_id": "web-123",
            }
        )
        second = self._ingest_website(
            {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "+201001234567",
                "message": "I need a room",
                "external_id": "web-123",
            },
            expected=200,
        )
        self.assertTrue(second["deduplicated"])
        self.assertEqual(first["message"]["id"], second["message"]["id"])
        self.assertEqual(Message.objects.count(), 1)

    def test_website_rejects_missing_api_key(self):
        response = self.client.post(
            "/api/integrations/website/messages/",
            data={"name": "A", "email": "a@example.com", "message": "Hi"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_whatsapp_webhook_and_customer_matching(self):
        self._ingest_website(
            {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "+201001234567",
                "message": "Website first",
                "external_id": "web-john",
            }
        )
        response = self._signed_post(
            "/api/integrations/whatsapp/webhook/",
            {
                "object": "whatsapp_business_account",
                "entry": [
                    {
                        "id": "entry-1",
                        "changes": [
                            {
                                "value": {
                                    "contacts": [{"profile": {"name": "John Smith"}, "wa_id": "201001234567"}],
                                    "messages": [
                                        {
                                            "id": "wamid.1",
                                            "from": "201001234567",
                                            "timestamp": "1710000000",
                                            "type": "text",
                                            "text": {"body": "Hello, I need more information."},
                                        }
                                    ],
                                }
                            }
                        ],
                    }
                ],
            },
            WA_SECRET,
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Conversation.objects.filter(channel="whatsapp").count(), 1)
        self.assertEqual(Message.objects.filter(channel="whatsapp").count(), 1)

    def test_whatsapp_duplicate_webhook_is_idempotent(self):
        payload = {
            "from": "+201001234567",
            "name": "John Smith",
            "content": "Hello",
            "external_message_id": "wamid.dup",
        }
        first = self._signed_post("/api/integrations/whatsapp/webhook/", payload, WA_SECRET)
        second = self._signed_post("/api/integrations/whatsapp/webhook/", payload, WA_SECRET)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Message.objects.count(), 1)

    def test_whatsapp_unsigned_webhook_rejected(self):
        response = self.client.post(
            "/api/integrations/whatsapp/webhook/",
            data={"from": "+201001234567", "content": "Hello", "external_message_id": "wamid.x"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_whatsapp_verify_token(self):
        ok = self.client.get(
            "/api/integrations/whatsapp/webhook/",
            {"hub.mode": "subscribe", "hub.verify_token": "wa-verify", "hub.challenge": "challenge-token"},
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.content.decode(), "challenge-token")
        bad = self.client.get(
            "/api/integrations/whatsapp/webhook/",
            {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "x"},
        )
        self.assertEqual(bad.status_code, 403)

    def test_whatsapp_historical_messages_include_bot(self):
        for index, (sender_type, content) in enumerate(
            [
                (SenderType.BOT, "Hello, how can I help?"),
                (SenderType.CUSTOMER, "I need the rate for Friday."),
                (SenderType.BOT, "The rate is 150."),
                (SenderType.CUSTOMER, "Can I book it?"),
            ],
            start=1,
        ):
            response = self.client.post(
                "/api/integrations/whatsapp/messages/",
                data={
                    "from": "+201001234567",
                    "name": "John Smith",
                    "content": content,
                    "sender_type": sender_type,
                    "external_message_id": f"wamid.hist-{index}",
                    "external_conversation_id": "wa-john",
                },
                content_type="application/json",
                headers={"X-API-Key": INGEST_KEY},
            )
            self.assertEqual(response.status_code, 201, response.content)

        self._login("staff.global")
        conversation_id = Conversation.objects.get(channel="whatsapp").pk
        history = self.client.get(f"/api/conversations/{conversation_id}/messages/").json()
        self.assertEqual(history["count"], 4)
        self.assertEqual([item["sender_type"] for item in history["results"]], ["bot", "customer", "bot", "customer"])

    def test_facebook_webhook_and_duplicate(self):
        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page-1",
                    "messaging": [
                        {
                            "sender": {"id": "psid-1"},
                            "recipient": {"id": "page-1"},
                            "timestamp": 1710000000000,
                            "message": {"mid": "mid.1", "text": "Is this hotel available next weekend?"},
                        }
                    ],
                }
            ],
        }
        first = self._signed_post("/api/integrations/facebook/webhook/", payload, FB_SECRET)
        second = self._signed_post("/api/integrations/facebook/webhook/", payload, FB_SECRET)
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 1)

    def test_facebook_matches_known_phone_identity(self):
        self._ingest_website(
            {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "+201001234567",
                "message": "Website first",
                "external_id": "web-fb",
            }
        )
        response = self.client.post(
            "/api/integrations/facebook/messages/",
            data={
                "sender_id": "psid-john",
                "name": "John Smith",
                "phone": "+201001234567",
                "content": "Facebook follow up",
                "external_message_id": "mid.john",
            },
            content_type="application/json",
            headers={"X-API-Key": INGEST_KEY},
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Customer.objects.count(), 1)
        customer = Customer.objects.get()
        self.assertTrue(customer.identities.filter(channel="facebook", identifier="psid-john").exists())
        self.assertTrue(customer.identities.filter(channel="whatsapp").exists() is False)

    def test_three_channels_resolve_to_one_customer(self):
        self._ingest_website(
            {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "+201001234567",
                "message": "I need a room",
                "external_id": "web-match",
            }
        )
        self.client.post(
            "/api/integrations/whatsapp/messages/",
            data={"from": "+201001234567", "content": "WhatsApp hello", "external_message_id": "wamid.match"},
            content_type="application/json",
            headers={"X-API-Key": INGEST_KEY},
        )
        self.client.post(
            "/api/integrations/facebook/messages/",
            data={
                "sender_id": "psid-match",
                "phone": "+201001234567",
                "content": "Facebook hello",
                "external_message_id": "mid.match",
            },
            content_type="application/json",
            headers={"X-API-Key": INGEST_KEY},
        )
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Conversation.objects.count(), 3)

    def test_superuser_and_global_user_see_all_conversations(self):
        self._ingest_website(
            {
                "name": "KL Guest",
                "phone": "+201111111111",
                "message": "Kuala Lumpur",
                "external_id": "cairo-1",
                "property_id": self.cairo.pk,
            }
        )
        self._ingest_website(
            {
                "name": "Alex Guest",
                "phone": "+202222222222",
                "message": "Alex",
                "external_id": "alex-1",
                "property_id": self.alex.pk,
            }
        )
        self._login("root")
        listing = self.client.get("/api/conversations/").json()
        self.assertEqual(listing["count"], 2)

        self.client.post("/api/auth/logout/")
        self._login("staff.global")
        listing = self.client.get("/api/conversations/").json()
        self.assertEqual(listing["count"], 2)

    def test_assigned_user_sees_only_assigned_property_conversations(self):
        cairo = self._ingest_website(
            {
                "name": "KL Guest",
                "phone": "+201111111111",
                "message": "Kuala Lumpur",
                "external_id": "cairo-2",
                "property_id": self.cairo.pk,
            }
        )
        alex = self._ingest_website(
            {
                "name": "Alex Guest",
                "phone": "+202222222222",
                "message": "Alex",
                "external_id": "alex-2",
                "property_id": self.alex.pk,
            }
        )
        self._login("staff.lee")
        listing = self.client.get("/api/conversations/").json()
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["results"][0]["property"]["id"], self.cairo.pk)

        blocked = self.client.get(f"/api/conversations/{alex['conversation']['id']}/")
        self.assertEqual(blocked.status_code, 403)
        blocked_messages = self.client.get(f"/api/conversations/{alex['conversation']['id']}/messages/")
        self.assertEqual(blocked_messages.status_code, 403)

        allowed = self.client.get(f"/api/conversations/{cairo['conversation']['id']}/")
        self.assertEqual(allowed.status_code, 200)

    def test_unassigned_conversation_is_hidden_from_assigned_users(self):
        payload = self._ingest_website(
            {
                "name": "No Property",
                "email": "noprop@example.com",
                "message": "Hello",
                "external_id": "nop-1",
            }
        )
        self._login("staff.lee")
        listing = self.client.get("/api/conversations/").json()
        self.assertEqual(listing["count"], 0)
        self.assertEqual(self.client.get(f"/api/conversations/{payload['conversation']['id']}/").status_code, 403)

    def test_authorized_user_can_send_cross_channel_reply(self):
        ingested = self._ingest_website(
            {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "+201001234567",
                "message": "I want to know your rate.",
                "external_id": "web-reply",
                "property_id": self.cairo.pk,
            }
        )
        self._login("staff.global")
        conversation_id = ingested["conversation"]["id"]
        response = self.client.post(
            f"/api/conversations/{conversation_id}/messages/",
            data={"content": "Our current rate is 150.", "channel": "whatsapp"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["channel"], "whatsapp")
        self.assertEqual(body["direction"], "outbound")
        self.assertEqual(body["sender_type"], "staff")
        conversation = Conversation.objects.get(pk=conversation_id)
        self.assertEqual(conversation.channel, "website")
        self.assertEqual(conversation.customer_id, ingested["customer"]["id"])

    def test_unauthorized_user_cannot_reply(self):
        ingested = self._ingest_website(
            {
                "name": "Alex Guest",
                "phone": "+202222222222",
                "message": "Alex",
                "external_id": "alex-reply",
                "property_id": self.alex.pk,
            }
        )
        self._login("staff.lee")
        response = self.client.post(
            f"/api/conversations/{ingested['conversation']['id']}/messages/",
            data={"content": "Hello", "channel": "whatsapp"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_and_unavailable_reply_channels_rejected(self):
        ingested = self._ingest_website(
            {
                "name": "Email Only",
                "email": "email.only@example.com",
                "message": "Hello",
                "external_id": "email-only",
                "property_id": self.cairo.pk,
            }
        )
        self._login("staff.global")
        conversation_id = ingested["conversation"]["id"]
        unknown = self.client.post(
            f"/api/conversations/{conversation_id}/messages/",
            data={"content": "Hello", "channel": "telegram"},
            content_type="application/json",
        )
        self.assertEqual(unknown.status_code, 400)
        website = self.client.post(
            f"/api/conversations/{conversation_id}/messages/",
            data={"content": "Hello", "channel": "website"},
            content_type="application/json",
        )
        self.assertEqual(website.status_code, 403)
        whatsapp = self.client.post(
            f"/api/conversations/{conversation_id}/messages/",
            data={"content": "Hello", "channel": "whatsapp"},
            content_type="application/json",
        )
        self.assertEqual(whatsapp.status_code, 403)
        facebook = self.client.post(
            f"/api/conversations/{conversation_id}/messages/",
            data={"content": "Hello", "channel": "facebook"},
            content_type="application/json",
        )
        self.assertEqual(facebook.status_code, 403)

    def test_staff_without_send_permission_blocked(self):
        ingested = self._ingest_website(
            {
                "name": "John Smith",
                "phone": "+201001234567",
                "message": "Hi",
                "external_id": "perm-1",
                "property_id": self.cairo.pk,
            }
        )
        from accounts.services import assign_limited_permissions

        limited = create_user(
            username="staff.limited",
            password="staff-pass-123",
            role=ROLE_STAFF,
            actor=self.superuser,
        )
        assign_limited_permissions(
            limited,
            ["inbox.view_inbox", "customers.view_customer"],
            actor=self.superuser,
        )
        self.cairo.staff.add(limited)
        self._login("staff.limited")
        response = self.client.post(
            f"/api/conversations/{ingested['conversation']['id']}/messages/",
            data={"content": "Hello", "channel": "whatsapp"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_create_and_list_search(self):
        self._login("staff.global")
        created = self.client.post(
            "/api/customers/",
            data={"name": "Ada Lovelace", "email": "ada@example.com", "phone": "+201009998887", "status": "lead"},
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        listing = self.client.get("/api/customers/", {"search": "Ada"})
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)
        self.assertEqual(listing.json()["results"][0]["email"], "ada@example.com")

    def test_conversation_channel_filter_and_search(self):
        self._ingest_website(
            {
                "name": "John Smith",
                "phone": "+201001234567",
                "message": "Website note",
                "external_id": "filter-web",
                "property_id": self.cairo.pk,
            }
        )
        self.client.post(
            "/api/integrations/whatsapp/messages/",
            data={"from": "+201001234567", "content": "WhatsApp note", "external_message_id": "wamid.filter"},
            content_type="application/json",
            headers={"X-API-Key": INGEST_KEY},
        )
        self._login("staff.global")
        whatsapp = self.client.get("/api/conversations/", {"channel": "whatsapp"}).json()
        self.assertEqual(whatsapp["count"], 1)
        self.assertEqual(whatsapp["results"][0]["channel"], "whatsapp")
        search = self.client.get("/api/conversations/", {"search": "Website note"}).json()
        self.assertEqual(search["count"], 1)

    def test_conversation_list_returns_latest_message_fields(self):
        first = self._ingest_website(
            {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "+201001234567",
                "message": "First question",
                "external_id": "latest-first",
                "property_id": self.cairo.pk,
            }
        )
        second = self._ingest_website(
            {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "+201001234567",
                "message": "I need the room rate.",
                "external_id": "latest-second",
                "property_id": self.cairo.pk,
            }
        )
        self.assertEqual(first["conversation"]["id"], second["conversation"]["id"])
        conversation = Conversation.objects.get(pk=second["conversation"]["id"])
        latest_message = conversation.messages.order_by("-created_at", "-id").first()
        first_message = conversation.messages.order_by("created_at", "id").first()
        self.assertIsNotNone(latest_message)
        self.assertEqual(latest_message.content, "I need the room rate.")
        self.assertEqual(conversation.last_message_preview, "I need the room rate.")

        self._login("staff.global")
        listing = self.client.get("/api/conversations/").json()
        self.assertEqual(listing["count"], 1)
        item = listing["results"][0]
        self.assertEqual(item["id"], conversation.pk)
        self.assertEqual(item["customer"]["name"], "John Smith")
        self.assertEqual(item["channel"], "website")
        self.assertEqual(item["last_message_preview"], conversation.last_message_preview)
        self.assertEqual(item["last_message"]["content"], conversation.last_message_preview)
        self.assertEqual(item["last_message_at"], conversation.last_message_at.isoformat())
        self.assertEqual(item["last_message"]["created_at"], item["last_message_at"])
        self.assertNotEqual(item["last_message_preview"], first_message.content)
        self.assertGreaterEqual(conversation.last_message_at, first_message.created_at)

    def test_raw_event_does_not_store_secrets(self):
        self._ingest_website(
            {
                "name": "John Smith",
                "email": "john@example.com",
                "message": "Hi",
                "external_id": "secret-1",
                "access_token": "super-secret-token",
                "password": "hunter2",
            }
        )
        raw = Message.objects.get().raw_event
        self.assertEqual(raw["access_token"], "[redacted]")
        self.assertEqual(raw["password"], "[redacted]")
        self.assertNotIn("super-secret-token", json.dumps(raw))
