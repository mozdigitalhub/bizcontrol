from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="stock_control_mode",
            field=models.CharField(
                choices=[("automatic", "Automatico"), ("manual", "Manual")],
                default="automatic",
                max_length=20,
            ),
        ),
    ]
