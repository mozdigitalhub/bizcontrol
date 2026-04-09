from django.contrib import admin

from superadmin.models import (
    PlatformAlert,
    PlatformSetting,
    SubscriptionPlan,
    SuperAdminAuditLog,
    SupportTicket,
    TenantAdminNote,
    TenantStatusHistory,
    TenantSubscription,
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "price_monthly", "trial_days", "is_active", "is_default")
    list_filter = ("is_active", "is_default", "billing_cycle_months")
    search_fields = ("name", "code")


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("business", "plan", "status", "ends_at", "payment_proof_status", "updated_at")
    list_filter = ("status", "payment_proof_status", "auto_renew")
    search_fields = ("business__name", "business__slug", "payment_reference")


@admin.register(TenantAdminNote)
class TenantAdminNoteAdmin(admin.ModelAdmin):
    list_display = ("business", "note_type", "created_by", "created_at")
    list_filter = ("note_type",)
    search_fields = ("business__name", "note")


@admin.register(TenantStatusHistory)
class TenantStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("business", "previous_status", "new_status", "changed_by", "changed_at")
    list_filter = ("previous_status", "new_status")
    search_fields = ("business__name", "reason")


@admin.register(SuperAdminAuditLog)
class SuperAdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "business", "target_type", "target_id")
    list_filter = ("action", "target_type")
    search_fields = ("action", "target_type", "target_id", "actor__username", "business__name")


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "is_public", "updated_by", "updated_at")
    list_filter = ("is_public",)
    search_fields = ("key", "description")


@admin.register(PlatformAlert)
class PlatformAlertAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "business", "is_active", "starts_at", "ends_at")
    list_filter = ("level", "is_active")
    search_fields = ("title", "message", "business__name")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("subject", "status", "business", "assigned_to", "created_at")
    list_filter = ("status",)
    search_fields = ("subject", "business__name", "message")
