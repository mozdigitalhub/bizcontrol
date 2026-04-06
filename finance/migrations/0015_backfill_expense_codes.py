from django.db import migrations
from django.db.models import Q


def _build_code(seq_date, business_id, seq_value):
    return f"D-{seq_date.strftime('%y%m%d')}-{business_id}-{seq_value:03d}"


def backfill_expense_codes(apps, schema_editor):
    Expense = apps.get_model("finance", "Expense")
    DocumentSequence = apps.get_model("tenants", "DocumentSequence")

    missing = Expense.objects.filter(Q(code__isnull=True) | Q(code=""))
    for expense in missing.order_by("business_id", "expense_date", "id"):
        seq_date = expense.expense_date
        seq = (
            DocumentSequence.objects.filter(
                business_id=expense.business_id,
                doc_type="expense",
                seq_date=seq_date,
            )
            .first()
        )
        if not seq:
            seq = DocumentSequence.objects.create(
                business_id=expense.business_id,
                doc_type="expense",
                seq_date=seq_date,
                current_value=0,
            )
        seq.current_value += 1
        seq.save(update_fields=["current_value"])
        expense.code = _build_code(seq_date, expense.business_id, seq.current_value)
        expense.save(update_fields=["code"])


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0014_expense_code"),
        ("tenants", "0016_rename_tenants_ten_business_d9b7b9_idx_tenants_ten_busines_c715dc_idx"),
    ]

    operations = [
        migrations.RunPython(backfill_expense_codes, migrations.RunPython.noop),
    ]
