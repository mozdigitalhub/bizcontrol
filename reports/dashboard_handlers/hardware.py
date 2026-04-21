from datetime import date, timedelta
from decimal import Decimal

from django.db.models import F, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from catalog.models import Product
from customers.models import Customer
from inventory.services import get_stock_snapshot_by_product_ids
from receivables.models import Payment, Receivable
from reports.services import MONTH_LABELS
from sales.models import Sale, SaleItem
from tenants.models import Business

from reports.dashboard_handlers.base import BusinessTypeHandler
from reports.dashboard_handlers.types import DashboardModule


class HardwareHandler(BusinessTypeHandler):
    key = "hardware"
    supported_business_types = (Business.BUSINESS_HARDWARE,)
    template_name = "reports/dashboard.html"

    def get_modules(self, request):
        return [
            DashboardModule(
                key="sales",
                title="Vendas",
                description="Fluxo de vendas e pedidos",
                url_name="sales:list",
                permission="sales.view_sale",
            ),
            DashboardModule(
                key="billing",
                title="Faturacao",
                description="Faturas, recibos e documentos",
                url_name="billing:invoice_list",
                permission="billing.view_invoice",
            ),
            DashboardModule(
                key="inventory",
                title="Stock",
                description="Inventario e reposicao",
                url_name="inventory:stock_list",
                permission="inventory.view_stockmovement",
            ),
        ]

    def get_dashboard_config(self, request):
        return {
            "domain": "hardware",
            "layout": "classic-executive",
            "focus": ["sales", "receivables", "inventory"],
        }

    def build_context(self, request):
        today = timezone.now().date()
        start_of_today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        sales_today = (
            Sale.objects.filter(
                business=request.business,
                status=Sale.STATUS_CONFIRMED,
                sale_date__date=today,
            )
            .aggregate(total=Coalesce(Sum("total"), Decimal("0")))
            .get("total")
        )

        receivable_open = (
            Receivable.objects.filter(
                business=request.business, status=Receivable.STATUS_OPEN
            )
            .aggregate(
                total=Coalesce(
                    Sum(F("original_amount") - F("total_paid")),
                    Decimal("0"),
                )
            )
            .get("total")
        )

        tracked_products = list(
            Product.objects.filter(
                business=request.business, reorder_level__isnull=False
            ).values("id", "reorder_level")
        )
        tracked_product_ids = [item["id"] for item in tracked_products]
        stock_snapshot = get_stock_snapshot_by_product_ids(
            request.business, tracked_product_ids
        )
        low_stock_count = sum(
            1
            for item in tracked_products
            if stock_snapshot.get(item["id"], 0) <= item["reorder_level"]
        )

        product_count = Product.objects.filter(business=request.business).count()
        customer_count = Customer.objects.filter(business=request.business).count()
        sales_count = Sale.objects.filter(
            business=request.business, status=Sale.STATUS_CONFIRMED
        ).count()

        receivable_totals = Receivable.objects.filter(business=request.business).aggregate(
            original_total=Coalesce(Sum("original_amount"), Decimal("0")),
            paid_total=Coalesce(Sum("total_paid"), Decimal("0")),
        )
        receivable_total = receivable_totals["original_total"]
        receivable_paid = receivable_totals["paid_total"]
        receivable_open_total = receivable_total - receivable_paid
        receivable_ratio = (
            float(receivable_paid / receivable_total) if receivable_total else 0.0
        )
        receivable_ratio_pct = int(receivable_ratio * 100)

        top_customers_qs = (
            Receivable.objects.filter(business=request.business, status=Receivable.STATUS_OPEN)
            .values("customer__name")
            .annotate(
                balance=Coalesce(
                    Sum(F("original_amount") - F("total_paid")),
                    Decimal("0"),
                )
            )
            .order_by("-balance")[:5]
        )
        max_customer_balance = max(
            [item["balance"] for item in top_customers_qs], default=Decimal("0")
        )
        top_customers = []
        for item in top_customers_qs:
            percent = (
                float(item["balance"] / max_customer_balance) * 100
                if max_customer_balance
                else 0
            )
            top_customers.append(
                {
                    "name": item["customer__name"],
                    "balance": item["balance"],
                    "percent": percent,
                }
            )

        top_products_qs = (
            SaleItem.objects.filter(
                sale__business=request.business, sale__status=Sale.STATUS_CONFIRMED
            )
            .values("product__name")
            .annotate(total=Coalesce(Sum("line_total"), Decimal("0")))
            .order_by("-total")[:5]
        )
        max_product_total = max(
            [item["total"] for item in top_products_qs], default=Decimal("0")
        )
        top_products = []
        for item in top_products_qs:
            percent = (
                float(item["total"] / max_product_total) * 100 if max_product_total else 0
            )
            top_products.append(
                {
                    "name": item["product__name"],
                    "total": item["total"],
                    "percent": percent,
                }
            )

        start_month = (start_of_today.replace(day=1) - timedelta(days=150)).date()
        sales_monthly = (
            Sale.objects.filter(
                business=request.business,
                status=Sale.STATUS_CONFIRMED,
                sale_date__date__gte=start_month,
            )
            .annotate(month=TruncMonth("sale_date"))
            .values("month")
            .annotate(total=Coalesce(Sum("total"), Decimal("0")))
        )
        payments_monthly = (
            Payment.objects.filter(
                business=request.business,
                paid_at__date__gte=start_month,
            )
            .annotate(month=TruncMonth("paid_at"))
            .values("month")
            .annotate(total=Coalesce(Sum("amount"), Decimal("0")))
        )

        month_map_sales = {item["month"].date(): item["total"] for item in sales_monthly}
        month_map_pay = {item["month"].date(): item["total"] for item in payments_monthly}

        def month_sequence(end_date, months=6):
            months_list = []
            year = end_date.year
            month = end_date.month
            for _ in range(months):
                months_list.append(date(year, month, 1))
                month -= 1
                if month == 0:
                    month = 12
                    year -= 1
            return list(reversed(months_list))

        months = month_sequence(today, 6)
        sales_values = [month_map_sales.get(m, Decimal("0")) for m in months]
        payment_values = [month_map_pay.get(m, Decimal("0")) for m in months]
        max_value = max(sales_values + payment_values + [Decimal("1")])

        def build_points(values):
            points = []
            count = len(values) - 1 or 1
            for index, value in enumerate(values):
                x = (index / count) * 100
                y = 90 - (float(value) / float(max_value)) * 70
                points.append(f"{x:.1f},{y:.1f}")
            return " ".join(points)

        return {
            "sales_today": sales_today,
            "receivable_open": receivable_open,
            "low_stock_count": low_stock_count,
            "product_count": product_count,
            "customer_count": customer_count,
            "sales_count": sales_count,
            "receivable_total": receivable_total,
            "receivable_paid": receivable_paid,
            "receivable_open_total": receivable_open_total,
            "receivable_ratio": receivable_ratio,
            "receivable_ratio_pct": receivable_ratio_pct,
            "top_customers": top_customers,
            "top_products": top_products,
            "sales_points": build_points(sales_values),
            "payment_points": build_points(payment_values),
            "month_labels": [MONTH_LABELS[m.month - 1] for m in months],
        }
