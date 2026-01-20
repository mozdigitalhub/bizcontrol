from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from catalog.models import Product
from customers.models import Customer
from sales.models import Sale
from tenants.models import Business


class Quotation(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Rascunho"),
        (STATUS_SENT, "Enviada"),
        (STATUS_APPROVED, "Aprovada"),
        (STATUS_REJECTED, "Rejeitada"),
        (STATUS_EXPIRED, "Expirada"),
        (STATUS_CANCELED, "Cancelada"),
    ]

    DISCOUNT_NONE = "none"
    DISCOUNT_FIXED = "fixed"
    DISCOUNT_PERCENT = "percent"
    DISCOUNT_CHOICES = [
        (DISCOUNT_NONE, "Sem desconto"),
        (DISCOUNT_FIXED, "Valor fixo"),
        (DISCOUNT_PERCENT, "Percentagem"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="quotations"
    )
    code = models.CharField(max_length=30, null=True, blank=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="quotations"
    )
    sale = models.OneToOneField(
        Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name="quotation"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    issue_date = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=10, default="MZN")
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(
        max_length=10, choices=DISCOUNT_CHOICES, default=DISCOUNT_NONE
    )
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_snapshot = models.JSONField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_quotations",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_quotations",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_quotations",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_quotations",
    )
    canceled_at = models.DateTimeField(null=True, blank=True)
    canceled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="canceled_quotations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"],
                condition=Q(code__isnull=False),
                name="uniq_quotation_code_business",
            )
        ]
        indexes = [
            models.Index(fields=["business", "status", "issue_date"]),
        ]

    def __str__(self):
        return f"Cotacao {self.code or self.id}"

    def mark_expired_if_needed(self, today=None):
        if self.status not in {self.STATUS_DRAFT, self.STATUS_SENT}:
            return False
        if not self.valid_until:
            return False
        today_value = today or timezone.localdate()
        if self.valid_until < today_value:
            self.status = self.STATUS_EXPIRED
            self.save(update_fields=["status"])
            return True
        return False


class QuotationItem(models.Model):
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="quotation_items"
    )
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    line_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        indexes = [
            models.Index(fields=["quotation", "product"]),
        ]

    def __str__(self):
        return f"{self.description} x {self.quantity}"


class QuotationStatusHistory(models.Model):
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name="status_history"
    )
    status = models.CharField(max_length=20, choices=Quotation.STATUS_CHOICES)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotation_status_changes",
    )
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["quotation", "changed_at"]),
        ]

    def __str__(self):
        return f"{self.quotation_id} {self.status}"
