from django.conf import settings
from django.db import models
from django.db.models import Q

from tenants.models import Business


class Category(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"], name="uniq_category_name_business"
            )
        ]

    def __str__(self):
        return self.name


class Product(models.Model):
    STOCK_AUTOMATIC = "automatic"
    STOCK_MANUAL = "manual"
    STOCK_MODE_CHOICES = [
        (STOCK_AUTOMATIC, "Automatico"),
        (STOCK_MANUAL, "Manual"),
    ]
    UNIT_CHOICES = [
        ("un", "Un"),
        ("kg", "Kg"),
        ("metro", "Metro"),
        ("saco", "Saco"),
        ("litro", "Litro"),
        ("caixa", "Caixa"),
        ("pacote", "Pacote"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=60, blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    unit_of_measure = models.CharField(max_length=20, choices=UNIT_CHOICES, default="un")
    stock_control_mode = models.CharField(
        max_length=20, choices=STOCK_MODE_CHOICES, default=STOCK_AUTOMATIC
    )
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reorder_level = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_products",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_products",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"], name="uniq_product_name_business"
            ),
            models.UniqueConstraint(
                fields=["business", "sku"],
                condition=Q(sku__isnull=False) & ~Q(sku=""),
                name="uniq_product_sku_business",
            ),
        ]

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    name = models.CharField(max_length=120, blank=True)
    size = models.CharField(max_length=30, blank=True)
    color = models.CharField(max_length=30, blank=True)
    sku = models.CharField(max_length=60, blank=True)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_qty = models.IntegerField(default=0)
    reorder_level = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "name", "size", "color"],
                name="uniq_product_variant_identity",
            ),
            models.UniqueConstraint(
                fields=["product", "sku"],
                condition=Q(sku__isnull=False) & ~Q(sku=""),
                name="uniq_variant_sku_per_product",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "is_active"]),
            models.Index(fields=["product", "stock_qty"]),
        ]

    def __str__(self):
        parts = [self.product.name]
        descriptor = " ".join(part for part in [self.name, self.size, self.color] if part)
        if descriptor:
            parts.append(descriptor)
        return " - ".join(parts)
