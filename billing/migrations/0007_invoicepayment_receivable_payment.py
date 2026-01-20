from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0006_rename_billing_invo_business_bf0c70_idx_billing_inv_busines_517701_idx"),
        ("receivables", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoicepayment",
            name="receivable_payment",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invoice_payment",
                to="receivables.payment",
            ),
        ),
    ]
