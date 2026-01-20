from django.db import migrations, models


def _build_code(prefix, seq_date, business_id, seq_value):
    return f"{prefix}-{seq_date.strftime('%y%m%d')}-{business_id}-{seq_value:03d}"


def backfill_sale_codes(apps, schema_editor):
    Sale = apps.get_model("sales", "Sale")
    DocumentSequence = apps.get_model("tenants", "DocumentSequence")
    sales = (
        Sale.objects.filter(code__isnull=True)
        .order_by("business_id", "sale_date", "created_at", "id")
    )
    for sale in sales:
        seq_date = sale.sale_date.date()
        seq = (
            DocumentSequence.objects.filter(
                business_id=sale.business_id, doc_type="sale", seq_date=seq_date
            )
            .first()
        )
        if not seq:
            seq = DocumentSequence.objects.create(
                business_id=sale.business_id,
                doc_type="sale",
                seq_date=seq_date,
                current_value=0,
            )
        seq.current_value += 1
        seq.save(update_fields=["current_value"])
        sale.code = _build_code("V", seq_date, sale.business_id, seq.current_value)
        sale.save(update_fields=["code"])


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0010_document_sequence"),
        ("sales", "0008_saleitem_quantity_integer"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="code",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddConstraint(
            model_name="sale",
            constraint=models.UniqueConstraint(
                fields=("business", "code"),
                condition=models.Q(code__isnull=False),
                name="uniq_sale_code",
            ),
        ),
        migrations.RunPython(backfill_sale_codes, migrations.RunPython.noop),
    ]
