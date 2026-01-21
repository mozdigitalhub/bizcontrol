from django.contrib import admin

from tenants.models import (
    Business,
    BusinessMembership,
    TenantBankAccount,
    TenantMobileWallet,
    TenantRole,
)


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "business_type",
        "vat_enabled",
        "vat_rate",
        "prices_include_vat",
    )
    search_fields = ("name", "slug", "nuit", "phone", "email")
    list_filter = ("business_type", "vat_enabled")


@admin.register(BusinessMembership)
class BusinessMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "business", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("user__username", "user__email", "business__name")


@admin.register(TenantMobileWallet)
class TenantMobileWalletAdmin(admin.ModelAdmin):
    list_display = ("business", "wallet_type", "phone_number", "is_active")
    list_filter = ("wallet_type", "is_active", "business")


@admin.register(TenantBankAccount)
class TenantBankAccountAdmin(admin.ModelAdmin):
    list_display = ("business", "bank_name", "account_number", "is_active")
    list_filter = ("is_active", "business")


@admin.register(TenantRole)
class TenantRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "code", "is_active")
    list_filter = ("code", "is_active", "business")
    search_fields = ("name", "business__name")
