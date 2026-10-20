from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quotes", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="quote",
            name="currency",
            field=models.CharField(default="MYR", max_length=8),
        ),
    ]
