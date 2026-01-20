from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from customers.models import Customer
from receivables.models import Payment
from sales.models import Sale
from tenants.models import Business


class Sequence(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="sequences")
    name = models.CharField(max_length=30)
    current_value = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "name"], name="uniq_sequence_name")
        ]

    def __str__(self):
        return f"{self.business} - {self.name}"


class Invoice(models.Model):
    STATUS_ISSUED = "issued"
    STATUS_PARTIAL = "partial"
    STATUS_PAID = "paid"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_ISSUED, "Em aberto"),
        (STATUS_PARTIAL, "Parcialmente paga"),
        (STATUS_PAID, "Paga"),
        (STATUS_CANCELED, "Cancelada"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="invoices")
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices"
    )
    payment_snapshot = models.JSONField(default=dict, blank=True)
    sale = models.ForeignKey(
        Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices"
    )
    code = models.CharField(max_length=30, null=True, blank=True)
    invoice_number = models.PositiveBigIntegerField()
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ISSUED)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "invoice_number"], name="uniq_invoice_number"
            ),
            models.UniqueConstraint(
                fields=["business", "code"],
                condition=Q(code__isnull=False),
                name="uniq_invoice_code",
            ),
        ]

    def __str__(self):
        return f"Fatura {self.code or self.invoice_number}"

    @property
    def amount_paid(self):
        if not hasattr(self, "_amount_paid_cache"):
            total = self.payments.aggregate(total=models.Sum("amount"))["total"] or Decimal("0")
            if self.sale_id:
                from receivables.models import Payment

                total += (
                    Payment.objects.filter(
                        receivable__sale_id=self.sale_id,
                        invoice_payment__isnull=True,
                    ).aggregate(total=models.Sum("amount"))["total"]
                    or Decimal("0")
                )
            self._amount_paid_cache = total
        return self._amount_paid_cache

    @property
    def balance(self):
        return self.total - self.amount_paid


class InvoicePayment(models.Model):
    METHOD_CASH = "cash"
    METHOD_CARD = "card"
    METHOD_TRANSFER = "bank_transfer"
    METHOD_CHEQUE = "cheque"
    METHOD_MPESA = "mpesa"
    METHOD_EMOLA = "emola"
    METHOD_MKESH = "mkesh"
    METHOD_OTHER = "other"
    METHOD_CHOICES = [
        (METHOD_CASH, "Numerario"),
        (METHOD_CARD, "Cartao"),
        (METHOD_TRANSFER, "Transferencia"),
        (METHOD_CHEQUE, "Cheque"),
        (METHOD_MPESA, "MPesa"),
        (METHOD_EMOLA, "Emola"),
        (METHOD_MKESH, "MKesh"),
        (METHOD_OTHER, "Outro"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="invoice_payments"
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    paid_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    receivable_payment = models.OneToOneField(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_payment",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "invoice"]),
        ]

    def __str__(self):
        return f"Pagamento {self.invoice.invoice_number} - {self.amount}"


class Receipt(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="receipts")
    invoice = models.ForeignKey(
        Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="receipts"
    )
    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="receipts"
    )
    invoice_payment = models.ForeignKey(
        InvoicePayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipts",
    )
    code = models.CharField(max_length=30, null=True, blank=True)
    receipt_number = models.PositiveBigIntegerField()
    issue_date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_receipts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "receipt_number"], name="uniq_receipt_number"
            ),
            models.UniqueConstraint(
                fields=["business", "code"],
                condition=Q(code__isnull=False),
                name="uniq_receipt_code",
            ),
        ]

    def __str__(self):
        return f"Recibo {self.code or self.receipt_number}"
