from django.db.models import ExpressionWrapper, F, IntegerField, Sum, Value
from django.db.models.functions import Coalesce

from sales.models import Sale, SaleItem


def get_product_sales_history(*, business, limit=None):
    qty_expr = ExpressionWrapper(
        F("quantity") - Coalesce(F("returned_quantity"), Value(0)),
        output_field=IntegerField(),
    )
    qs = (
        SaleItem.objects.filter(
            sale__business=business, sale__status=Sale.STATUS_CONFIRMED
        )
        .values("product_id", "product__name")
        .annotate(total_qty=Coalesce(Sum(qty_expr), Value(0)))
        .order_by("-total_qty", "product__name")
    )
    if limit:
        qs = qs[:limit]
    return list(qs)
