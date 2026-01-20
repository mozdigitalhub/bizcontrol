def current_business(request):
    return {
        "current_business": getattr(request, "business", None),
        "nav_groups": {
            "sales": ["sales", "deliveries", "quotations"],
            "customers": ["customers", "receivables"],
            "products": ["catalog", "inventory"],
            "billing": ["billing"],
            "finance": ["finance"],
            "settings": ["tenants"],
        },
    }
