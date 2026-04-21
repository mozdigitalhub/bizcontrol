from decimal import Decimal

from django.db.models import Count, F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from food.models import MenuCategory, MenuItem, Order, RestaurantTable
from tenants.models import Business

from reports.dashboard_handlers.base import BusinessTypeHandler
from reports.dashboard_handlers.types import DashboardModule


class RestaurantHandler(BusinessTypeHandler):
    key = "restaurant"
    supported_business_types = (
        Business.BUSINESS_RESTAURANT,
        Business.BUSINESS_BURGER,
    )
    template_name = "reports/dashboards/restaurant.html"

    def get_modules(self, request):
        modules = [
            DashboardModule(
                key="orders",
                title="Pedidos",
                description="Gestao de pedidos por canal",
                url_name="food:order_list",
                permission="food.view_order",
            ),
            DashboardModule(
                key="kds",
                title="Cozinha",
                description="Fluxo da cozinha em tempo real",
                url_name="food:kds",
                permission="food.view_order",
            ),
            DashboardModule(
                key="menu",
                title="Menu",
                description="Categorias e precos dos itens",
                url_name="food:menu_list",
                permission="food.view_menuitem",
            ),
            DashboardModule(
                key="ingredients",
                title="Ingredientes",
                description="Stock de ingredientes e reposicao",
                url_name="food:ingredient_list",
                permission="food.view_foodingredient",
            ),
        ]
        if request.business.feature_enabled(Business.FEATURE_USE_TABLES):
            modules.insert(
                1,
                DashboardModule(
                    key="tables",
                    title="Mesas",
                    description="Estado de ocupacao e reservas",
                    url_name="food:table_list",
                    permission="food.view_restauranttable",
                ),
            )
        return modules

    def get_dashboard_config(self, request):
        return {
            "domain": "restaurant",
            "layout": "service-floor",
            "workflow_status_map": {
                "pending": Order.STATUS_CONFIRMED,
                "preparing": Order.STATUS_IN_PREPARATION,
                "ready": Order.STATUS_READY,
                "served": Order.STATUS_DELIVERED,
            },
            "uses_tables": request.business.feature_enabled(Business.FEATURE_USE_TABLES),
        }

    def build_context(self, request):
        business = request.business
        today = timezone.localdate()
        orders = Order.objects.filter(business=business)
        today_orders = orders.filter(created_at__date=today).exclude(
            status=Order.STATUS_CANCELED
        )
        sales_today = today_orders.aggregate(total=Coalesce(Sum("total"), Decimal("0"))).get(
            "total"
        )
        orders_today_count = today_orders.count()

        kitchen_counts = {
            "pending": orders.filter(status=Order.STATUS_CONFIRMED).count(),
            "preparing": orders.filter(status=Order.STATUS_IN_PREPARATION).count(),
            "ready": orders.filter(status=Order.STATUS_READY).count(),
            "served": orders.filter(status=Order.STATUS_DELIVERED).count(),
        }

        active_orders = (
            orders.filter(
                status__in=[
                    Order.STATUS_CONFIRMED,
                    Order.STATUS_IN_PREPARATION,
                    Order.STATUS_READY,
                ]
            )
            .select_related("table", "customer")
            .order_by("created_at")
        )

        table_counts = {
            RestaurantTable.STATUS_FREE: 0,
            RestaurantTable.STATUS_OCCUPIED: 0,
            RestaurantTable.STATUS_RESERVED: 0,
        }
        if business.feature_enabled(Business.FEATURE_USE_TABLES):
            for row in (
                RestaurantTable.objects.filter(business=business, is_active=True)
                .values("status")
                .annotate(total=Count("id"))
            ):
                table_counts[row["status"]] = row["total"]

        low_ingredients = (
            business.food_ingredients.filter(
                is_active=True,
                reorder_level__isnull=False,
                stock_qty__lte=F("reorder_level"),
            ).count()
            if hasattr(business, "food_ingredients")
            else 0
        )

        return {
            "sales_today": sales_today,
            "orders_today_count": orders_today_count,
            "average_ticket": (sales_today / orders_today_count)
            if orders_today_count
            else Decimal("0"),
            "kitchen_counts": kitchen_counts,
            "tables_count": table_counts,
            "menu_item_count": MenuItem.objects.filter(business=business, is_active=True).count(),
            "menu_category_count": MenuCategory.objects.filter(
                business=business, is_active=True
            ).count(),
            "low_ingredient_alerts": low_ingredients,
            "active_orders": active_orders[:8],
            "use_tables": business.feature_enabled(Business.FEATURE_USE_TABLES),
        }
