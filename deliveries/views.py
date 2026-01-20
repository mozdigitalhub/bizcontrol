from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.dateparse import parse_date
import json
from itertools import groupby
from decimal import Decimal, InvalidOperation

from deliveries.models import DeliveryGuide, DeliveryGuideItem
from deliveries.services import cancel_delivery, get_deposit_limits, register_delivery
from sales.models import Sale
from tenants.decorators import business_required

try:
    from weasyprint import HTML
except Exception:  # pragma: no cover - optional dependency
    HTML = None


def _build_sale_item_summary(sale):
    deposit_data = get_deposit_limits(sale=sale)
    allow_over = bool(sale.business.allow_over_delivery_deposit)
    delivered_map = {
        row["sale_item_id"]: row["total"] or 0
        for row in (
            DeliveryGuideItem.objects.filter(
                guide__sale=sale,
                guide__status__in=["issued", "partial", "delivered"],
            )
            .values("sale_item_id")
            .annotate(total=Sum("quantity"))
        )
    }
    summary = []
    for item in sale.items.select_related("product"):
        ordered_qty = item.quantity - (item.returned_quantity or 0)
        delivered_qty = delivered_map.get(item.id, 0)
        remaining_qty = ordered_qty - delivered_qty
        if remaining_qty < 0:
            remaining_qty = 0
        allowed_remaining = remaining_qty
        if deposit_data and not allow_over:
            allowed_total = deposit_data["allowed_map"].get(item.id, 0)
            allowed_remaining = allowed_total - delivered_qty
            if allowed_remaining < 0:
                allowed_remaining = 0
        summary.append(
            {
                "item": item,
                "ordered_qty": ordered_qty,
                "delivered_qty": delivered_qty,
                "remaining_qty": remaining_qty,
                "allowed_remaining": allowed_remaining,
            }
        )
    return summary


