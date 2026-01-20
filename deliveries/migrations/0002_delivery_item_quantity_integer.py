from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("deliveries", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="deliveryguideitem",
            name="quantity",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
