from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0005_location_resource"),
    ]

    operations = [
        migrations.AddField(
            model_name="case",
            name="actual_check_in",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="case",
            name="actual_check_out",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
