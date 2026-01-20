from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import DecimalField, IntegerField, ExpressionWrapper, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse

from catalog.models import Product
from customers.models import Customer
from receivables.models import Receivable
from sales.forms import SaleItemForm, SaleUpdateForm
from sales.models import Sale, SaleItem
from deliveries.models import DeliveryGuideItem
from deliveries.models import DeliveryGuide
from deliveries.services import get_deposit_limits
from inventory.services import get_product_stock
from sales.services import (
    add_draft_item,
    build_draft_item_from_sale_item,
    calculate_draft_totals,
    cancel_sale,
    clear_draft_items,
    confirm_sale,
    get_draft_items,
    set_draft_items,
    remove_draft_item,
)
from tenants.decorators import business_required
from tenants.services import generate_document_code


def _get_reserved_stock(*, business, product):
    ordered = (
        SaleItem.objects.filter(
            sale__business=business,
            sale__status=Sale.STATUS_CONFIRMED,
            product=product,
        )
        .aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") - F("returned_quantity"),
                    output_field=IntegerField(),
                )
            )
        )
        .get("total")
        or 0
    )
    delivered = (
        DeliveryGuideItem.objects.filter(
            guide__business=business,
            guide__status__in=[
                DeliveryGuide.STATUS_ISSUED,
                DeliveryGuide.STATUS_PARTIAL,
                DeliveryGuide.STATUS_DELIVERED,
            ],
            product=product,
        )
        .aggregate(total=Sum("quantity"))
        .get("total")
        or 0
    )
    reserved = ordered - delivered
    if reserved < 0:
        reserved = 0
    return int(reserved)


def _get_available_stock(*, business, product):
    stock = get_product_stock(business, product)
    reserved = _get_reserved_stock(business=business, product=product)
    available = stock - reserved
    if available < 0:
        available = 0
    return int(stock), int(reserved), int(available)


@login_required
@business_required
@permission_required("sales.add_sale", raise_exception=True)
def sale_new(request):
    sale = (
        Sale.objects.filter(
            business=request.business,
            created_by=request.user,
            status=Sale.STATUS_DRAFT,
        )
        .order_by("-created_at")
        .first()
    )
    if not sale:
        sale = Sale.objects.create(
            business=request.business, created_by=request.user, updated_by=request.user
        )
    if not sale.code:
        sale.code = generate_document_code(
            business=request.business,
            doc_type="sale",
            prefix="V",
            date=sale.sale_date.date(),
        )
        sale.save(update_fields=["code"])
    return redirect("sales:detail", pk=sale.id)


