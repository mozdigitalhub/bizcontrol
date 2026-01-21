from datetime import date, timedelta

from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, IntegerField, Sum, Value, When
from django.db.models.functions import Coalesce, TruncDay, TruncMonth
from django.utils import timezone

from finance.models import CashMovement
from catalog.models import Product
from inventory.models import StockMovement
from receivables.models import Receivable
from sales.models import Sale, SaleItem


MONTH_LABELS = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
]


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


def get_date_range(*, date_from=None, date_to=None, preset=None, default_days=30):
    today = timezone.localdate()
    if preset == "today":
        return today, today
    if preset == "7d":
        return today - timedelta(days=6), today
    if preset == "30d":
        return today - timedelta(days=29), today
    if preset == "month":
        return today.replace(day=1), today
    if preset == "year":
        return date(today.year, 1, 1), today
    if not date_to:
        date_to = today
    if not date_from:
        date_from = date_to - timedelta(days=default_days - 1)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    return date_from, date_to


def _month_sequence(start_date, end_date):
    current = date(start_date.year, start_date.month, 1)
    end = date(end_date.year, end_date.month, 1)
    months = []
    while current <= end:
        months.append(current)
        year = current.year + (current.month // 12)
        month = (current.month % 12) + 1
        current = date(year, month, 1)
    return months


def _day_sequence(start_date, end_date):
    days = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)
    return days


def build_time_series(*, data, date_from, date_to, granularity):
    if granularity == "yearly":
        periods = _month_sequence(date_from, date_to)
        labels = [MONTH_LABELS[item.month - 1] for item in periods]
    elif granularity == "monthly":
        periods = _month_sequence(date_from, date_to)
        labels = [f"{MONTH_LABELS[item.month - 1]} {item.year}" for item in periods]
    else:
        periods = _day_sequence(date_from, date_to)
        labels = [item.strftime("%d/%m") for item in periods]
    values = [data.get(item, 0) for item in periods]
    return labels, values


def get_sales_series(*, business, date_from, date_to, granularity):
    qs = Sale.objects.filter(
        business=business,
        status=Sale.STATUS_CONFIRMED,
        sale_date__date__gte=date_from,
        sale_date__date__lte=date_to,
    )
    trunc = TruncMonth("sale_date") if granularity in ("monthly", "yearly") else TruncDay("sale_date")
    rows = (
        qs.annotate(period=trunc)
        .values("period")
        .annotate(total=Coalesce(Sum("total"), Value(0, output_field=DecimalField())))
        .order_by("period")
    )
    data_map = {row["period"].date(): float(row["total"]) for row in rows}
    labels, values = build_time_series(
        data=data_map, date_from=date_from, date_to=date_to, granularity=granularity
    )
    return labels, values


def get_sales_summary(*, business, date_from, date_to):
    qs = Sale.objects.filter(
        business=business,
        status=Sale.STATUS_CONFIRMED,
        sale_date__date__gte=date_from,
        sale_date__date__lte=date_to,
    )
    totals = qs.aggregate(
        total=Coalesce(Sum("total"), Value(0, output_field=DecimalField())),
        count=Coalesce(Count("id"), Value(0, output_field=IntegerField())),
    )
    total = totals["total"]
    count = totals["count"]
    ticket = float(total / count) if count else 0
    return {"total": float(total), "count": count, "ticket": ticket}


def get_payment_breakdown(*, business, date_from, date_to):
    qs = CashMovement.objects.filter(
        business=business,
        movement_type=CashMovement.MOVEMENT_IN,
        happened_at__date__gte=date_from,
        happened_at__date__lte=date_to,
    )
    rows = (
        qs.values("method")
        .annotate(
            total=Coalesce(Sum("amount"), Value(0, output_field=DecimalField())),
            count=Coalesce(Count("id"), Value(0, output_field=IntegerField())),
        )
        .order_by("-total")
    )
    labels = {key: label for key, label in CashMovement.METHOD_CHOICES}
    data = []
    for row in rows:
        method = row["method"]
        data.append(
            {
                "method": method,
                "label": labels.get(method, method),
                "total": float(row["total"]),
                "count": row["count"],
            }
        )
    return data


