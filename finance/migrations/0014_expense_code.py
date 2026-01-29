from django.db import migrations, models
from django.db.models import Q

def backfill_expense_codes(apps, schema_editor):
    Expense = apps.get_model("finance", "Expense")
    DocumentSequence = apps.get_model("tenants", "DocumentSequence")
    qs = (
        Expense.objects.select_related("business")
        .filter(Q(code__isnull=True) | Q(code=""))
        .order_by("expense_date", "id")
    )
    for expense in qs:
        if not expense.business_id:
            continue
        seq_date = expense.expense_date
        seq = (
            DocumentSequence.objects.filter(
                business_id=expense.business_id, doc_type="expense", seq_date=seq_date
            )
            .select_for_update()
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
        expense.code = f"D-{seq_date.strftime('%y%m%d')}-{expense.business_id}-{seq.current_value:03d}"
        expense.save(update_fields=["code"])

class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0016_rename_tenants_ten_business_d9b7b9_idx_tenants_ten_busines_c715dc_idx"),
        ("finance", "0013_rename_finance_purc_busines_6db6f9_idx_finance_pur_busines_9df87a_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="expense",
            name="code",
            field=models.CharField(max_length=30, null=True, blank=True),
        ),
        migrations.RunPython(backfill_expense_codes, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="expense",
            constraint=models.UniqueConstraint(
                fields=("business", "code"),
                condition=models.Q(code__isnull=False),
                name="uniq_expense_code_business",
            ),
        ),
    ]
