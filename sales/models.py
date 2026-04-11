from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from catalog.models import Product
from customers.models import Customer
from tenants.models import Business


class ContingencyBatch(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Aberto"),
        (STATUS_CLOSED, "Fechado"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="contingency_batches"
    )
    code = models.CharField(max_length=40)
    date_from = models.DateField()
    date_to = models.DateField()
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opened_contingency_batches",
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_contingency_batches",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"],
                name="uniq_contingency_batch_code_business",
            )
        ]
        indexes = [
            models.Index(fields=["business", "status", "date_from", "date_to"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business} - {self.code}"


class Sale(models.Model):
    SALE_TYPE_NORMAL = "normal"
    SALE_TYPE_DEPOSIT = "deposit"
    SALE_TYPE_CHOICES = [
        (SALE_TYPE_NORMAL, "Venda normal"),
        (SALE_TYPE_DEPOSIT, "Deposito de material"),
    ]

    DELIVERY_IMMEDIATE = "immediate"
    DELIVERY_SCHEDULED = "scheduled"
    DELIVERY_CHOICES = [
        (DELIVERY_IMMEDIATE, "Levantamento imediato"),
        (DELIVERY_SCHEDULED, "Levantamento faseado"),
    ]

    DELIVERY_STATUS_PENDING = "pending"
    DELIVERY_STATUS_PARTIAL = "partial"
    DELIVERY_STATUS_DELIVERED = "delivered"
    DELIVERY_STATUS_CHOICES = [
        (DELIVERY_STATUS_PENDING, "Pendente"),
        (DELIVERY_STATUS_PARTIAL, "Parcialmente entregue"),
        (DELIVERY_STATUS_DELIVERED, "Totalmente entregue"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Rascunho"),
        (STATUS_CONFIRMED, "Confirmada"),
        (STATUS_CANCELED, "Cancelada"),
    ]

    PAYMENT_UNPAID = "unpaid"
    PAYMENT_PARTIAL = "partial"
    PAYMENT_PAID = "paid"
    PAYMENT_CHOICES = [
        (PAYMENT_UNPAID, "Nao paga"),
        (PAYMENT_PARTIAL, "Parcial"),
        (PAYMENT_PAID, "Paga"),
    ]

    METHOD_CASH = "cash"
    METHOD_CARD = "card"
    METHOD_BANK = "bank_transfer"
    METHOD_MPESA = "mpesa"
    METHOD_EMOLA = "emola"
    METHOD_MKESH = "mkesh"
    METHOD_OTHER = "other"
    METHOD_CHOICES = [
        (METHOD_BANK, "Transferencia"),
        (METHOD_CARD, "Cartao"),
        (METHOD_CASH, "Numerario"),
        (METHOD_MPESA, "M-Pesa"),
        (METHOD_EMOLA, "e-Mola"),
        (METHOD_MKESH, "M-Kesh"),
        (METHOD_OTHER, "Outro"),
    ]

    DISCOUNT_NONE = "none"
    DISCOUNT_FIXED = "fixed"
    DISCOUNT_PERCENT = "percent"
    DISCOUNT_CHOICES = [
        (DISCOUNT_NONE, "Sem desconto"),
        (DISCOUNT_FIXED, "Valor fixo"),
        (DISCOUNT_PERCENT, "Percentagem"),
    ]

    DOWNPAY_NONE = "none"
    DOWNPAY_FIXED = "fixed"
    DOWNPAY_PERCENT = "percent"
    DOWNPAY_CHOICES = [
        (DOWNPAY_NONE, "Sem entrada"),
        (DOWNPAY_FIXED, "Valor fixo"),
        (DOWNPAY_PERCENT, "Percentagem"),
    ]

    RETURN_NONE = "none"
    RETURN_PARTIAL = "partial"
    RETURN_TOTAL = "total"
    RETURN_CHOICES = [
        (RETURN_NONE, "Sem devolucao"),
        (RETURN_PARTIAL, "Devolucao parcial"),
        (RETURN_TOTAL, "Devolucao total"),
    ]
    ENTRY_MODE_NORMAL = "normal"
    ENTRY_MODE_CONTINGENCY = "contingency"
    ENTRY_MODE_CHOICES = [
        (ENTRY_MODE_NORMAL, "Normal"),
        (ENTRY_MODE_CONTINGENCY, "Contingencia"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="sales")
    code = models.CharField(max_length=30, null=True, blank=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales"
    )
    sale_type = models.CharField(
        max_length=20, choices=SALE_TYPE_CHOICES, default=SALE_TYPE_NORMAL
    )
    delivery_mode = models.CharField(
        max_length=20, choices=DELIVERY_CHOICES, default=DELIVERY_IMMEDIATE
    )
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default=DELIVERY_STATUS_PENDING,
    )
    entry_mode = models.CharField(
        max_length=20, choices=ENTRY_MODE_CHOICES, default=ENTRY_MODE_NORMAL
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    sale_date = models.DateTimeField(default=timezone.now)
    contingency_batch = models.ForeignKey(
        ContingencyBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
    )
    contingency_reason = models.CharField(max_length=255, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(
        max_length=10, choices=DISCOUNT_CHOICES, default=DISCOUNT_NONE
    )
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(
        max_length=20, choices=METHOD_CHOICES, blank=True
    )
    payment_due_date = models.DateField(null=True, blank=True)
    has_down_payment = models.BooleanField(default=False)
    down_payment_type = models.CharField(
        max_length=10, choices=DOWNPAY_CHOICES, default=DOWNPAY_NONE
    )
    down_payment_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    down_payment_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_UNPAID
    )
    is_credit = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sales",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_sales",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    canceled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="canceled_sales",
    )
    cancel_reason = models.TextField(blank=True)
    return_type = models.CharField(
        max_length=10, choices=RETURN_CHOICES, default=RETURN_NONE
    )

    class Meta:
        indexes = [
            models.Index(fields=["business", "status", "sale_date"]),
            models.Index(fields=["business", "entry_mode", "sale_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"],
                condition=Q(code__isnull=False),
                name="uniq_sale_code",
            )
        ]
        permissions = [
            ("can_backdate_sale", "Pode registar vendas retroativas"),
        ]

    def __str__(self):
        return f"Sale {self.code or self.id} - {self.total}"

    @property
    def is_backdated(self):
        if not self.sale_date or not self.created_at:
            return False
        return self.sale_date.date() < self.created_at.date()


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="sale_items")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    returned_quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        indexes = [
            models.Index(fields=["sale", "product"]),
        ]

    def __str__(self):
        return f"{self.product} x {self.quantity}"


class SaleRefund(models.Model):
    STATUS_REFUNDED = "refunded"
    STATUS_CHOICES = [
        (STATUS_REFUNDED, "Estornado"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="sale_refunds"
    )
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="refunds")
    return_type = models.CharField(
        max_length=10, choices=Sale.RETURN_CHOICES, default=Sale.RETURN_NONE
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_REFUNDED
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sale_refunds",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Estorno {self.sale_id} - {self.amount}"
