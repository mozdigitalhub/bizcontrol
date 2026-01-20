from django.contrib import admin

from receivables.models import Payment, Receivable


@admin.register(Receivable)
class ReceivableAdmin(admin.ModelAdmin):
    list_display = ("customer", "business", "original_amount", "total_paid", "status")
    list_filter = ("status", "business")
    search_fields = ("customer__name",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("receivable", "amount", "method", "paid_at")
    list_filter = ("method", "business")
