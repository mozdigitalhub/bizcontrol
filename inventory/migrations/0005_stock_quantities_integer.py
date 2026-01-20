from django.db import migrations, models
from django.core.validators import MinValueValidator


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0004_rename_inventory_g_busines_18f4f2_idx_inventory_g_busines_1964a9_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stockmovement",
            name="quantity",
            field=models.PositiveIntegerField(validators=[MinValueValidator(1)]),
        ),
        migrations.AlterField(
            model_name="goodsreceiptitem",
            name="quantity",
            field=models.PositiveIntegerField(validators=[MinValueValidator(1)]),
        ),
    ]
