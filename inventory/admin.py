from django.contrib import admin

from inventory.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    ProductCostHistory,
    ProductSalePriceHistory,
    StockMovement,
)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("product", "movement_type", "quantity", "business", "created_at")
    list_filter = ("movement_type", "business")


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ("id", "supplier", "document_number", "document_date", "business", "created_at")
    list_filter = ("business", "document_date")
    search_fields = ("document_number", "supplier__name")


@admin.register(GoodsReceiptItem)
class GoodsReceiptItemAdmin(admin.ModelAdmin):
    list_display = ("receipt", "product", "quantity", "unit_cost", "sale_price")
    list_filter = ("receipt__business",)


@admin.register(ProductCostHistory)
class ProductCostHistoryAdmin(admin.ModelAdmin):
    list_display = ("product", "unit_cost", "receipt", "created_at")
    list_filter = ("business",)


@admin.register(ProductSalePriceHistory)
class ProductSalePriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("product", "old_price", "new_price", "receipt", "created_at")
    list_filter = ("business",)
    search_fields = ("product__name",)
