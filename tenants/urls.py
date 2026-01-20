from django.urls import path

from tenants import views

app_name = "tenants"

urlpatterns = [
    path("select/", views.select_business, name="select_business"),
    path("settings/", views.business_settings, name="settings"),
    path("settings/wallets/new/", views.tenant_wallet_create, name="wallet_create"),
    path("settings/wallets/<int:wallet_id>/edit/", views.tenant_wallet_edit, name="wallet_edit"),
    path("settings/banks/new/", views.tenant_bank_create, name="bank_create"),
    path("settings/banks/<int:bank_id>/edit/", views.tenant_bank_edit, name="bank_edit"),
    path("settings/payments/<str:kind>/<int:pk>/delete/", views.tenant_payment_delete, name="payment_delete"),
]
