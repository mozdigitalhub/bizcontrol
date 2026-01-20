from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import Product
from finance.models import CashMovement, Supplier, Purchase
from tenants.models import Business


class StockMovement(models.Model):
    MOVEMENT_IN = "IN"
    MOVEMENT_OUT = "OUT"
    MOVEMENT_ADJUST = "ADJUST"
    MOVEMENT_RESERVE = "RESERVE"
    MOVEMENT_CHOICES = [
        (MOVEMENT_IN, "Entrada"),
        (MOVEMENT_OUT, "Saida"),
        (MOVEMENT_ADJUST, "Ajuste"),
        (MOVEMENT_RESERVE, "Reserva"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="stock_movements")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_movements")
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_CHOICES)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    reference_type = models.CharField(max_length=30, blank=True)
    reference_id = models.PositiveBigIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "product", "created_at"]),
        ]

    def __str__(self):
        return f"{self.product} {self.movement_type} {self.quantity}"


class GoodsReceipt(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="goods_receipts"
    )
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipts",
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="goods_receipts"
    )
    document_number = models.CharField(max_length=80)
    document_date = models.DateField()
    storage_location = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    cash_movement = models.OneToOneField(
        CashMovement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipt",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "document_date"]),
            models.Index(fields=["business", "document_number"]),
        ]

    def __str__(self):
        return f"Rececao #{self.id}"


class GoodsReceiptItem(models.Model):
    receipt = models.ForeignKey(
        GoodsReceipt, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    sale_price = models.DecimalField(max_digits=12, decimal_places=2)
    storage_location = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f"{self.product} {self.quantity}"


class ProductCostHistory(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="product_cost_history"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="cost_history"
    )
    receipt = models.ForeignKey(
        GoodsReceipt, on_delete=models.SET_NULL, null=True, blank=True
    )
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_cost_history",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class ProductSalePriceHistory(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="product_sale_price_history"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="sale_price_history"
    )
    receipt = models.ForeignKey(
        GoodsReceipt, on_delete=models.SET_NULL, null=True, blank=True
    )
    old_price = models.DecimalField(max_digits=12, decimal_places=2)
    new_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_sale_price_history",
    )
    created_at = models.DateTimeField(auto_now_add=True)
