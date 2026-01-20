from django.db import migrations, models


def _build_code(prefix, seq_date, business_id, seq_value):
    return f"{prefix}-{seq_date.strftime('%y%m%d')}-{business_id}-{seq_value:03d}"


def backfill_invoice_receipt_codes(apps, schema_editor):
    Invoice = apps.get_model("billing", "Invoice")
    Receipt = apps.get_model("billing", "Receipt")
    DocumentSequence = apps.get_model("tenants", "DocumentSequence")

    invoices = (
        Invoice.objects.filter(code__isnull=True)
        .order_by("business_id", "issue_date", "created_at", "id")
    )
    for invoice in invoices:
        seq_date = invoice.issue_date
        seq = (
            DocumentSequence.objects.filter(
                business_id=invoice.business_id,
                doc_type="invoice",
                seq_date=seq_date,
            )
            .first()
        )
        if not seq:
            seq = DocumentSequence.objects.create(
                business_id=invoice.business_id,
                doc_type="invoice",
                seq_date=seq_date,
                current_value=0,
            )
        seq.current_value += 1
        seq.save(update_fields=["current_value"])
        invoice.code = _build_code("F", seq_date, invoice.business_id, seq.current_value)
        invoice.save(update_fields=["code"])

    receipts = (
        Receipt.objects.filter(code__isnull=True)
        .order_by("business_id", "issue_date", "created_at", "id")
    )
    for receipt in receipts:
        seq_date = receipt.issue_date
        seq = (
            DocumentSequence.objects.filter(
                business_id=receipt.business_id,
                doc_type="receipt",
                seq_date=seq_date,
            )
            .first()
        )
        if not seq:
            seq = DocumentSequence.objects.create(
                business_id=receipt.business_id,
                doc_type="receipt",
                seq_date=seq_date,
                current_value=0,
            )
        seq.current_value += 1
        seq.save(update_fields=["current_value"])
        receipt.code = _build_code("R", seq_date, receipt.business_id, seq.current_value)
        receipt.save(update_fields=["code"])


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0010_document_sequence"),
        ("billing", "0012_alter_invoicepayment_method"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="code",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name="receipt",
            name="code",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                fields=("business", "code"),
                condition=models.Q(code__isnull=False),
                name="uniq_invoice_code",
            ),
        ),
        migrations.AddConstraint(
            model_name="receipt",
            constraint=models.UniqueConstraint(
                fields=("business", "code"),
                condition=models.Q(code__isnull=False),
                name="uniq_receipt_code",
            ),
        ),
        migrations.RunPython(backfill_invoice_receipt_codes, migrations.RunPython.noop),
    ]
