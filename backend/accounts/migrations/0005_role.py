from django.db import migrations, models
import django.db.models.deletion


def seed_builtin_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Group = apps.get_model("auth", "Group")

    defs = (
        {
            "code": "SUPERUSER",
            "name": "System Admin",
            "description": "System administrator. Full system access. Protected Django superuser.",
            "level": 0,
            "parent_code": None,
            "is_system_role": True,
            "all_properties": True,
            "can_manage_lower_users": True,
            "can_assign_property_staff": True,
            "group_name": None,
        },
        {
            "code": "TOP_MANAGER",
            "name": "Top Manager",
            "description": "All properties. Manage lower-level managers and staff.",
            "level": 1,
            "parent_code": "SUPERUSER",
            "is_system_role": False,
            "all_properties": True,
            "can_manage_lower_users": True,
            "can_assign_property_staff": True,
            "group_name": "Top Manager",
        },
        {
            "code": "MANAGER",
            "name": "Manager",
            "description": "Assigned properties. Manage staff within permitted scope.",
            "level": 2,
            "parent_code": "TOP_MANAGER",
            "is_system_role": False,
            "all_properties": False,
            "can_manage_lower_users": True,
            "can_assign_property_staff": True,
            "group_name": "Manager",
        },
        {
            "code": "STAFF",
            "name": "Staff",
            "description": "Assigned properties. Limited CRM access.",
            "level": 3,
            "parent_code": "MANAGER",
            "is_system_role": False,
            "all_properties": False,
            "can_manage_lower_users": False,
            "can_assign_property_staff": False,
            "group_name": "Staff",
        },
    )

    created = {}
    for item in defs:
        group = None
        if item["group_name"]:
            group, _ = Group.objects.get_or_create(name=item["group_name"])
        role, _ = Role.objects.get_or_create(
            code=item["code"],
            defaults={
                "name": item["name"],
                "description": item["description"],
                "level": item["level"],
                "is_system_role": item["is_system_role"],
                "is_builtin": True,
                "is_active": True,
                "all_properties": item["all_properties"],
                "can_manage_lower_users": item["can_manage_lower_users"],
                "can_assign_property_staff": item["can_assign_property_staff"],
                "group": group,
            },
        )
        created[item["code"]] = role

    for item in defs:
        role = created[item["code"]]
        parent_code = item["parent_code"]
        if parent_code and role.parent_id is None:
            role.parent = created[parent_code]
            role.save(update_fields=["parent"])


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_propertystaffassignment"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=64)),
                ("description", models.TextField(blank=True, default="")),
                ("level", models.PositiveSmallIntegerField()),
                ("is_system_role", models.BooleanField(default=False)),
                ("is_builtin", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("all_properties", models.BooleanField(default=False)),
                ("can_manage_lower_users", models.BooleanField(default=False)),
                ("can_assign_property_staff", models.BooleanField(default=False)),
                (
                    "group",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="crm_role",
                        to="auth.group",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="children",
                        to="accounts.role",
                    ),
                ),
            ],
            options={
                "verbose_name": "role",
                "verbose_name_plural": "roles",
                "ordering": ["level", "name", "id"],
                "default_permissions": (),
            },
        ),
        migrations.RunPython(seed_builtin_roles, noop_reverse),
    ]