@login_required
@business_required
@permission_required("sales.view_sale", raise_exception=True)
def sale_list(request):
    query = request.GET.get("q", "").strip()
    customer_id = request.GET.get("customer", "").strip()
    status = request.GET.get("status", "").strip()
    payment_status = request.GET.get("payment_status", "").strip()
    delivery_status = request.GET.get("delivery_status", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    sales = Sale.objects.select_related("customer").filter(business=request.business)
    if query:
        if query.isdigit():
            sales = sales.filter(
                Q(customer__name__icontains=query)
                | Q(id=int(query))
                | Q(code__icontains=query)
            )
        else:
            sales = sales.filter(
                Q(customer__name__icontains=query) | Q(code__icontains=query)
            )
    if customer_id:
        sales = sales.filter(customer_id=customer_id)
    if status:
        sales = sales.filter(status=status)
    if payment_status:
        sales = sales.filter(payment_status=payment_status)
    if delivery_status:
        sales = sales.filter(delivery_status=delivery_status)
    if date_from:
        sales = sales.filter(sale_date__date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__date__lte=date_to)
    totals = sales.aggregate(total=Sum("total"))
    total_sales_amount = totals["total"] or 0
    canceled_count = sales.filter(status=Sale.STATUS_CANCELED).count()
    open_total = (
        sales.filter(
            status=Sale.STATUS_CONFIRMED,
            payment_status__in=[Sale.PAYMENT_UNPAID, Sale.PAYMENT_PARTIAL],
        ).aggregate(total=Sum("total"))["total"]
        or 0
    )
    paginator = Paginator(sales.order_by("-sale_date"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "sales/sale_list.html",
        {
            "page": page,
            "query": query,
            "customer_id": customer_id,
            "status": status,
            "payment_status": payment_status,
            "delivery_status": delivery_status,
            "date_from": date_from,
            "date_to": date_to,
            "status_choices": Sale.STATUS_CHOICES,
            "payment_choices": Sale.PAYMENT_CHOICES,
            "delivery_choices": Sale.DELIVERY_STATUS_CHOICES,
            "customers": request.business.customers.order_by("name"),
            "total_sales_amount": total_sales_amount,
            "canceled_count": canceled_count,
            "open_total": open_total,
        },
    )


@login_required
@business_required
@permission_required("sales.view_sale", raise_exception=True)
def sale_detail(request, pk):
    sale = get_object_or_404(Sale, pk=pk, business=request.business)
    allow_credit = request.business.feature_enabled("allow_credit_sales")
    open_receivable_total = Decimal("0")
    if sale.customer_id:
        open_receivable_total = (
            Receivable.objects.filter(
                business=request.business,
                customer_id=sale.customer_id,
                status=Receivable.STATUS_OPEN,
            )
            .exclude(sale_id=sale.id)
            .aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("original_amount") - F("total_paid"),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                )
            )
            .get("total")
            or Decimal("0")
        )
    display_items = []
    if sale.status != Sale.STATUS_DRAFT:
        for item in sale.items.select_related("product"):
            returned = item.returned_quantity or 0
            net_qty = item.quantity - returned
            if net_qty < 0:
                net_qty = 0
            if item.quantity > 0:
                net_total = (item.line_total / item.quantity) * net_qty
            else:
                net_total = Decimal("0")
            display_items.append(
                {"item": item, "net_qty": net_qty, "net_total": net_total}
            )
    header_form = SaleUpdateForm(
        instance=sale,
        allow_credit=allow_credit,
        read_only=sale.status != Sale.STATUS_DRAFT,
    )
    header_form.fields["customer"].queryset = sale.business.customers.all()
    item_form = SaleItemForm()
    item_form.fields["product"].queryset = Product.objects.filter(
        business=request.business, is_active=True
    )
    product_label = request.business.ui_labels.get("product", "Produto").lower()
    item_form.fields["product"].widget.attrs["data-placeholder"] = (
        f"Pesquisar {product_label}..."
    )
    draft_items = (
        get_draft_items(request, sale.id)
        if sale.status == Sale.STATUS_DRAFT
        else []
    )
    if sale.status == Sale.STATUS_DRAFT and not draft_items and sale.items.exists():
        draft_items = [
            build_draft_item_from_sale_item(item)
            for item in sale.items.select_related("product")
        ]
        set_draft_items(request, sale.id, draft_items)
    draft_totals = {}
    if sale.status == Sale.STATUS_DRAFT:
        draft_totals = calculate_draft_totals(
            business=sale.business,
            items=draft_items,
            discount_type=sale.discount_type,
            discount_value=sale.discount_value,
        )
    payments = []
    if sale.receivables.exists():
        payments = sorted(
            [
            payment
            for receivable in sale.receivables.prefetch_related("payments").all()
            for payment in receivable.payments.all()
        ],
            key=lambda payment: payment.paid_at,
        )

    delivery_guides = sale.delivery_guides.select_related("created_by").order_by(
        "-issued_at"
    )
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
    delivery_items = []
    delivery_remaining_total = 0
    for item in sale.items.select_related("product"):
        delivered_qty = delivered_map.get(item.id, 0)
        net_qty = item.quantity - (item.returned_quantity or 0)
        remaining = net_qty - delivered_qty
        if remaining < 0:
            remaining = 0
        delivery_remaining_total += remaining
        delivery_items.append(
            {
                "item": item,
                "delivered_qty": delivered_qty,
                "remaining_qty": remaining,
                "ordered_qty": net_qty,
            }
        )
    delivery_completed = sale.items.exists() and delivery_remaining_total == 0

    deposit_data = get_deposit_limits(sale=sale)
    deposit_paid = None
    deposit_balance = None
    deposit_invoice = None
    if deposit_data:
        deposit_paid = deposit_data["paid"]
        deposit_invoice = deposit_data["invoice"]
        total_amount = Decimal(sale.total or 0)
        deposit_balance = total_amount - deposit_paid
        if deposit_balance < 0:
            deposit_balance = Decimal("0")

    has_invoice = sale.invoices.exists()
    delivery_block_reason = None
    if sale.sale_type == Sale.SALE_TYPE_DEPOSIT:
        can_register_delivery = bool(
            deposit_invoice and deposit_paid and deposit_paid > 0
        )
        if not deposit_invoice:
            delivery_block_reason = "Gere a fatura antes do levantamento."
        elif not deposit_paid or deposit_paid <= 0:
            delivery_block_reason = "Registe o pagamento do deposito antes do levantamento."
    else:
        requires_paid = not sale.is_credit
        can_register_delivery = has_invoice and (
            not requires_paid or sale.payment_status == Sale.PAYMENT_PAID
        )
        if not has_invoice:
            delivery_block_reason = "Gere a fatura antes do levantamento."
        elif requires_paid and sale.payment_status != Sale.PAYMENT_PAID:
            delivery_block_reason = "Registe o pagamento antes do levantamento."

    if request.method == "POST" and request.POST.get("action") == "update_header":
        if sale.status != Sale.STATUS_DRAFT:
            messages.error(request, "Nao pode editar uma venda confirmada.")
            return redirect("sales:detail", pk=sale.id)
        header_form = SaleUpdateForm(
            request.POST,
            instance=sale,
            allow_credit=allow_credit,
            read_only=False,
        )
        header_form.fields["customer"].queryset = sale.business.customers.all()
        if header_form.is_valid():
            sale = header_form.save(commit=False)
            sale.updated_by = request.user
            sale.save(
                update_fields=[
                    "customer",
                    "sale_type",
                    "delivery_mode",
                    "is_credit",
                    "discount_type",
                    "discount_value",
                    "payment_method",
                    "payment_due_date",
                    "updated_by",
                ]
            )
            messages.success(request, "Venda atualizada.")
            return redirect("sales:detail", pk=sale.id)

    return render(
        request,
        "sales/sale_detail.html",
        {
            "sale": sale,
            "header_form": header_form,
            "item_form": item_form,
            "draft_items": draft_items,
            "draft_totals": draft_totals,
            "payments": payments,
            "display_items": display_items,
            "delivery_guides": delivery_guides,
            "delivery_items": delivery_items,
            "delivery_remaining_total": delivery_remaining_total,
            "delivery_completed": delivery_completed,
            "refunds": sale.refunds.order_by("-created_at"),
            "allow_credit": allow_credit,
            "allow_returns": request.business.feature_enabled("enable_returns"),
            "can_register_delivery": can_register_delivery,
            "delivery_block_reason": delivery_block_reason,
            "open_receivable_total": open_receivable_total,
            "deposit_paid": deposit_paid,
            "deposit_balance": deposit_balance,
            "deposit_invoice": deposit_invoice,
        },
    )


