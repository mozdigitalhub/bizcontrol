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
