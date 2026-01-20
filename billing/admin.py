from django.contrib import admin

from billing.models import Invoice, Receipt, Sequence


@admin.register(Sequence)
class SequenceAdmin(admin.ModelAdmin):
    list_display = ("business", "name", "current_value")
    list_filter = ("name", "business")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "business", "status", "total", "issue_date")
    list_filter = ("status", "business")
    date_hierarchy = "issue_date"


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "business", "amount", "issue_date")
    date_hierarchy = "issue_date"
