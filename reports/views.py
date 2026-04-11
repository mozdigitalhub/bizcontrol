import csv
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from catalog.models import Product
from customers.models import Customer
from inventory.services import get_product_stock
from receivables.models import Payment, Receivable
from sales.models import Sale, SaleItem
from tenants.decorators import business_required
from tenants.permissions import tenant_permission_required, user_has_tenant_permission
from reports.services import (
    MONTH_LABELS,
    get_cashflow_series,
    get_cashflow_snapshot,
    get_date_range,
    get_gross_margin_summary,
    get_pending_deposits_snapshot,
    get_payment_breakdown,
    get_receivables_aging,
    get_sales_series,
    get_sales_summary,
    get_stock_summary,
)


@login_required
@business_required
def dashboard(request):
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

    low_stock_count = 0
    products = Product.objects.filter(
        business=request.business, reorder_level__isnull=False
    )
    for product in products:
        current_stock = get_product_stock(request.business, product)
        if current_stock <= product.reorder_level:
            low_stock_count += 1

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

    context = {
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
    return render(request, "reports/dashboard.html", context)


def _export_csv(request, *, filename, headers, rows):
    if not user_has_tenant_permission(request, "reports.export"):
        messages.error(request, "Sem permissao para exportar relatorios.")
        return None
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


@login_required
@business_required
@tenant_permission_required("reports.view_basic")
def overview(request):
    preset = request.GET.get("preset") or ""
    date_from_raw = request.GET.get("date_from")
    date_to_raw = request.GET.get("date_to")
    if not preset and not date_from_raw and not date_to_raw:
        preset = "30d"
    date_from, date_to = get_date_range(
        date_from=_parse_date(date_from_raw),
        date_to=_parse_date(date_to_raw),
        preset=preset,
        default_days=30,
    )
    summary = get_sales_summary(
        business=request.business, date_from=date_from, date_to=date_to
    )
    period_days = (date_to - date_from).days + 1
    previous_date_to = date_from - timedelta(days=1)
    previous_date_from = previous_date_to - timedelta(days=period_days - 1)
    previous_summary = get_sales_summary(
        business=request.business,
        date_from=previous_date_from,
        date_to=previous_date_to,
    )

    summary_variation = {
        "sales_total": _build_variation(
            current=summary["total"], previous=previous_summary["total"]
        ),
        "transactions": _build_variation(
            current=summary["count"], previous=previous_summary["count"]
        ),
        "ticket": _build_variation(
            current=summary["ticket"], previous=previous_summary["ticket"]
        ),
    }

    gross_margin = get_gross_margin_summary(
        business=request.business, date_from=date_from, date_to=date_to
    )
    cashflow_snapshot = get_cashflow_snapshot(
        business=request.business, date_from=date_from, date_to=date_to
    )
    pending_deposits = get_pending_deposits_snapshot(business=request.business)

    labels, values = get_sales_series(
        business=request.business,
        date_from=date_from,
        date_to=date_to,
        granularity="daily",
    )
    payments = get_payment_breakdown(
        business=request.business, date_from=date_from, date_to=date_to
    )
    payment_labels = [item["label"] for item in payments]
    payment_values = [item["total"] for item in payments]

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "preset": preset,
        "summary": summary,
        "summary_variation": summary_variation,
        "previous_date_from": previous_date_from,
        "previous_date_to": previous_date_to,
        "gross_margin": gross_margin,
        "cashflow_snapshot": cashflow_snapshot,
        "pending_deposits": pending_deposits,
        "sales_labels": labels,
        "sales_values": values,
        "payments": payments,
        "labels": payment_labels,
        "values": payment_values,
    }
    return render(request, "reports/overview.html", context)


