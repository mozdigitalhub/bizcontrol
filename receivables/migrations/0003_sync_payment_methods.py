from django.db import migrations


def forwards(apps, schema_editor):
    Payment = apps.get_model("receivables", "Payment")
    InvoicePayment = apps.get_model("billing", "InvoicePayment")
    allowed = {
        "cash",
        "card",
        "bank_transfer",
        "cheque",
        "mpesa",
        "emola",
        "mkesh",
        "other",
    }

    for invoice_payment in InvoicePayment.objects.exclude(receivable_payment_id__isnull=True):
        payment = Payment.objects.filter(id=invoice_payment.receivable_payment_id).first()
        if not payment:
            continue
        target_method = (
            invoice_payment.method
            if invoice_payment.method in allowed
            else "other"
        )
        if payment.method != target_method:
            payment.method = target_method
            payment.save(update_fields=["method"])


class Migration(migrations.Migration):

    dependencies = [
        ("receivables", "0002_initial"),
        ("billing", "0007_invoicepayment_receivable_payment"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
