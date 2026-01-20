from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_product_stock_control_mode"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="reorder_level",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
