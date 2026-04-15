from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import UserProfile
from accounts.services import reset_password_and_send_email

User = get_user_model()


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "phone",
        "must_change_password",
        "welcome_seen",
        "onboarding_completed",
        "updated_at",
    )
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")


def admin_reset_password_and_email(modeladmin, request, queryset):
    sent = 0
    failed = 0
    for user in queryset:
        ok, _ = reset_password_and_send_email(user=user, request=request)
        if ok:
            sent += 1
        else:
            failed += 1
    if sent:
        messages.success(
            request,
            f"Nova palavra-passe enviada por email para {sent} utilizador(es).",
        )
    if failed:
        messages.warning(
            request,
            f"{failed} utilizador(es) sem envio (sem email válido ou erro no envio).",
        )


admin_reset_password_and_email.short_description = (
    "Redefinir palavra-passe e enviar nova por email"
)


class BizControlUserAdmin(DjangoUserAdmin):
    actions = [admin_reset_password_and_email]


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, BizControlUserAdmin)
