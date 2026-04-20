from django.conf import settings

from accounts.models import UserProfile


def current_business(request):
    profile = None
    if getattr(request, "user", None) and request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return {
        "current_business": getattr(request, "business", None),
        "current_membership": getattr(request, "membership", None),
        "tenant_permissions": getattr(request, "tenant_permissions", set()),
        "user_profile": profile,
        "session_inactivity_timeout": getattr(
            settings, "SESSION_INACTIVITY_TIMEOUT", 0
        ),
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
