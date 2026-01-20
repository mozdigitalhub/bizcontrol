from django.db import migrations, models


def _build_code(prefix, seq_date, business_id, seq_value):
    return f"{prefix}-{seq_date.strftime('%y%m%d')}-{business_id}-{seq_value:03d}"


def backfill_guide_codes(apps, schema_editor):
    DeliveryGuide = apps.get_model("deliveries", "DeliveryGuide")
    DocumentSequence = apps.get_model("tenants", "DocumentSequence")
    guides = (
        DeliveryGuide.objects.filter(code__isnull=True)
        .order_by("business_id", "issued_at", "created_at", "id")
    )
    for guide in guides:
        seq_date = guide.issued_at.date()
        seq = (
            DocumentSequence.objects.filter(
                business_id=guide.business_id,
                doc_type="delivery",
                seq_date=seq_date,
            )
            .first()
        )
        if not seq:
            seq = DocumentSequence.objects.create(
                business_id=guide.business_id,
                doc_type="delivery",
                seq_date=seq_date,
                current_value=0,
            )
        seq.current_value += 1
        seq.save(update_fields=["current_value"])
        guide.code = _build_code("G", seq_date, guide.business_id, seq.current_value)
        guide.save(update_fields=["code"])


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0010_document_sequence"),
        ("deliveries", "0002_delivery_item_quantity_integer"),
    ]

    operations = [
        migrations.AddField(
            model_name="deliveryguide",
            name="code",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddConstraint(
            model_name="deliveryguide",
            constraint=models.UniqueConstraint(
                fields=("business", "code"),
                condition=models.Q(code__isnull=False),
                name="uniq_delivery_guide_code",
            ),
        ),
        migrations.RunPython(backfill_guide_codes, migrations.RunPython.noop),
    ]
