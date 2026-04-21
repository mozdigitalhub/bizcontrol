from decimal import Decimal

from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from billing.models import Receipt
from catalog.models import Product, ProductVariant
from inventory.services import get_stock_snapshot_by_product_ids
from sales.models import Sale, SaleItem
from tenants.models import Business

from reports.dashboard_handlers.base import BusinessTypeHandler
from reports.dashboard_handlers.types import DashboardModule


class RetailHandler(BusinessTypeHandler):
    key = "retail"
    supported_business_types = (
        Business.BUSINESS_CLOTHING,
        Business.BUSINESS_GROCERY,
        Business.BUSINESS_MINI_GROCERY,
        Business.BUSINESS_ALCOHOL,
    )
    template_name = "reports/dashboards/retail.html"

    def get_modules(self, request):
        return [
            DashboardModule(
                key="catalog",
                title=request.business.ui_labels.get("products", "Produtos"),
                description="Catalogo e variacoes",
                url_name="catalog:product_list",
                permission="catalog.view_product",
            ),
            DashboardModule(
                key="inventory",
                title="Inventario",
                description="Reposicao e alertas de stock",
                url_name="inventory:stock_list",
                permission="inventory.view_stockmovement",
            ),
            DashboardModule(
                key="sales",
                title="Vendas",
                description="Vendas e comprovativos",
                url_name="sales:list",
                permission="sales.view_sale",
            ),
            DashboardModule(
                key="receipts",
                title="Recibos",
                description="Historico de recebimentos",
                url_name="billing:receipt_list",
                permission="billing.view_receipt",
            ),
        ]

    def get_dashboard_config(self, request):
        return {
            "domain": "retail",
            "layout": "catalog-led",
            "focus": ["product_variations", "inventory_alerts", "receipts"],
            "uses_variants": request.business.feature_enabled(Business.FEATURE_USE_VARIANTS),
        }

    def build_context(self, request):
        business = request.business
        today = timezone.localdate()
        sales_today = (
            Sale.objects.filter(
                business=business,
                status=Sale.STATUS_CONFIRMED,
                sale_date__date=today,
            )
            .aggregate(total=Coalesce(Sum("total"), Decimal("0")))
            .get("total")
        )

        products = list(Product.objects.filter(business=business))
        product_ids = [product.id for product in products]
        stock_snapshot = get_stock_snapshot_by_product_ids(business, product_ids)
        low_stock_products = []
        estimated_stock_value = Decimal("0")
        for product in products:
            current_stock = stock_snapshot.get(product.id, 0)
            estimated_stock_value += Decimal(product.cost_price or 0) * Decimal(current_stock)
            if (
                product.reorder_level is not None
                and current_stock <= int(product.reorder_level)
            ):
                low_stock_products.append(
                    {
                        "name": product.name,
                        "stock": current_stock,
                        "reorder_level": product.reorder_level,
                    }
                )

        low_stock_variants = ProductVariant.objects.filter(
            product__business=business,
            is_active=True,
            reorder_level__isnull=False,
            stock_qty__lte=F("reorder_level"),
        )

        top_products = (
            SaleItem.objects.filter(
                sale__business=business,
                sale__status=Sale.STATUS_CONFIRMED,
            )
            .values("product__name")
            .annotate(total=Coalesce(Sum("line_total"), Decimal("0")))
            .order_by("-total")[:6]
        )

        return {
            "sales_today": sales_today,
            "sales_today_count": Sale.objects.filter(
                business=business,
                status=Sale.STATUS_CONFIRMED,
                sale_date__date=today,
            ).count(),
            "receipts_today_count": Receipt.objects.filter(
                business=business,
                issue_date=today,
            ).count(),
            "product_count": len(products),
            "variant_count": ProductVariant.objects.filter(
                product__business=business, is_active=True
            ).count(),
            "low_stock_products": low_stock_products[:8],
            "low_stock_products_count": len(low_stock_products),
            "low_stock_variants_count": low_stock_variants.count(),
            "estimated_stock_value": estimated_stock_value,
            "top_products": top_products,
        }
