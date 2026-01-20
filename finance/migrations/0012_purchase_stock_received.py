from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0011_purchase_payment_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchase",
            name="stock_received",
            field=models.BooleanField(default=False),
        ),
    ]
