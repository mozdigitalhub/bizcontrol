from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from customers.models import Customer
from sales.models import Sale, SaleItem
from tenants.models import Business


class DeliveryGuide(models.Model):
    STATUS_ISSUED = "issued"
    STATUS_PARTIAL = "partial"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_ISSUED, "Emitida"),
        (STATUS_PARTIAL, "Parcialmente entregue"),
        (STATUS_DELIVERED, "Totalmente entregue"),
        (STATUS_CANCELED, "Cancelada"),
    ]

    ORIGIN_SALE = "sale"
    ORIGIN_CREDIT = "credit"
    ORIGIN_DEPOSIT = "deposit"
    ORIGIN_CHOICES = [
        (ORIGIN_SALE, "Venda normal"),
        (ORIGIN_CREDIT, "Fiado"),
        (ORIGIN_DEPOSIT, "Deposito de material"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="delivery_guides"
    )
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="delivery_guides")
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_guides"
    )
    code = models.CharField(max_length=30, null=True, blank=True)
    guide_number = models.PositiveBigIntegerField()
    origin_type = models.CharField(max_length=20, choices=ORIGIN_CHOICES)
    issued_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ISSUED)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_delivery_guides",
    )
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivered_guides",
    )
    expected_delivery_date = models.DateField(null=True, blank=True)
    transport_responsible = models.CharField(max_length=120, blank=True)
    transport_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "guide_number"], name="uniq_delivery_guide_number"
            ),
            models.UniqueConstraint(
                fields=["business", "code"],
                condition=Q(code__isnull=False),
                name="uniq_delivery_guide_code",
            ),
        ]
        indexes = [
            models.Index(fields=["business", "issued_at"]),
            models.Index(fields=["business", "status"]),
        ]

    def __str__(self):
        return f"Guia {self.code or self.guide_number}"


class DeliveryGuideItem(models.Model):
    guide = models.ForeignKey(
        DeliveryGuide, on_delete=models.CASCADE, related_name="items"
    )
    sale_item = models.ForeignKey(
        SaleItem, on_delete=models.CASCADE, related_name="delivery_items"
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="delivery_items",
    )
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["guide", "product"]),
        ]

    def __str__(self):
        return f"{self.product} - {self.quantity}"
