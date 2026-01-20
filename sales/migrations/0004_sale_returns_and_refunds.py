from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0003_sale_payment_and_cancel_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="saleitem",
            name="returned_quantity",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=12),
        ),
        migrations.CreateModel(
            name="SaleRefund",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("return_type", models.CharField(choices=[("none", "Sem devolucao"), ("partial", "Devolucao parcial"), ("total", "Devolucao total")], default="none", max_length=10)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("status", models.CharField(choices=[("refunded", "Estornado")], default="refunded", max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sale_refunds", to="tenants.business")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sale_refunds", to=settings.AUTH_USER_MODEL)),
                ("sale", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="refunds", to="sales.sale")),
            ],
        ),
    ]