@login_required
@business_required
@permission_required("sales.add_saleitem", raise_exception=True)
def sale_add_item(request, pk):
    sale = get_object_or_404(Sale, pk=pk, business=request.business)
    if sale.status != Sale.STATUS_DRAFT:
        messages.error(request, "Nao pode adicionar itens a uma venda confirmada.")
        return redirect("sales:detail", pk=sale.id)
    item_error = None
    allow_credit = request.business.feature_enabled("allow_credit_sales")
    header_fields = [
        "customer",
        "sale_type",
        "delivery_mode",
        "is_credit",
        "discount_type",
        "discount_value",
        "payment_method",
        "payment_due_date",
    ]
    if request.method == "POST":
        if any(field in request.POST for field in header_fields):
            header_form = SaleUpdateForm(
                request.POST,
                instance=sale,
                allow_credit=allow_credit,
                relaxed=True,
            )
            header_form.fields["customer"].queryset = sale.business.customers.all()
            if header_form.is_valid():
                sale = header_form.save(commit=False)
                sale.updated_by = request.user
                sale.save(
                    update_fields=[
                        "customer",
                        "sale_type",
                        "delivery_mode",
                        "is_credit",
                        "discount_type",
                        "discount_value",
                        "payment_method",
                        "payment_due_date",
                        "updated_by",
                    ]
                )
        form = SaleItemForm(request.POST)
        form.fields["product"].queryset = Product.objects.filter(
            business=request.business, is_active=True
        )
        if form.is_valid():
            product = form.cleaned_data["product"]
            quantity = form.cleaned_data["quantity"]
            if (
                product.stock_control_mode == product.STOCK_AUTOMATIC
                and not request.business.allow_negative_stock
            ):
                stock, reserved, available = _get_available_stock(
                    business=request.business, product=product
                )
                if quantity > available:
                    item_error = (
                        f"Stock insuficiente. Disponivel: {available} unidades."
                    )
                else:
                    items = get_draft_items(request, sale.id)
                    items = add_draft_item(
                        business=sale.business,
                        items=items,
                        product=product,
                        quantity=quantity,
                    )
                    set_draft_items(request, sale.id, items)
            else:
                items = get_draft_items(request, sale.id)
                items = add_draft_item(
                    business=sale.business,
                    items=items,
                    product=product,
                    quantity=quantity,
                )
                set_draft_items(request, sale.id, items)
        else:
            item_error = "Selecione o produto e a quantidade."
    if request.headers.get("HX-Request"):
        draft_items = get_draft_items(request, sale.id)
        draft_totals = calculate_draft_totals(
            business=sale.business,
            items=draft_items,
            discount_type=sale.discount_type,
            discount_value=sale.discount_value,
        )
        return render(
            request,
            "sales/partials/sale_items.html",
            {
                "sale": sale,
                "draft_items": draft_items,
                "draft_totals": draft_totals,
                "item_error": item_error,
            },
        )
    return redirect("sales:detail", pk=sale.id)


