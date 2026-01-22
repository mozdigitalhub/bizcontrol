from django.urls import path

from tenants import views

app_name = "tenants"

urlpatterns = [
    path("select/", views.select_business, name="select_business"),
    path("profile/", views.business_profile, name="business_profile"),
    path("payments/", views.tenant_payment_data, name="payment_data"),
    path("me/", views.user_profile, name="user_profile"),
    path("password/force/", views.force_password_change, name="force_password_change"),
    path("onboarding/welcome/", views.onboarding_welcome_seen, name="onboarding_welcome"),
    path("onboarding/complete/", views.onboarding_complete, name="onboarding_complete"),
    path("approvals/", views.tenant_approvals, name="tenant_approvals"),
    path("approvals/<int:business_id>/approve/", views.tenant_approve, name="tenant_approve"),
    path("approvals/<int:business_id>/reject/", views.tenant_reject, name="tenant_reject"),
    path("system-settings/", views.system_settings, name="system_settings"),
    path("settings/wallets/new/", views.tenant_wallet_create, name="wallet_create"),
    path("settings/wallets/<int:wallet_id>/edit/", views.tenant_wallet_edit, name="wallet_edit"),
    path("settings/banks/new/", views.tenant_bank_create, name="bank_create"),
    path("settings/banks/<int:bank_id>/edit/", views.tenant_bank_edit, name="bank_edit"),
    path("settings/payments/<str:kind>/<int:pk>/delete/", views.tenant_payment_delete, name="payment_delete"),
    path("staff/", views.staff_list, name="staff_list"),
    path("staff/new/", views.staff_create, name="staff_create"),
    path("staff/<int:membership_id>/edit/", views.staff_edit, name="staff_edit"),
    path("staff/<int:membership_id>/toggle/", views.staff_toggle, name="staff_toggle"),
    path("roles/", views.roles_permissions, name="roles"),
]
