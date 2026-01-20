from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("deliveries", "0003_deliveryguide_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="deliveryguide",
            name="expected_delivery_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="deliveryguide",
            name="transport_cost",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="deliveryguide",
            name="transport_responsible",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