@login_required
@business_required
@permission_required("sales.change_sale", raise_exception=True)
def sale_update_discount(request, pk):
    sale = get_object_or_404(Sale, pk=pk, business=request.business)
    if sale.status != Sale.STATUS_DRAFT:
        return JsonResponse({"detail": "Venda nao esta em rascunho."}, status=400)
    if request.method != "POST":
        return JsonResponse({"detail": "Metodo invalido."}, status=405)
    allow_credit = request.business.feature_enabled("allow_credit_sales")
    form_data = {
        "customer": sale.customer_id or "",
        "sale_type": sale.sale_type,
        "delivery_mode": sale.delivery_mode,
        "is_credit": sale.is_credit,
        "discount_type": request.POST.get("discount_type", sale.discount_type),
        "discount_value": request.POST.get("discount_value", sale.discount_value),
        "payment_method": sale.payment_method,
        "payment_due_date": sale.payment_due_date or "",
    }
    form = SaleUpdateForm(
        form_data, instance=sale, allow_credit=allow_credit, relaxed=True
    )
    if form.is_valid():
        sale = form.save(commit=False)
        sale.updated_by = request.user
        sale.save(
            update_fields=[
                "discount_type",
                "discount_value",
                "updated_by",
            ]
        )
    draft_items = get_draft_items(request, sale.id)
    draft_totals = calculate_draft_totals(
        business=sale.business,
        items=draft_items,
        discount_type=sale.discount_type,
        discount_value=sale.discount_value,
    )
    return render(
        request,
        "sales/partials/sale_items.html",
        {
            "sale": sale,
            "draft_items": draft_items,
            "draft_totals": draft_totals,
            "item_error": None if form.is_valid() else "Desconto invalido.",
        },
    )


