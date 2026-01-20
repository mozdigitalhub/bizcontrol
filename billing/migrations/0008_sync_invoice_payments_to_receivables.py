from django.db import migrations, models


def forwards(apps, schema_editor):
    InvoicePayment = apps.get_model("billing", "InvoicePayment")
    Invoice = apps.get_model("billing", "Invoice")
    Receipt = apps.get_model("billing", "Receipt")
    Receivable = apps.get_model("receivables", "Receivable")
    Payment = apps.get_model("receivables", "Payment")
    Sale = apps.get_model("sales", "Sale")

    method_map = {
        "cash": "cash",
        "card": "card",
        "bank_transfer": "bank_transfer",
        "cheque": "cheque",
        "mpesa": "mpesa",
        "emola": "emola",
        "mkesh": "mkesh",
        "other": "other",
    }

    for invoice_payment in InvoicePayment.objects.select_related("invoice").all():
        if invoice_payment.receivable_payment_id:
            continue
        invoice = invoice_payment.invoice
        if not invoice or not invoice.sale_id:
            continue
        receivable = Receivable.objects.filter(
            sale_id=invoice.sale_id,
            business_id=invoice_payment.business_id,
        ).first()
        if not receivable:
            continue

        existing = Payment.objects.filter(
            receivable_id=receivable.id,
            amount=invoice_payment.amount,
            created_by_id=invoice_payment.created_by_id,
            paid_at__date=invoice_payment.paid_at.date(),
        ).first()
        if not existing:
            existing = Payment.objects.create(
                business_id=invoice_payment.business_id,
                receivable_id=receivable.id,
                amount=invoice_payment.amount,
                method=method_map.get(invoice_payment.method, "other"),
                paid_at=invoice_payment.paid_at,
                notes=invoice_payment.notes or "",
                created_by_id=invoice_payment.created_by_id,
            )

        invoice_payment.receivable_payment_id = existing.id
        invoice_payment.save(update_fields=["receivable_payment"])

        Receipt.objects.filter(
            invoice_payment_id=invoice_payment.id, payment__isnull=True
        ).update(payment_id=existing.id)

        total_paid = (
            Payment.objects.filter(receivable_id=receivable.id).aggregate(
                total=models.Sum("amount")
            )["total"]
            or 0
        )
        receivable.total_paid = total_paid
        receivable.status = (
            "settled"
            if receivable.original_amount - total_paid <= 0
            else "open"
        )
        receivable.save(update_fields=["total_paid", "status"])

        if receivable.sale_id:
            sale = Sale.objects.filter(id=receivable.sale_id).first()
            if sale:
                sale.payment_status = (
                    "paid" if receivable.original_amount - total_paid <= 0 else "partial"
                )
                sale.save(update_fields=["payment_status"])

        if invoice.status != "canceled":
            paid_total = (
                InvoicePayment.objects.filter(invoice_id=invoice.id).aggregate(
                    total=models.Sum("amount")
                )["total"]
                or 0
            )
            extra_total = (
                Payment.objects.filter(
                    receivable_id=receivable.id, invoice_payment__isnull=True
                ).aggregate(total=models.Sum("amount"))["total"]
                or 0
            )
            balance = invoice.total - (paid_total + extra_total)
            if balance <= 0:
                invoice.status = "paid"
            elif paid_total + extra_total > 0:
                invoice.status = "partial"
            else:
                invoice.status = "issued"
            invoice.save(update_fields=["status"])


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0007_invoicepayment_receivable_payment"),
        ("receivables", "0002_initial"),
        ("sales", "0004_sale_returns_and_refunds"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
