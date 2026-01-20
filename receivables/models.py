from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from customers.models import Customer
from sales.models import Sale
from tenants.models import Business


class Receivable(models.Model):
    STATUS_OPEN = "open"
    STATUS_SETTLED = "settled"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Em aberto"),
        (STATUS_SETTLED, "Liquidado"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="receivables")
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="receivables"
    )
    sale = models.ForeignKey(
        Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name="receivables"
    )
    original_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "status"]),
        ]

    @property
    def balance(self):
        return self.original_amount - self.total_paid

    def __str__(self):
        return f"{self.customer} - {self.balance}"


class Payment(models.Model):
    METHOD_CASH = "cash"
    METHOD_CARD = "card"
    METHOD_BANK = "bank_transfer"
    METHOD_CHEQUE = "cheque"
    METHOD_MPESA = "mpesa"
    METHOD_EMOLA = "emola"
    METHOD_MKESH = "mkesh"
    METHOD_OTHER = "other"
    METHOD_CHOICES = [
        (METHOD_CASH, "Numerario"),
        (METHOD_CARD, "Cartao"),
        (METHOD_BANK, "Transferencia"),
        (METHOD_CHEQUE, "Cheque"),
        (METHOD_MPESA, "MPesa"),
        (METHOD_EMOLA, "Emola"),
        (METHOD_MKESH, "MKesh"),
        (METHOD_OTHER, "Outro"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="payments")
    receivable = models.ForeignKey(
        Receivable, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_CASH)
    paid_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.receivable} - {self.amount}"