@login_required
@business_required
@permission_required("sales.view_sale", raise_exception=True)
def sale_product_stock(request, product_id):
    product = get_object_or_404(
        Product, pk=product_id, business=request.business, is_active=True
    )
    stock, reserved, available = _get_available_stock(
        business=request.business, product=product
    )
    return JsonResponse(
        {
            "stock": int(stock),
            "reserved": int(reserved),
            "available": int(available),
            "allow_negative": request.business.allow_negative_stock,
            "stock_control": product.stock_control_mode,
        }
    )


@login_required
@business_required
@permission_required("sales.view_sale", raise_exception=True)
def customer_open_debt(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id, business=request.business)
    total = (
        Receivable.objects.filter(
            business=request.business,
            customer=customer,
            status=Receivable.STATUS_OPEN,
        )
        .aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("original_amount") - F("total_paid"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
        )
        .get("total")
        or Decimal("0")
    )
    return JsonResponse({"total": str(total)})


@login_required
@business_required
@permission_required("sales.change_sale", raise_exception=True)
def sale_remove_item(request, pk, item_id):
    sale = get_object_or_404(Sale, pk=pk, business=request.business)
    if request.method == "POST":
        if sale.status == Sale.STATUS_DRAFT:
            items = get_draft_items(request, sale.id)
            items = remove_draft_item(items=items, product_id=item_id)
            set_draft_items(request, sale.id, items)
        else:
            messages.error(request, "Nao pode remover itens de uma venda confirmada.")
            return redirect("sales:detail", pk=sale.id)
    if request.headers.get("HX-Request"):
        draft_items = get_draft_items(request, sale.id)
        draft_totals = calculate_draft_totals(
            business=sale.business,
            items=draft_items,
            discount_type=sale.discount_type,
            discount_value=sale.discount_value,
        )
        return render(
            request,
            "sales/partials/sale_items.html",
            {"sale": sale, "draft_items": draft_items, "draft_totals": draft_totals},
        )
    return redirect("sales:detail", pk=sale.id)


