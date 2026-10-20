import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0001_initial"),
        ("pipeline", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="opportunity",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="opportunity",
            name="conversation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="opportunities",
                to="crm.conversation",
            ),
        ),
        migrations.AddField(
            model_name="opportunity",
            name="finance_moved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="opportunity",
            name="finance_status",
            field=models.CharField(
                choices=[("none", "Not sent"), ("sent", "Sent to finance")],
                default="none",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="opportunity",
            name="quote_notes",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="opportunity",
            name="quoted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
