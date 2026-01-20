from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0004_customer_profile_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="credit_limit",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
    ]
