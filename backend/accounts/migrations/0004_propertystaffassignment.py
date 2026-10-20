from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def copy_existing_staff_assignments(apps, schema_editor):
    Property = apps.get_model("accounts", "Property")
    Assignment = apps.get_model("accounts", "PropertyStaffAssignment")
    Through = Property.staff.through
    User = apps.get_model(settings.AUTH_USER_MODEL)

    group_roles = {"Manager": "MANAGER", "Staff": "STAFF"}
    users = {user.pk: user for user in User.objects.all().prefetch_related("groups")}

    for row in Through.objects.all():
        user = users.get(row.user_id)
        role = "STAFF"
        if user is not None:
            if user.is_superuser:
                role = "SUPERUSER"
            else:
                for name in user.groups.values_list("name", flat=True):
                    if name in group_roles:
                        role = group_roles[name]
                        break
        Assignment.objects.get_or_create(
            property_id=row.property_id,
            user_id=row.user_id,
            defaults={"role": role, "is_active": True},
        )


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_property_location_hotel_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PropertyStaffAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(blank=True, default="", max_length=32)),
                ("is_active", models.BooleanField(default=True)),
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                (
                    "assigned_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="property_staff_assigned",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "property",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="staff_assignments",
                        to="accounts.property",
                    ),
                ),
                (
                    "reports_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="property_direct_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="property_staff_assignments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "property staff assignment",
                "verbose_name_plural": "property staff assignments",
                "ordering": ["user__first_name", "user__last_name", "user__username", "id"],
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="propertystaffassignment",
            constraint=models.UniqueConstraint(fields=("property", "user"), name="uniq_property_staff_assignment"),
        ),
        migrations.RunPython(copy_existing_staff_assignments, noop_reverse),
    ]
