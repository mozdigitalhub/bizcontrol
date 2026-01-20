from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0010_backfill_purchase_codes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="purchase",
            name="due_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="purchase",
            name="payment_status",
            field=models.CharField(
                choices=[
                    ("unpaid", "Em aberto"),
                    ("partial", "Parcial"),
                    ("paid", "Pago"),
                ],
                default="unpaid",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="purchase",
            name="amount_paid",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.CreateModel(
            name="PurchasePayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("method", models.CharField(choices=[("cash", "Numerario"), ("card", "Cartao"), ("bank_transfer", "Transferencia"), ("cheque", "Cheque"), ("mpesa", "MPesa"), ("emola", "Emola"), ("mkesh", "MKesh"), ("other", "Outro")], max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("paid_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("business", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="purchase_payments", to="tenants.business")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="purchase_payments", to=settings.AUTH_USER_MODEL)),
                ("purchase", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="payments", to="finance.purchase")),
            ],
            options={
                "indexes": [models.Index(fields=["business", "paid_at"], name="finance_purc_busines_6db6f9_idx")],
            },
        ),
    ]
