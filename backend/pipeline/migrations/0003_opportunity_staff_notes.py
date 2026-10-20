from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pipeline", "0002_opportunity_workflow_and_conversation"),
    ]

    operations = [
        migrations.AddField(
            model_name="opportunity",
            name="staff_notes",
            field=models.TextField(blank=True, default=""),
        ),
    ]
