from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenants", "0004_business_feature_flags"),
        ("catalog", "0002_product_stock_control_mode"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("address", models.TextField(blank=True)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="suppliers", to="tenants.business"),
                ),
            ],
            options={"unique_together": {("business", "name")}},
        ),
        migrations.CreateModel(
            name="ExpenseCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "business",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="expense_categories", to="tenants.business"),
                ),
            ],
            options={"unique_together": {("business", "name")}},
        ),
        migrations.CreateModel(
            name="CashMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "movement_type",
                    models.CharField(choices=[("IN", "Entrada"), ("OUT", "Saida")], max_length=10),
                ),
                ("amount", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=12)),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("cash", "Dinheiro"),
                            ("card", "Cartao"),
                            ("bank_transfer", "Transferencia"),
                            ("other", "Outro"),
                        ],
                        max_length=20,
                    ),
                ),
                ("reference_type", models.CharField(blank=True, max_length=30)),
                ("reference_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("happened_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "business",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cash_movements", to="tenants.business"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cash_movements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"indexes": [models.Index(fields=["business", "happened_at"], name="finance_cash_business_bf6f70_idx")]},
        ),
        migrations.CreateModel(
            name="Purchase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "purchase_type",
                    models.CharField(
                        choices=[("stock", "Reposicao de stock"), ("internal", "Uso interno")],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Rascunho"), ("confirmed", "Confirmada"), ("canceled", "Cancelada")],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("purchase_date", models.DateField()),
                (
                    "payment_method",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("cash", "Dinheiro"),
                            ("card", "Cartao"),
                            ("bank_transfer", "Transferencia"),
                            ("other", "Outro"),
                        ],
                        max_length=20,
                    ),
                ),
                ("internal_description", models.CharField(blank=True, max_length=255)),
                ("internal_amount", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=12)),
                ("subtotal", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=12)),
                ("total", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=12)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="purchases", to="tenants.business"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_purchases",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="purchases",
                        to="finance.supplier",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_purchases",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Expense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Rascunho"), ("paid", "Paga"), ("canceled", "Cancelada")],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("expense_date", models.DateField()),
                (
                    "payment_method",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("cash", "Dinheiro"),
                            ("card", "Cartao"),
                            ("bank_transfer", "Transferencia"),
                            ("other", "Outro"),
                        ],
                        max_length=20,
                    ),
                ),
                ("attachment", models.FileField(blank=True, null=True, upload_to="expense_receipts/")),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="expenses", to="tenants.business"),
                ),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="finance.expensecategory",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_expenses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_expenses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PurchaseItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.DecimalField(decimal_places=3, max_digits=12)),
                ("unit_cost", models.DecimalField(decimal_places=2, max_digits=12)),
                ("line_total", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "product",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="catalog.product"),
                ),
                (
                    "purchase",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="finance.purchase"),
                ),
            ],
        ),
    ]