@login_required
@business_required
@tenant_permission_required("reports.view_basic")
def sales_report(request):
    preset = request.GET.get("preset") or ""
    date_from_raw = request.GET.get("date_from")
    date_to_raw = request.GET.get("date_to")
    granularity = request.GET.get("granularity") or "daily"
    date_from, date_to = get_date_range(
        date_from=_parse_date(date_from_raw),
        date_to=_parse_date(date_to_raw),
        preset=preset,
        default_days=30,
    )
    summary = get_sales_summary(
        business=request.business, date_from=date_from, date_to=date_to
    )
    labels, values = get_sales_series(
        business=request.business,
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
    )
    table_rows = [{"label": label, "value": value} for label, value in zip(labels, values)]
    period_blocks = _build_sales_period_blocks(
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
        labels=labels,
        values=values,
    )

    if request.GET.get("export") == "csv":
        rows = []
        for label, value in zip(labels, values):
            rows.append([label, f"{value:.2f}"])
        response = _export_csv(
            request,
            filename="relatorio_vendas.csv",
            headers=["Periodo", "Total"],
            rows=rows,
        )
        if response:
            return response

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "preset": preset,
        "granularity": granularity,
        "summary": summary,
        "labels": labels,
        "values": values,
        "table_rows": table_rows,
        "period_blocks": period_blocks,
    }
    return render(request, "reports/sales.html", context)


def _build_sales_period_blocks(*, date_from, date_to, granularity, labels, values):
    rows = [{"label": label, "value": value} for label, value in zip(labels, values)]
    if granularity != "daily":
        return [{"label": "Períodos", "rows": rows}]

    blocks = []
    current_date = date_from
    for index, value in enumerate(values):
        if current_date > date_to:
            break
        iso = current_date.isocalendar()
        iso_year = int(iso[0])
        iso_week = int(iso[1])
        if not blocks or blocks[-1]["key"] != (iso_year, iso_week):
            blocks.append(
                {
                    "key": (iso_year, iso_week),
                    "week": iso_week,
                    "year": iso_year,
                    "start": current_date,
                    "end": current_date,
                    "rows": [],
                }
            )
        blocks[-1]["rows"].append(
            {
                "label": labels[index] if index < len(labels) else current_date.strftime("%d/%m"),
                "value": value,
            }
        )
        blocks[-1]["end"] = current_date
        current_date += timedelta(days=1)

    return [
        {
            "label": (
                f"Semana {block['week']}/{block['year']} "
                f"({block['start'].strftime('%d/%m')} - {block['end'].strftime('%d/%m')})"
            ),
            "rows": block["rows"],
        }
        for block in blocks
    ]


@login_required
@business_required
@tenant_permission_required("reports.view_finance")
def payment_methods_report(request):
    preset = request.GET.get("preset") or ""
    date_from_raw = request.GET.get("date_from")
    date_to_raw = request.GET.get("date_to")
    date_from, date_to = get_date_range(
        date_from=_parse_date(date_from_raw),
        date_to=_parse_date(date_to_raw),
        preset=preset,
        default_days=30,
    )
    breakdown = get_payment_breakdown(
        business=request.business, date_from=date_from, date_to=date_to
    )

    if request.GET.get("export") == "csv":
        rows = [
            [item["label"], f'{item["total"]:.2f}', item["count"]]
            for item in breakdown
        ]
        response = _export_csv(
            request,
            filename="relatorio_metodos_pagamento.csv",
            headers=["Metodo", "Total", "Transacoes"],
            rows=rows,
        )
        if response:
            return response

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "preset": preset,
        "breakdown": breakdown,
        "labels": [item["label"] for item in breakdown],
        "values": [item["total"] for item in breakdown],
    }
    return render(request, "reports/payments.html", context)


@login_required
@business_required
@tenant_permission_required("reports.view_finance")
def cashflow_report(request):
    preset = request.GET.get("preset") or ""
    date_from_raw = request.GET.get("date_from")
    date_to_raw = request.GET.get("date_to")
    granularity = request.GET.get("granularity") or "daily"
    date_from, date_to = get_date_range(
        date_from=_parse_date(date_from_raw),
        date_to=_parse_date(date_to_raw),
        preset=preset,
        default_days=30,
    )
    labels, values_in, values_out = get_cashflow_series(
        business=request.business,
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
    )
    total_in = sum(values_in)
    total_out = sum(values_out)

    if request.GET.get("export") == "csv":
        rows = [
            [label, f"{in_value:.2f}", f"{out_value:.2f}"]
            for label, in_value, out_value in zip(labels, values_in, values_out)
        ]
        response = _export_csv(
            request,
            filename="relatorio_fluxo_caixa.csv",
            headers=["Periodo", "Entradas", "Saidas"],
            rows=rows,
        )
        if response:
            return response

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "preset": preset,
        "granularity": granularity,
        "labels": labels,
        "values_in": values_in,
        "values_out": values_out,
        "total_in": total_in,
        "total_out": total_out,
        "net": total_in - total_out,
    }
    return render(request, "reports/cashflow.html", context)


