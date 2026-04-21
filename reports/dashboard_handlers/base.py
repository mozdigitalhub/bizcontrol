from abc import ABC, abstractmethod

from django.shortcuts import render

from tenants.models import Business

from reports.dashboard_handlers.types import DashboardNavigationProfile


class BusinessTypeHandler(ABC):
    key = "default"
    supported_business_types = ()
    template_name = "reports/dashboards/default.html"

    def supports(self, business_type):
        return business_type in self.supported_business_types

    def get_navigation_profile(self, business):
        use_food_operations = bool(
            business.feature_enabled(Business.FEATURE_USE_KITCHEN_DISPLAY)
            and business.feature_enabled(Business.FEATURE_USE_RECIPES)
        )
        return DashboardNavigationProfile(
            use_food_operations=use_food_operations,
            show_customer_credit=not use_food_operations,
            show_billing=not use_food_operations,
            show_finance=bool(business.module_cashflow_enabled) and not use_food_operations,
            show_food_tables=use_food_operations
            and business.feature_enabled(Business.FEATURE_USE_TABLES),
            products_section_title="Menu & Ingredientes"
            if use_food_operations
            else "Produtos & Stock",
        )

    def get_modules(self, request):
        return []

    def get_dashboard_config(self, request):
        return {}

    @abstractmethod
    def build_context(self, request):
        raise NotImplementedError

    def render_dashboard(self, request):
        context = self.build_context(request)
        context.setdefault("dashboard_modules", self.get_modules(request))
        context.setdefault("dashboard_config", self.get_dashboard_config(request))
        context.setdefault("dashboard_handler_key", self.key)
        return render(request, self.template_name, context)
