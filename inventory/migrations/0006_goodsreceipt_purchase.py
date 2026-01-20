from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0011_purchase_payment_status"),
        ("inventory", "0005_stock_quantities_integer"),
    ]

    operations = [
        migrations.AddField(
            model_name="goodsreceipt",
            name="purchase",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="receipts",
                to="finance.purchase",
            ),
        ),
    ]
