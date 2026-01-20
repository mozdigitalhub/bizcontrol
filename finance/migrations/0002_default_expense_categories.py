from django.db import migrations


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


def create_default_categories(apps, schema_editor):
    Business = apps.get_model("tenants", "Business")
    ExpenseCategory = apps.get_model("finance", "ExpenseCategory")
    for business in Business.objects.all():
        existing = set(
            ExpenseCategory.objects.filter(
                business=business, name__in=DEFAULT_EXPENSE_CATEGORIES
            ).values_list("name", flat=True)
        )
        to_create = [
            ExpenseCategory(business=business, name=name)
            for name in DEFAULT_EXPENSE_CATEGORIES
            if name not in existing
        ]
        if to_create:
            ExpenseCategory.objects.bulk_create(to_create)


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_categories, migrations.RunPython.noop),
    ]
