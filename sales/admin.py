from django.contrib import admin

from sales.models import ContingencyBatch, Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "business", "status", "entry_mode", "total", "sale_date")
    list_filter = ("status", "entry_mode", "business")
    date_hierarchy = "sale_date"
    inlines = [SaleItemInline]


@admin.register(ContingencyBatch)
class ContingencyBatchAdmin(admin.ModelAdmin):
    list_display = ("code", "business", "date_from", "date_to", "status", "created_at")
    list_filter = ("status", "business")
    search_fields = ("code", "notes")
