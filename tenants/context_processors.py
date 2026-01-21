def current_business(request):
    return {
        "current_business": getattr(request, "business", None),
        "current_membership": getattr(request, "membership", None),
        "tenant_permissions": getattr(request, "tenant_permissions", set()),
        "nav_groups": {
            "sales": ["sales", "deliveries", "quotations"],
            "customers": ["customers", "receivables"],
            "products": ["catalog", "inventory"],
            "billing": ["billing"],
            "finance": ["finance"],
            "reports": ["reports"],
            "settings": ["tenants"],
        },
    }