def get_cashflow_series(*, business, date_from, date_to, granularity):
    qs = CashMovement.objects.filter(
        business=business,
        happened_at__date__gte=date_from,
        happened_at__date__lte=date_to,
    )
    trunc = TruncMonth("happened_at") if granularity in ("monthly", "yearly") else TruncDay("happened_at")
    rows = (
        qs.annotate(period=trunc)
        .values("period")
        .annotate(
            total_in=Coalesce(
                Sum(
                    Case(
                        When(movement_type=CashMovement.MOVEMENT_IN, then=F("amount")),
                        default=Value(0),
                        output_field=DecimalField(),
                    )
                ),
                Value(0, output_field=DecimalField()),
            ),
            total_out=Coalesce(
                Sum(
                    Case(
                        When(movement_type=CashMovement.MOVEMENT_OUT, then=F("amount")),
                        default=Value(0),
                        output_field=DecimalField(),
                    )
                ),
                Value(0, output_field=DecimalField()),
            ),
        )
        .order_by("period")
    )
    in_map = {row["period"].date(): float(row["total_in"]) for row in rows}
    out_map = {row["period"].date(): float(row["total_out"]) for row in rows}
    labels, in_values = build_time_series(
        data=in_map, date_from=date_from, date_to=date_to, granularity=granularity
    )
    _, out_values = build_time_series(
        data=out_map, date_from=date_from, date_to=date_to, granularity=granularity
    )
    return labels, in_values, out_values


def get_stock_summary(*, business):
    movements = (
        StockMovement.objects.filter(business=business)
        .values("product_id")
        .annotate(
            qty_in=Coalesce(
                Sum(
                    Case(
                        When(movement_type=StockMovement.MOVEMENT_IN, then=F("quantity")),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                Value(0, output_field=IntegerField()),
            ),
            qty_out=Coalesce(
                Sum(
                    Case(
                        When(movement_type=StockMovement.MOVEMENT_OUT, then=F("quantity")),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                Value(0, output_field=IntegerField()),
            ),
            qty_adjust=Coalesce(
                Sum(
                    Case(
                        When(movement_type=StockMovement.MOVEMENT_ADJUST, then=F("quantity")),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                Value(0, output_field=IntegerField()),
            ),
        )
    )
    movement_map = {
        row["product_id"]: {
            "qty_in": row["qty_in"],
            "qty_out": row["qty_out"],
            "qty_adjust": row["qty_adjust"],
        }
        for row in movements
    }
    product_rows = Product.objects.filter(business=business).values(
        "id", "name", "cost_price", "reorder_level"
    )
    products = []
    low_stock = []
    for product in product_rows:
        summary = movement_map.get(
            product["id"], {"qty_in": 0, "qty_out": 0, "qty_adjust": 0}
        )
        qty = int(summary["qty_in"]) - int(summary["qty_out"]) + int(
            summary["qty_adjust"]
        )
        cost = float(product["cost_price"] or 0)
        value = qty * cost
        data = {
            "product_id": product["id"],
            "name": product["name"],
            "quantity": qty,
            "reorder_level": product["reorder_level"],
            "stock_value": value,
        }
        products.append(data)
        if product["reorder_level"] is not None and qty <= product["reorder_level"]:
            low_stock.append(data)
    return products, low_stock


def get_receivables_aging(*, business):
    today = timezone.localdate()
    receivables = (
        Receivable.objects.filter(business=business, status=Receivable.STATUS_OPEN)
        .select_related("customer")
        .order_by("-created_at")
    )
    buckets = {"0-7": 0, "8-30": 0, "31-60": 0, "61+": 0}
    rows = []
    for receivable in receivables:
        balance = float(receivable.balance)
        days = (today - receivable.created_at.date()).days
        if days <= 7:
            bucket = "0-7"
        elif days <= 30:
            bucket = "8-30"
        elif days <= 60:
            bucket = "31-60"
        else:
            bucket = "61+"
        buckets[bucket] += balance
        rows.append(
            {
                "customer": receivable.customer.name,
                "balance": balance,
                "days": days,
                "created_at": receivable.created_at,
            }
        )
    return buckets, rows
