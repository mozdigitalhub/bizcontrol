"""
URL configuration for bizcontrol project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("tenants/", include(("tenants.urls", "tenants"), namespace="tenants")),
    path("api/v1/", include(("tenants.api_urls", "tenants_api"), namespace="api_v1")),
    path("", include(("reports.urls", "reports"), namespace="reports")),
    path("products/", include(("catalog.urls", "catalog"), namespace="catalog")),
    path("inventory/", include(("inventory.urls", "inventory"), namespace="inventory")),
    path("customers/", include(("customers.urls", "customers"), namespace="customers")),
    path("sales/", include(("sales.urls", "sales"), namespace="sales")),
    path("quotations/", include(("quotations.urls", "quotations"), namespace="quotations")),
    path("deliveries/", include(("deliveries.urls", "deliveries"), namespace="deliveries")),
    path("receivables/", include(("receivables.urls", "receivables"), namespace="receivables")),
    path("billing/", include(("billing.urls", "billing"), namespace="billing")),
    path("finance/", include(("finance.urls", "finance"), namespace="finance")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
