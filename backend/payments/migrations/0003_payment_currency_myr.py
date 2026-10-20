from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0002_copy_legacy_case_payments"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="currency",
            field=models.CharField(default="MYR", max_length=8),
        ),
    ]