@login_required
@business_required
@permission_required("sales.change_sale", raise_exception=True)
def sale_confirm(request, pk):
    if request.method == "POST":
        try:
            sale = get_object_or_404(Sale, pk=pk, business=request.business)
            allow_credit = request.business.feature_enabled("allow_credit_sales")
            header_fields = [
                "customer",
                "sale_type",
                "delivery_mode",
                "is_credit",
                "discount_type",
                "discount_value",
                "payment_method",
                "payment_due_date",
            ]
            if any(field in request.POST for field in header_fields):
                form_data = request.POST.copy()
                if "customer" not in form_data and sale.customer_id:
                    form_data["customer"] = str(sale.customer_id)
                if "sale_type" not in form_data:
                    form_data["sale_type"] = sale.sale_type
                if "delivery_mode" not in form_data:
                    form_data["delivery_mode"] = sale.delivery_mode
                if "is_credit" not in form_data and sale.is_credit:
                    form_data["is_credit"] = "on"
                if "discount_type" not in form_data:
                    form_data["discount_type"] = sale.discount_type
                if "discount_value" not in form_data:
                    form_data["discount_value"] = str(sale.discount_value)
                if "payment_method" not in form_data and sale.payment_method:
                    form_data["payment_method"] = sale.payment_method
                if "payment_due_date" not in form_data and sale.payment_due_date:
                    form_data["payment_due_date"] = sale.payment_due_date.isoformat()
                header_form = SaleUpdateForm(
                    form_data,
                    instance=sale,
                    allow_credit=allow_credit,
                )
                header_form.fields["customer"].queryset = sale.business.customers.all()
                if header_form.is_valid():
                    sale = header_form.save(commit=False)
                    sale.updated_by = request.user
                    sale.save(
                        update_fields=[
                            "customer",
                            "sale_type",
                            "delivery_mode",
                            "is_credit",
                            "discount_type",
                            "discount_value",
                            "payment_method",
                            "payment_due_date",
                            "updated_by",
                        ]
                    )
                else:
                    messages.error(request, "Corrija os campos do cabecalho.")
                    item_form = SaleItemForm()
                    item_form.fields["product"].queryset = Product.objects.filter(
                        business=request.business, is_active=True
                    )
                    product_label = request.business.ui_labels.get("product", "Produto").lower()
                    item_form.fields["product"].widget.attrs["data-placeholder"] = (
                        f"Pesquisar {product_label}..."
                    )
                    draft_items = (
                        get_draft_items(request, sale.id)
                        if sale.status == Sale.STATUS_DRAFT
                        else []
                    )
                    if sale.status == Sale.STATUS_DRAFT and not draft_items and sale.items.exists():
                        draft_items = [
                            build_draft_item_from_sale_item(item)
                            for item in sale.items.select_related("product")
                        ]
                        set_draft_items(request, sale.id, draft_items)
                    draft_totals = {}
                    if sale.status == Sale.STATUS_DRAFT:
                        draft_totals = calculate_draft_totals(
                            business=sale.business,
                            items=draft_items,
                            discount_type=sale.discount_type,
                            discount_value=sale.discount_value,
                        )
                    payments = []
                    if sale.receivables.exists():
                        payments = sorted(
                            [
                                payment
                                for receivable in sale.receivables.prefetch_related("payments").all()
                                for payment in receivable.payments.all()
                            ],
                            key=lambda payment: payment.paid_at,
                        )
                    display_items = []
                    if sale.status != Sale.STATUS_DRAFT:
                        for item in sale.items.select_related("product"):
                            returned = item.returned_quantity or 0
                            net_qty = item.quantity - returned
                            if net_qty < 0:
                                net_qty = 0
                            if item.quantity > 0:
                                net_total = (item.line_total / item.quantity) * net_qty
                            else:
                                net_total = Decimal("0")
                            display_items.append(
                                {"item": item, "net_qty": net_qty, "net_total": net_total}
                            )
                    delivery_guides = sale.delivery_guides.select_related("created_by").order_by(
                        "-issued_at"
                    )
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
                    delivery_items = []
                    delivery_remaining_total = 0
                    for item in sale.items.select_related("product"):
                        delivered_qty = delivered_map.get(item.id, 0)
                        net_qty = item.quantity - (item.returned_quantity or 0)
                        remaining = net_qty - delivered_qty
                        if remaining < 0:
                            remaining = 0
                        delivery_remaining_total += remaining
                        delivery_items.append(
                            {
                                "item": item,
                                "delivered_qty": delivered_qty,
                                "remaining_qty": remaining,
                                "ordered_qty": net_qty,
                            }
                        )
                    delivery_completed = sale.items.exists() and delivery_remaining_total == 0
                    deposit_data = get_deposit_limits(sale=sale)
                    deposit_paid = None
                    deposit_balance = None
                    deposit_invoice = None
                    if deposit_data:
                        deposit_paid = deposit_data["paid"]
                        deposit_invoice = deposit_data["invoice"]
                        total_amount = Decimal(sale.total or 0)
                        deposit_balance = total_amount - deposit_paid
                        if deposit_balance < 0:
                            deposit_balance = Decimal("0")
                    has_invoice = sale.invoices.exists()
                    delivery_block_reason = None
                    if sale.sale_type == Sale.SALE_TYPE_DEPOSIT:
                        can_register_delivery = bool(
                            deposit_invoice and deposit_paid and deposit_paid > 0
                        )
                        if not deposit_invoice:
                            delivery_block_reason = "Gere a fatura antes do levantamento."
                        elif not deposit_paid or deposit_paid <= 0:
                            delivery_block_reason = "Registe o pagamento do deposito antes do levantamento."
                    else:
                        requires_paid = not sale.is_credit
                        can_register_delivery = has_invoice and (
                            not requires_paid or sale.payment_status == Sale.PAYMENT_PAID
                        )
                        if not has_invoice:
                            delivery_block_reason = "Gere a fatura antes do levantamento."
                        elif requires_paid and sale.payment_status != Sale.PAYMENT_PAID:
                            delivery_block_reason = "Registe o pagamento antes do levantamento."
                    return render(
                        request,
                        "sales/sale_detail.html",
                        {
                            "sale": sale,
                            "header_form": header_form,
                            "item_form": item_form,
                            "draft_items": draft_items,
                            "draft_totals": draft_totals,
                            "payments": payments,
                            "display_items": display_items,
                            "delivery_guides": delivery_guides,
                            "delivery_items": delivery_items,
                            "delivery_remaining_total": delivery_remaining_total,
                            "delivery_completed": delivery_completed,
                            "refunds": sale.refunds.order_by("-created_at"),
                            "allow_credit": allow_credit,
                            "allow_returns": request.business.feature_enabled("enable_returns"),
                            "can_register_delivery": can_register_delivery,
                            "delivery_block_reason": delivery_block_reason,
                            "deposit_paid": deposit_paid,
                            "deposit_balance": deposit_balance,
                            "deposit_invoice": deposit_invoice,
                        },
                    )
            items_data = (
                get_draft_items(request, sale.id)
                if sale.status == Sale.STATUS_DRAFT
                else None
            )
            confirm_sale(
                sale_id=pk,
                business=request.business,
                user=request.user,
                items_data=items_data,
                confirm_open_debt=request.POST.get("confirm_open_debt") == "1",
            )
            clear_draft_items(request, sale.id)
            messages.success(request, "Venda confirmada.")
            return redirect("sales:list")
        except ValidationError as exc:
            messages.error(request, exc.messages[0] if exc.messages else str(exc))
        except Exception as exc:
            messages.error(request, str(exc))
    return redirect("sales:detail", pk=pk)


