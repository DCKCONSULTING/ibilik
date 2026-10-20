from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def remap_legacy_status(apps, schema_editor):
    Location = apps.get_model("locations", "Location")
    Location.objects.filter(status="occupied").update(status="available")
    Location.objects.filter(status="reserved").update(status="available")


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0005_role"),
        ("locations", "0003_property_location_hotel_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="location",
            name="status",
            field=models.CharField(
                choices=[
                    ("available", "Available"),
                    ("dirty", "Dirty"),
                    ("cleaning", "Cleaning"),
                    ("maintenance", "Maintenance"),
                    ("out_of_order", "Out of order"),
                    ("inspection", "Inspection"),
                    ("inactive", "Inactive"),
                ],
                default="available",
                max_length=16,
            ),
        ),
        migrations.RunPython(remap_legacy_status, migrations.RunPython.noop),
        migrations.CreateModel(
            name="LocationStatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("previous_status", models.CharField(blank=True, default="", max_length=16)),
                ("new_status", models.CharField(max_length=16)),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="location_status_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_history",
                        to="locations.location",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="CleaningTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[("in_progress", "In progress"), ("completed", "Completed"), ("cancelled", "Cancelled")],
                        default="in_progress",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assigned_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assigned_cleaning_tasks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_cleaning_tasks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cleaning_tasks",
                        to="locations.location",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="MaintenanceIssue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "priority",
                    models.CharField(
                        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("urgent", "Urgent")],
                        default="medium",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("in_progress", "In progress"),
                            ("resolved", "Resolved"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="open",
                        max_length=16,
                    ),
                ),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("expected_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assigned_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assigned_maintenance_issues",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_maintenance_issues",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="maintenance_issues",
                        to="locations.location",
                    ),
                ),
                (
                    "property",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="maintenance_issues",
                        to="accounts.property",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
