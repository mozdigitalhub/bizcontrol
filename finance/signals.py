from django.db.models.signals import post_save
from django.dispatch import receiver

from finance.models import ExpenseCategory, FinancialAccount, PaymentMethod
from tenants.models import Business


DEFAULT_EXPENSE_CATEGORIES = [
    "Energia",
    "Agua",
    "Renda",
    "Internet",
    "Salarios",
    "Transporte",
    "Manutencao",
    "Outros",
]

DEFAULT_ACCOUNTS = [
    (FinancialAccount.CATEGORY_CASH, "Caixa Principal"),
    (FinancialAccount.CATEGORY_BANK, "Banco Principal"),
    (FinancialAccount.CATEGORY_MOBILE, "Carteira Principal"),
]

DEFAULT_PAYMENT_METHODS = [
    ("cash", "Numerario", FinancialAccount.CATEGORY_CASH, "Caixa Principal"),
    ("card", "Cartao", FinancialAccount.CATEGORY_BANK, "Banco Principal"),
    ("bank_transfer", "Transferencia", FinancialAccount.CATEGORY_BANK, "Banco Principal"),
    ("cheque", "Cheque", FinancialAccount.CATEGORY_BANK, "Banco Principal"),
    ("mpesa", "MPesa", FinancialAccount.CATEGORY_MOBILE, "Carteira Principal"),
    ("emola", "Emola", FinancialAccount.CATEGORY_MOBILE, "Carteira Principal"),
    ("mkesh", "MKesh", FinancialAccount.CATEGORY_MOBILE, "Carteira Principal"),
    ("other", "Outro", FinancialAccount.CATEGORY_CASH, "Caixa Principal"),
]


@receiver(post_save, sender=Business)
def ensure_default_expense_categories(sender, instance, created, **kwargs):
    if not created:
        return
    existing = set(
        ExpenseCategory.objects.filter(
            business=instance, name__in=DEFAULT_EXPENSE_CATEGORIES
        ).values_list("name", flat=True)
    )
    to_create = [
        ExpenseCategory(business=instance, name=name)
        for name in DEFAULT_EXPENSE_CATEGORIES
        if name not in existing
    ]
    if to_create:
        ExpenseCategory.objects.bulk_create(to_create)

    existing_accounts = {
        account.name: account
        for account in FinancialAccount.objects.filter(
            business=instance, name__in=[name for _, name in DEFAULT_ACCOUNTS]
        )
    }
    accounts_to_create = [
        FinancialAccount(business=instance, category=category, name=name)
        for category, name in DEFAULT_ACCOUNTS
        if name not in existing_accounts
    ]
    if accounts_to_create:
        FinancialAccount.objects.bulk_create(accounts_to_create)
        existing_accounts.update(
            {account.name: account for account in FinancialAccount.objects.filter(business=instance)}
        )

    existing_methods = set(
        PaymentMethod.objects.filter(
            business=instance, code__in=[code for code, _, _, _ in DEFAULT_PAYMENT_METHODS]
        ).values_list("code", flat=True)
    )
    payment_methods = []
    for code, name, category, account_name in DEFAULT_PAYMENT_METHODS:
        if code in existing_methods:
            continue
        account = existing_accounts.get(account_name)
        if not account:
            account = FinancialAccount.objects.create(
                business=instance, category=category, name=account_name
            )
            existing_accounts[account_name] = account
        payment_methods.append(
            PaymentMethod(
                business=instance,
                code=code,
                name=name,
                category=category,
                account=account,
            )
        )
    if payment_methods:
        PaymentMethod.objects.bulk_create(payment_methods)