@login_required
@business_required
@permission_required("sales.change_sale", raise_exception=True)
def sale_cancel(request, pk):
    sale = get_object_or_404(Sale, pk=pk, business=request.business)
    allow_returns = request.business.feature_enabled("enable_returns")
    if request.method == "GET" and request.headers.get("HX-Request"):
        items = sale.items.select_related("product")
        return render(
            request,
            "sales/partials/sale_cancel_modal.html",
            {"sale": sale, "items": items, "allow_returns": allow_returns},
        )
    if request.method == "POST":
        return_type = request.POST.get("return_type", Sale.RETURN_NONE)
        notes = request.POST.get("notes", "")
        return_items = {}
        if return_type == Sale.RETURN_PARTIAL:
            for item in sale.items.all():
                qty_raw = request.POST.get(f"return_qty_{item.id}", "0")
                try:
                    qty = int(Decimal(qty_raw.replace(",", ".")))
                except Exception:
                    qty = 0
                return_items[item.id] = qty
        try:
            cancel_sale(
                sale_id=pk,
                business=request.business,
                user=request.user,
                return_type=return_type,
                return_items=return_items,
                notes=notes,
            )
            messages.success(request, "Venda cancelada.")
            if request.headers.get("HX-Request"):
                return render(
                    request,
                    "sales/partials/sale_cancel_modal.html",
                    {"sale": sale, "canceled": True, "allow_returns": allow_returns},
                )
            return redirect("sales:list")
        except ValidationError as exc:
            messages.error(request, exc.messages[0] if exc.messages else str(exc))
            if request.headers.get("HX-Request"):
                items = sale.items.select_related("product")
                return render(
                    request,
                    "sales/partials/sale_cancel_modal.html",
                    {
                        "sale": sale,
                        "items": items,
                        "error": exc.messages[0],
                        "allow_returns": allow_returns,
                    },
                )
        except Exception as exc:
            messages.error(request, str(exc))
            if request.headers.get("HX-Request"):
                items = sale.items.select_related("product")
                return render(
                    request,
                    "sales/partials/sale_cancel_modal.html",
                    {
                        "sale": sale,
                        "items": items,
                        "error": str(exc),
                        "allow_returns": allow_returns,
                    },
                )
    return redirect("sales:detail", pk=pk)
