from django.contrib import admin

from sales.models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "business", "status", "total", "sale_date")
    list_filter = ("status", "business")
    date_hierarchy = "sale_date"
    inlines = [SaleItemInline]
