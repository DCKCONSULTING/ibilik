from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("locations", "0001_location_resource"),
    ]

    operations = [
        migrations.AlterField(
            model_name="location",
            name="location_type",
            field=models.CharField(
                choices=[
                    ("room", "Room"),
                    ("table", "Table"),
                    ("meeting_room", "Meeting Room"),
                    ("villa", "Villa"),
                    ("apartment", "Apartment"),
                    ("suite", "Suite"),
                    ("parking", "Parking"),
                    ("desk", "Desk"),
                    ("other", "Other"),
                ],
                default="room",
                max_length=32,
            ),
        ),
    ]
