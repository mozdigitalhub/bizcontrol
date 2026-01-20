from django.contrib import admin

from catalog.models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "sku", "sale_price", "stock_control_mode", "is_active")
    search_fields = ("name", "sku")
    list_filter = ("is_active", "unit_of_measure", "stock_control_mode")
