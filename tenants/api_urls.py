from django.urls import path

from tenants.views import TenantRegisterAPIView

app_name = "tenants_api"

urlpatterns = [
    path("tenants/register/", TenantRegisterAPIView.as_view(), name="tenant_register"),
]
