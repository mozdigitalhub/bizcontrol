from django.urls import path

from superadmin import views

app_name = "superadmin"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("approvals/", views.tenant_approvals, name="tenant_approvals"),
    path("tenants/", views.tenant_list, name="tenant_list"),
    path("tenants/create/", views.tenant_create, name="tenant_create"),
    path("tenants/<int:business_id>/", views.tenant_detail, name="tenant_detail"),
    path(
        "tenants/<int:business_id>/status/",
        views.tenant_status_action,
        name="tenant_status_action",
    ),
    path(
        "tenants/<int:business_id>/extend-trial/",
        views.tenant_extend_trial,
        name="tenant_extend_trial",
    ),
    path(
        "tenants/<int:business_id>/extend-subscription/",
        views.tenant_extend_subscription,
        name="tenant_extend_subscription",
    ),
    path(
        "tenants/<int:business_id>/subscription/",
        views.tenant_subscription_update,
        name="tenant_subscription_update",
    ),
    path(
        "tenants/<int:business_id>/proof/",
        views.tenant_subscription_proof_action,
        name="tenant_subscription_proof_action",
    ),
    path(
        "tenants/<int:business_id>/notes/",
        views.tenant_add_note,
        name="tenant_add_note",
    ),
    path(
        "tenants/<int:business_id>/resend-pending-email/",
        views.tenant_resend_pending_email,
        name="tenant_resend_pending_email",
    ),
    path("subscriptions/", views.subscriptions, name="subscriptions"),
    path("plans/", views.plans, name="plans"),
    path("users/", views.users, name="users"),
    path("users/<int:user_id>/toggle/", views.user_toggle_active, name="user_toggle_active"),
    path("logs/", views.audit_logs, name="audit_logs"),
    path("settings/", views.settings_page, name="settings"),
    path("notifications/", views.notifications, name="notifications"),
]
