from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0002_sale_discount_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="payment_method",
            field=models.CharField(blank=True, choices=[("cash", "Dinheiro"), ("card", "Cartao"), ("bank_transfer", "Transferencia"), ("other", "Outro")], max_length=20),
        ),
        migrations.AddField(
            model_name="sale",
            name="payment_due_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sale",
            name="has_down_payment",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="sale",
            name="down_payment_type",
            field=models.CharField(choices=[("none", "Sem entrada"), ("fixed", "Valor fixo"), ("percent", "Percentagem")], default="none", max_length=10),
        ),
        migrations.AddField(
            model_name="sale",
            name="down_payment_value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="sale",
            name="down_payment_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="sale",
            name="canceled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sale",
            name="canceled_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="canceled_sales", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="sale",
            name="cancel_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="sale",
            name="return_type",
            field=models.CharField(choices=[("none", "Sem devolucao"), ("partial", "Devolucao parcial"), ("total", "Devolucao total")], default="none", max_length=10),
        ),
    ]