@login_required
@business_required
@tenant_permission_required("reports.view_stock")
def stock_report(request):
    products, low_stock = get_stock_summary(business=request.business)
    total_skus = len(products)
    out_of_stock = sum(1 for item in products if item["quantity"] <= 0)
    total_value = sum(item["stock_value"] for item in products)
    top_value = sorted(products, key=lambda item: item["stock_value"], reverse=True)[:10]

    if request.GET.get("export") == "csv":
        rows = [
            [item["name"], item["quantity"], f'{item["stock_value"]:.2f}']
            for item in products
        ]
        response = _export_csv(
            request,
            filename="relatorio_stock.csv",
            headers=["Produto", "Quantidade", "Valor estimado"],
            rows=rows,
        )
        if response:
            return response

    context = {
        "products": products,
        "low_stock": low_stock,
        "total_skus": total_skus,
        "out_of_stock": out_of_stock,
        "total_value": total_value,
        "labels": [item["name"] for item in top_value],
        "values": [item["stock_value"] for item in top_value],
    }
    return render(request, "reports/stock.html", context)


@login_required
@business_required
@tenant_permission_required("reports.view_finance")
def receivables_report(request):
    buckets, rows = get_receivables_aging(business=request.business)
    if request.GET.get("export") == "csv":
        response = _export_csv(
            request,
            filename="relatorio_recebiveis.csv",
            headers=["Cliente", "Saldo", "Dias em aberto"],
            rows=[
                [row["customer"], f'{row["balance"]:.2f}', row["days"]]
                for row in rows
            ],
        )
        if response:
            return response

    context = {
        "buckets": buckets,
        "rows": rows,
        "labels": list(buckets.keys()),
        "values": list(buckets.values()),
    }
    return render(request, "reports/receivables.html", context)


@login_required
@business_required
@tenant_permission_required("reports.view_basic")
def staff_report(request):
    preset = request.GET.get("preset") or ""
    date_from_raw = request.GET.get("date_from")
    date_to_raw = request.GET.get("date_to")
    date_from, date_to = get_date_range(
        date_from=_parse_date(date_from_raw),
        date_to=_parse_date(date_to_raw),
        preset=preset,
        default_days=30,
    )
    rows = (
        Sale.objects.filter(
            business=request.business,
            status=Sale.STATUS_CONFIRMED,
            sale_date__date__gte=date_from,
            sale_date__date__lte=date_to,
        )
        .values("created_by__first_name", "created_by__last_name", "created_by__username")
        .annotate(
            total=Coalesce(Sum("total"), Decimal("0")),
            count=Coalesce(Count("id"), 0),
        )
        .order_by("-total")
    )
    staff = []
    for row in rows:
        name_parts = [row["created_by__first_name"], row["created_by__last_name"]]
        name = " ".join(part for part in name_parts if part)
        if not name:
            name = row["created_by__username"] or "Sem nome"
        staff.append(
            {
                "name": name,
                "total": float(row["total"]),
                "count": int(row["count"]),
            }
        )

    if request.GET.get("export") == "csv":
        response = _export_csv(
            request,
            filename="relatorio_staff.csv",
            headers=["Colaborador", "Total vendas", "Transacoes"],
            rows=[
                [item["name"], f'{item["total"]:.2f}', item["count"]]
                for item in staff
            ],
        )
        if response:
            return response

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "preset": preset,
        "staff": staff,
        "labels": [item["name"] for item in staff],
        "values": [item["total"] for item in staff],
    }
    return render(request, "reports/staff.html", context)


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _build_variation(*, current, previous):
    current_value = float(current or 0)
    previous_value = float(previous or 0)
    diff = current_value - previous_value
    if previous_value == 0:
        pct = None if current_value == 0 else 100.0
    else:
        pct = (diff / previous_value) * 100
    return {"diff": diff, "pct": pct, "is_positive": diff >= 0}
