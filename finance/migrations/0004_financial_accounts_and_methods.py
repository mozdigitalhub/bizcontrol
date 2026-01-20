from django.db import migrations, models
import django.db.models.deletion


DEFAULT_ACCOUNTS = [
    ("cash", "Caixa Principal"),
    ("bank", "Banco Principal"),
    ("mobile", "Carteira Principal"),
]

DEFAULT_PAYMENT_METHODS = [
    ("cash", "Dinheiro", "cash", "Caixa Principal"),
    ("card", "Cartao", "bank", "Banco Principal"),
    ("bank_transfer", "Transferencia", "bank", "Banco Principal"),
    ("cheque", "Cheque", "bank", "Banco Principal"),
    ("mpesa", "MPesa", "mobile", "Carteira Principal"),
    ("emola", "Emola", "mobile", "Carteira Principal"),
    ("mkesh", "MKesh", "mobile", "Carteira Principal"),
    ("other", "Outro", "cash", "Caixa Principal"),
]


def create_defaults(apps, schema_editor):
    Business = apps.get_model("tenants", "Business")
    FinancialAccount = apps.get_model("finance", "FinancialAccount")
    PaymentMethod = apps.get_model("finance", "PaymentMethod")
    CashMovement = apps.get_model("finance", "CashMovement")

    for business in Business.objects.all():
        existing_accounts = {
            account.name: account
            for account in FinancialAccount.objects.filter(
                business=business, name__in=[name for _, name in DEFAULT_ACCOUNTS]
            )
        }
        accounts_to_create = [
            FinancialAccount(business=business, category=category, name=name)
            for category, name in DEFAULT_ACCOUNTS
            if name not in existing_accounts
        ]
        if accounts_to_create:
            FinancialAccount.objects.bulk_create(accounts_to_create)
            existing_accounts.update(
                {
                    account.name: account
                    for account in FinancialAccount.objects.filter(business=business)
                }
            )

        existing_methods = set(
            PaymentMethod.objects.filter(
                business=business, code__in=[code for code, _, _, _ in DEFAULT_PAYMENT_METHODS]
            ).values_list("code", flat=True)
        )
        payment_methods = []
        for code, name, category, account_name in DEFAULT_PAYMENT_METHODS:
            if code in existing_methods:
                continue
            account = existing_accounts.get(account_name)
            if not account:
                account = FinancialAccount.objects.create(
                    business=business, category=category, name=account_name
                )
                existing_accounts[account_name] = account
            payment_methods.append(
                PaymentMethod(
                    business=business,
                    code=code,
                    name=name,
                    category=category,
                    account=account,
                )
            )
        if payment_methods:
            PaymentMethod.objects.bulk_create(payment_methods)

        movements = CashMovement.objects.filter(business=business, payment_method__isnull=True)
        if not movements.exists():
            continue
        method_map = {code: category for code, _, category, _ in DEFAULT_PAYMENT_METHODS}
        for movement in movements.iterator():
            method_code = movement.method or "cash"
            category = method_map.get(method_code, "cash")
            account = FinancialAccount.objects.filter(
                business=business, category=category
            ).first()
            payment_method = PaymentMethod.objects.filter(
                business=business, code=method_code
            ).first()
            movement.category = category
            movement.account_id = account.id if account else None
            movement.payment_method_id = payment_method.id if payment_method else None
            movement.save(update_fields=["category", "account", "payment_method"])


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0003_merge_finance_0002"),
    ]

    operations = [
        migrations.CreateModel(
            name="FinancialAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                (
                    "category",
                    models.CharField(
                        choices=[("cash", "Caixa"), ("bank", "Banco"), ("mobile", "Carteiras moveis")],
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="financial_accounts", to="tenants.business"),
                ),
            ],
            options={"unique_together": {("business", "name")}},
        ),
        migrations.CreateModel(
            name="PaymentMethod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=30)),
                ("name", models.CharField(max_length=120)),
                (
                    "category",
                    models.CharField(
                        choices=[("cash", "Caixa"), ("bank", "Banco"), ("mobile", "Carteiras moveis")],
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payment_methods",
                        to="finance.financialaccount",
                    ),
                ),
                (
                    "business",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_methods", to="tenants.business"),
                ),
            ],
            options={"unique_together": {("business", "code")}},
        ),
        migrations.AddField(
            model_name="cashmovement",
            name="account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cash_movements",
                to="finance.financialaccount",
            ),
        ),
        migrations.AddField(
            model_name="cashmovement",
            name="category",
            field=models.CharField(
                blank=True,
                choices=[("cash", "Caixa"), ("bank", "Banco"), ("mobile", "Carteiras moveis")],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="cashmovement",
            name="payment_method",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cash_movements",
                to="finance.paymentmethod",
            ),
        ),
        migrations.AddIndex(
            model_name="cashmovement",
            index=models.Index(fields=["business", "category"], name="finance_cash_business_category_idx"),
        ),
        migrations.RunPython(create_defaults, migrations.RunPython.noop),
    ]
