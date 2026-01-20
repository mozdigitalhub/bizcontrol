from django.contrib import admin

from customers.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "phone", "email")
    search_fields = ("name", "phone", "email")