@login_required
@business_required
@permission_required("deliveries.view_deliveryguide", raise_exception=True)
def guide_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    customer_id = request.GET.get("customer", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    guides = DeliveryGuide.objects.filter(business=request.business).select_related(
        "customer", "sale"
    )
    if query:
        guides = guides.filter(
            Q(code__icontains=query)
            | Q(guide_number__icontains=query)
            | Q(customer__name__icontains=query)
            | Q(sale__code__icontains=query)
            | Q(sale__id__icontains=query)
        )
    if status:
        guides = guides.filter(status=status)
    if customer_id:
        guides = guides.filter(customer_id=customer_id)
    if date_from:
        guides = guides.filter(issued_at__date__gte=date_from)
    if date_to:
        guides = guides.filter(issued_at__date__lte=date_to)

    paginator = Paginator(guides.order_by("-issued_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    grouped_guides = []
    for sale_id, items in groupby(page.object_list, key=lambda guide: guide.sale_id):
        items_list = list(items)
        grouped_guides.append({"sale": items_list[0].sale, "guides": items_list})
    return render(
        request,
        "deliveries/guide_list.html",
        {
            "page": page,
            "grouped_guides": grouped_guides,
            "query": query,
            "status": status,
            "customer_id": customer_id,
            "date_from": date_from,
            "date_to": date_to,
            "status_choices": DeliveryGuide.STATUS_CHOICES,
            "customers": request.business.customers.order_by("name"),
        },
    )


@login_required
@business_required
@permission_required("deliveries.view_deliveryguide", raise_exception=True)
def guide_detail(request, pk):
    is_htmx = request.headers.get("HX-Request") == "true"
    guide = get_object_or_404(DeliveryGuide, pk=pk, business=request.business)
    summary = _build_sale_item_summary(guide.sale)
    items = guide.items.select_related("product")
    template = (
        "deliveries/partials/guide_detail_modal.html"
        if is_htmx
        else "deliveries/guide_detail.html"
    )
    return render(
        request,
        template,
        {"guide": guide, "items": items, "summary_items": summary},
    )


@login_required
@business_required
@permission_required("deliveries.add_deliveryguide", raise_exception=True)
def guide_create_modal(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id, business=request.business)
    summary = _build_sale_item_summary(sale)
    deposit_data = get_deposit_limits(sale=sale)
    deposit_allow_over = bool(request.business.allow_over_delivery_deposit)
    return render(
        request,
        "deliveries/partials/guide_create_modal.html",
        {
            "sale": sale,
            "summary_items": summary,
            "deposit_data": deposit_data,
            "deposit_allow_over": deposit_allow_over,
        },
    )


@login_required
@business_required
@permission_required("deliveries.add_deliveryguide", raise_exception=True)
def guide_create(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id, business=request.business)
    if request.method == "POST":
        is_htmx = request.headers.get("HX-Request") == "true"
        delivery_kind = request.POST.get("delivery_kind", "partial")
        if delivery_kind not in {"partial", "total"}:
            delivery_kind = "partial"
        items_map = {}
        if delivery_kind == "total":
            summary = _build_sale_item_summary(sale)
            for row in summary:
                if row["remaining_qty"] > 0:
                    items_map[str(row["item"].id)] = str(row["remaining_qty"])
        else:
            for item in sale.items.all():
                key = f"qty_{item.id}"
                raw = request.POST.get(key, "").strip()
                if raw:
                    items_map[str(item.id)] = raw.replace(",", ".")
        notes = request.POST.get("notes", "").strip()
        expected_delivery_date = parse_date(
            request.POST.get("expected_delivery_date", "").strip()
        )
        transport_responsible = request.POST.get("transport_responsible", "").strip()
        transport_cost_raw = request.POST.get("transport_cost", "").strip()
        transport_cost = None
        if transport_cost_raw:
            try:
                transport_cost = Decimal(transport_cost_raw.replace(",", "."))
            except InvalidOperation:
                transport_cost = None
        try:
            register_delivery(
                sale_id=sale.id,
                business=request.business,
                user=request.user,
                items_map=items_map,
                notes=notes,
                delivery_kind=delivery_kind,
                expected_delivery_date=expected_delivery_date,
                transport_responsible=transport_responsible,
                transport_cost=transport_cost,
            )
            if is_htmx:
                sale.refresh_from_db()
                delivery_guides = sale.delivery_guides.order_by("-issued_at")
                summary = _build_sale_item_summary(sale)
                remaining_total = sum(row["remaining_qty"] for row in summary)
                response = render(
                    request,
                    "deliveries/partials/sale_delivery_table.html",
                    {
                        "delivery_guides": delivery_guides,
                    },
                )
                response["HX-Trigger"] = json.dumps(
                    {"deliveryGuideCreated": {"remaining": remaining_total}}
                )
                return response
            messages.success(request, "Levantamento registado.")
            return redirect("sales:detail", pk=sale.id)
        except ValidationError as exc:
            message = exc.messages[0] if exc.messages else "Nao foi possivel registar o levantamento."
            summary = _build_sale_item_summary(sale)
            if is_htmx:
                response = render(
                    request,
                    "deliveries/partials/guide_create_modal.html",
                    {"sale": sale, "summary_items": summary, "error": message},
                )
                response["HX-Retarget"] = "#delivery-modal-container"
                response["HX-Reswap"] = "innerHTML"
                return response
            messages.error(request, message)
        except Exception:
            summary = _build_sale_item_summary(sale)
            if is_htmx:
                response = render(
                    request,
                    "deliveries/partials/guide_create_modal.html",
                    {"sale": sale, "summary_items": summary, "error": "Nao foi possivel registar o levantamento."},
                )
                response["HX-Retarget"] = "#delivery-modal-container"
                response["HX-Reswap"] = "innerHTML"
                return response
            messages.error(request, "Nao foi possivel registar o levantamento.")
    return redirect("sales:detail", pk=sale.id)


@login_required
@business_required
@permission_required("deliveries.change_deliveryguide", raise_exception=True)
def guide_cancel(request, pk):
    guide = get_object_or_404(DeliveryGuide, pk=pk, business=request.business)
    if request.method == "POST":
        try:
            cancel_delivery(
                guide_id=guide.id,
                business=request.business,
                user=request.user,
                notes="Cancelamento manual",
            )
            messages.success(request, "Guia cancelada.")
        except Exception as exc:
            messages.error(request, str(exc))
        if request.headers.get("HX-Request"):
            guides = guide.sale.delivery_guides.order_by("-issued_at")
            return render(
                request,
                "deliveries/partials/sale_delivery_table.html",
                {"delivery_guides": guides},
            )
        return redirect("sales:detail", pk=guide.sale_id)
    return redirect("deliveries:guide_detail", pk=guide.id)


def _render_guide_pdf(guide, request, download=False):
    if HTML is None:
        return HttpResponse("WeasyPrint nao instalado.", status=500)
    summary = _build_sale_item_summary(guide.sale)
    html = render_to_string(
        "deliveries/guide_pdf.html",
        {
            "guide": guide,
            "business": guide.business,
            "items": guide.items.select_related("product"),
            "summary_items": summary,
        },
    )
    pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()
    response = HttpResponse(pdf, content_type="application/pdf")
    if download:
        response["Content-Disposition"] = (
            f'attachment; filename=\"guia-{guide.guide_number}.pdf\"'
        )
    return response


@login_required
@business_required
@permission_required("deliveries.view_deliveryguide", raise_exception=True)
def guide_pdf_view(request, pk):
    guide = get_object_or_404(DeliveryGuide, pk=pk, business=request.business)
    return _render_guide_pdf(guide, request, download=False)


@login_required
@business_required
@permission_required("deliveries.view_deliveryguide", raise_exception=True)
def guide_pdf_download(request, pk):
    guide = get_object_or_404(DeliveryGuide, pk=pk, business=request.business)
    return _render_guide_pdf(guide, request, download=True)
