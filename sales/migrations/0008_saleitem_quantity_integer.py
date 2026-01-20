from django.db import migrations, models
from django.core.validators import MinValueValidator


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0007_alter_sale_payment_method"),
    ]

    operations = [
        migrations.AlterField(
            model_name="saleitem",
            name="quantity",
            field=models.PositiveIntegerField(validators=[MinValueValidator(1)]),
        ),
        migrations.AlterField(
            model_name="saleitem",
            name="returned_quantity",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
