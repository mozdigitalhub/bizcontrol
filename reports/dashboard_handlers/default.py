from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from catalog.models import Product
from customers.models import Customer
from receivables.models import Receivable
from sales.models import Sale

from reports.dashboard_handlers.base import BusinessTypeHandler
from reports.dashboard_handlers.types import DashboardModule


class DefaultHandler(BusinessTypeHandler):
    key = "default"
    template_name = "reports/dashboards/default.html"

    def supports(self, business_type):
        return True

    def get_modules(self, request):
        modules = [
            DashboardModule(
                key="dashboard",
                title="Relatorios",
                description="Visao geral e tendencias",
                url_name="reports:overview",
                permission="reports.view_basic",
            ),
            DashboardModule(
                key="operations",
                title="Operacoes",
                description="Registos e fluxo diario",
                url_name="sales:list",
                permission="sales.view_sale",
            ),
        ]
        if request.business.module_catalog_enabled:
            modules.append(
                DashboardModule(
                    key="catalog",
                    title=request.business.ui_labels.get("products", "Produtos"),
                    description="Registo e consulta de catalogo",
                    url_name="catalog:product_list",
                    permission="catalog.view_product",
                )
            )
        if request.business.module_cashflow_enabled:
            modules.append(
                DashboardModule(
                    key="finance",
                    title="Financeiro",
                    description="Fluxo de caixa e despesas",
                    url_name="finance:cashflow_list",
                    permission="finance.view_cashmovement",
                )
            )
        return modules

    def get_dashboard_config(self, request):
        return {
            "domain": "generic",
            "layout": "modular",
            "focus": ["overview", "operations"],
            "enabled_modules": request.business.get_module_flags(),
            "feature_flags": request.business.get_feature_flags(),
        }

    def build_context(self, request):
        today = timezone.localdate()
        sales_today = (
            Sale.objects.filter(
                business=request.business,
                status=Sale.STATUS_CONFIRMED,
                sale_date__date=today,
            )
            .aggregate(total=Coalesce(Sum("total"), Decimal("0")))
            .get("total")
        )
        open_receivables = (
            Receivable.objects.filter(
                business=request.business,
                status=Receivable.STATUS_OPEN,
            )
            .aggregate(total=Coalesce(Sum("original_amount"), Decimal("0")))
            .get("total")
        )
        return {
            "sales_today": sales_today,
            "open_receivables": open_receivables,
            "sales_count_today": Sale.objects.filter(
                business=request.business,
                status=Sale.STATUS_CONFIRMED,
                sale_date__date=today,
            ).count(),
            "product_count": Product.objects.filter(business=request.business).count(),
            "customer_count": Customer.objects.filter(business=request.business).count(),
            "business_labels": request.business.ui_labels,
        }
