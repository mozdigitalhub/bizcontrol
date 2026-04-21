from dataclasses import asdict

from django.conf import settings

from accounts.models import UserProfile
from reports.dashboard_handlers import DashboardFactory


def _default_dashboard_navigation():
    return {
        "use_food_operations": False,
        "show_customer_credit": True,
        "show_billing": True,
        "show_finance": True,
        "show_food_tables": False,
        "products_section_title": "Produtos & Stock",
    }


def current_business(request):
    profile = None
    dashboard_navigation = _default_dashboard_navigation()
    dashboard_handler_key = "default"
    if getattr(request, "user", None) and request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
    business = getattr(request, "business", None)
    if business:
        handler = DashboardFactory.get_dashboard(business.business_type)
        dashboard_handler_key = handler.key
        dashboard_navigation = asdict(handler.get_navigation_profile(business))
    return {
        "current_business": business,
        "current_membership": getattr(request, "membership", None),
        "tenant_permissions": getattr(request, "tenant_permissions", set()),
        "user_profile": profile,
        "session_inactivity_timeout": getattr(
            settings, "SESSION_INACTIVITY_TIMEOUT", 0
        ),
        "dashboard_handler_key": dashboard_handler_key,
        "dashboard_navigation": dashboard_navigation,
        "nav_groups": {
            "sales": ["sales", "deliveries", "quotations", "food"],
            "customers": ["customers", "receivables"],
            "products": ["catalog", "inventory"],
            "billing": ["billing"],
            "finance": ["finance"],
            "reports": ["reports"],
            "settings": ["tenants"],
        },
    }
