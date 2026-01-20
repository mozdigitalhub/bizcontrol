from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0003_delete_customer_payment_methods"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="customer_type",
            field=models.CharField(
                choices=[("individual", "Particular"), ("company", "Empresa")],
                default="individual",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="nuit",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AlterField(
            model_name="customer",
            name="phone",
            field=models.CharField(max_length=30),
        ),
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.UniqueConstraint(
                condition=~Q(phone=""),
                fields=("business", "phone"),
                name="uniq_customer_phone_business",
            ),
        ),
    ]
