from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Property
from cases.models import Case
from crm.models import Conversation, Customer, Message
from locations.models import Location, LocationType
from pipeline.models import PipelineStage


class SeedDemoDataTests(TestCase):
    def test_seed_is_idempotent(self):
        call_command("seed_demo_data")
        customers = Customer.objects.count()
        conversations = Conversation.objects.count()
        messages = Message.objects.count()
        cases = Case.objects.count()

        call_command("seed_demo_data")

        self.assertEqual(Customer.objects.count(), customers)
        self.assertEqual(Conversation.objects.count(), conversations)
        self.assertEqual(Message.objects.count(), messages)
        self.assertEqual(Case.objects.count(), cases)
        self.assertGreaterEqual(customers, 8)
        self.assertGreaterEqual(Conversation.objects.filter(channel="whatsapp").count(), 5)
        self.assertGreaterEqual(Conversation.objects.filter(channel="facebook").count(), 3)
        self.assertGreaterEqual(Conversation.objects.filter(channel="website").count(), 3)
        self.assertGreaterEqual(Message.objects.filter(sender_type="bot").count(), 2)
        self.assertTrue(Conversation.objects.filter(property__isnull=True).exists())
        self.assertGreaterEqual(cases, 18)
        for stage in PipelineStage.values:
            self.assertGreaterEqual(Case.objects.filter(stage=stage).count(), 1, stage)
        self.assertTrue(Case.objects.filter(case_number__startswith="CASE-").exists())
        john_cases = Case.objects.filter(customer__email="john@example.com")
        self.assertGreaterEqual(john_cases.count(), 2)
        self.assertEqual(Property.objects.count(), 4)
        self.assertEqual(Location.objects.count(), 38)
        self.assertEqual(
            set(Property.objects.values_list("name", flat=True)),
            {
                "iBilik Kuala Lumpur City Centre",
                "iBilik Penang Heritage Hotel",
                "iBilik Langkawi Beach Resort",
                "iBilik Johor Bahru Business Hotel",
            },
        )
        self.assertFalse(Property.objects.filter(name__icontains="Cairo").exists())
        self.assertFalse(Property.objects.filter(name="gg").exists())
        self.assertTrue(Location.objects.filter(location_type=LocationType.ROOM).exists())
        self.assertTrue(Location.objects.filter(location_type=LocationType.TABLE).exists())
        self.assertTrue(Location.objects.filter(location_type=LocationType.MEETING_ROOM).exists())
        self.assertTrue(Location.objects.filter(location_type=LocationType.VILLA).exists())
        self.assertTrue(Location.objects.filter(location_type=LocationType.SUITE).exists())
        self.assertTrue(Case.objects.filter(location__isnull=False).exists())
        first_ids = list(Property.objects.order_by("id").values_list("id", "name"))
        first_location_ids = list(Location.objects.order_by("id").values_list("id", "code"))
        first_case_ids = list(Case.objects.order_by("id").values_list("id", "case_number"))

        call_command("seed_demo_data")
        self.assertEqual(list(Property.objects.order_by("id").values_list("id", "name")), first_ids)
        self.assertEqual(list(Location.objects.order_by("id").values_list("id", "code")), first_location_ids)
        self.assertEqual(list(Case.objects.order_by("id").values_list("id", "case_number")), first_case_ids)

        expected = {
            "iBilik Kuala Lumpur City Centre": ("Kuala Lumpur", "Kuala Lumpur", "hotel", "220.00", 12),
            "iBilik Penang Heritage Hotel": ("Penang", "George Town", "boutique_hotel", "180.00", 8),
            "iBilik Langkawi Beach Resort": ("Kedah", "Langkawi", "resort", "320.00", 10),
            "iBilik Johor Bahru Business Hotel": ("Johor", "Johor Bahru", "business_hotel", "160.00", 8),
        }
        for name, (region, city, property_type, rate, location_count) in expected.items():
            property_obj = Property.objects.get(name=name)
            self.assertEqual(property_obj.country, "Malaysia")
            self.assertEqual(property_obj.region, region)
            self.assertEqual(property_obj.city, city)
            self.assertEqual(property_obj.property_type, property_type)
            self.assertEqual(property_obj.currency, "MYR")
            self.assertEqual(property_obj.rate, Decimal(rate))
            self.assertEqual(property_obj.timezone, "Asia/Kuala_Lumpur")
            self.assertTrue(property_obj.address_line1)
            self.assertEqual(property_obj.locations.count(), location_count)
            self.assertTrue(property_obj.locations.filter(currency="MYR").exists())
            self.assertTrue(property_obj.locations.exclude(base_rate=None).exists())

        self.assertFalse(Property.objects.filter(name__icontains="Egypt").exists())
        self.assertFalse(Property.objects.filter(name__icontains="Alexandria").exists())
        self.assertFalse(Property.objects.filter(name__icontains="Hurghada").exists())
        self.assertFalse(Property.objects.filter(city__icontains="Cairo").exists())
