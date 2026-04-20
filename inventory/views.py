import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import (
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Product
from deliveries.models import DeliveryGuide, DeliveryGuideItem
from inventory.forms import (
    GoodsReceiptForm,
    GoodsReceiptItemFormSet,
    StockMovementForm,
    StockImportForm,
)
from inventory.excel_import import ExcelImportService
from deliveries.models import DeliveryGuide
from inventory.models import GoodsReceipt, StockMovement
from inventory.services import get_product_stock, receive_goods
from finance.models import Purchase
from sales.models import Sale, SaleItem
from tenants.decorators import business_required


@login_required
@business_required
@permission_required("inventory.view_stockmovement", raise_exception=True)
def stock_list(request):
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    stock_status = request.GET.get("stock_status", "").strip()
    reserved_only = request.GET.get("reserved", "").strip()
    delivered_only = request.GET.get("delivered", "").strip()
    last_movement = StockMovement.objects.filter(
        business=request.business,
        product=OuterRef("pk"),
    ).order_by("-created_at")
    products = (
        Product.objects.filter(business=request.business)
        .select_related("category")
        .annotate(last_movement_at=Subquery(last_movement.values("created_at")[:1]))
        .order_by("name")
    )
    if query:
        products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    if category_id:
        products = products.filter(category_id=category_id)
    products = list(products)
    ordered_quantities = (
        SaleItem.objects.filter(
            sale__business=request.business,
            sale__status=Sale.STATUS_CONFIRMED,
        )
        .values("product_id")
        .annotate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") - F("returned_quantity"),
                    output_field=IntegerField(),
                )
            )
        )
    )
    ordered_map = {
        row["product_id"]: row["total"] or 0 for row in ordered_quantities
    }
    delivered_quantities = (
        DeliveryGuideItem.objects.filter(
            guide__business=request.business,
            guide__status__in=[
                DeliveryGuide.STATUS_ISSUED,
                DeliveryGuide.STATUS_PARTIAL,
                DeliveryGuide.STATUS_DELIVERED,
            ],
        )
        .values("product_id")
        .annotate(total=Sum("quantity"))
    )
    delivered_map = {
        row["product_id"]: row["total"] or 0 for row in delivered_quantities
    }
    reserved_products_count = 0
    delivered_products_count = 0
    low_stock_count = 0
    for product in products:
        product.stock_quantity = int(get_product_stock(request.business, product))
        ordered_qty = int(ordered_map.get(product.id, 0))
        delivered_qty = int(delivered_map.get(product.id, 0))
        reserved_qty = ordered_qty - delivered_qty
        if reserved_qty < 0:
            reserved_qty = 0
        product.delivered_quantity = int(delivered_qty)
        product.reserved_quantity = int(reserved_qty)
        available_qty = product.stock_quantity - product.reserved_quantity
        if available_qty < 0:
            available_qty = 0
        product.available_quantity = int(available_qty)
        if product.reorder_level is not None:
            product.is_low_stock = product.available_quantity <= product.reorder_level
        else:
            product.is_low_stock = False
        if product.reserved_quantity > 0:
            reserved_products_count += 1
        if product.delivered_quantity > 0:
            delivered_products_count += 1
        if product.is_low_stock:
            low_stock_count += 1
    if stock_status == "low":
        products = [product for product in products if product.is_low_stock]
    elif stock_status == "ok":
        products = [product for product in products if not product.is_low_stock]
    if reserved_only:
        products = [product for product in products if product.reserved_quantity > 0]
    if delivered_only:
        products = [product for product in products if product.delivered_quantity > 0]
    paginator = Paginator(products, 20)
    page = paginator.get_page(request.GET.get("page"))
    categories = Category.objects.filter(business=request.business).order_by("name")
    return render(
        request,
        "inventory/stock_list.html",
        {
            "page": page,
            "query": query,
            "category_id": category_id,
            "stock_status": stock_status,
            "reserved_only": reserved_only,
            "delivered_only": delivered_only,
            "reserved_products_count": reserved_products_count,
            "delivered_products_count": delivered_products_count,
            "low_stock_count": low_stock_count,
            "categories": categories,
        },
    )


@login_required
@business_required
@permission_required("inventory.view_stockmovement", raise_exception=True)
def movement_list(request):
    query = request.GET.get("q", "").strip()
    movement_type = request.GET.get("movement_type", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    movements = StockMovement.objects.filter(business=request.business).select_related(
        "product"
    )
    if query:
        movements = movements.filter(
            Q(product__name__icontains=query) | Q(product__sku__icontains=query)
        )
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    if date_from:
        movements = movements.filter(created_at__date__gte=date_from)
    if date_to:
        movements = movements.filter(created_at__date__lte=date_to)
    paginator = Paginator(movements.order_by("-created_at"), 25)
    page = paginator.get_page(request.GET.get("page"))
    guide_ids = {
        movement.reference_id
        for movement in page.object_list
        if movement.reference_type == "delivery_guide" and movement.reference_id
    }
    receipt_ids = {
        movement.reference_id
        for movement in page.object_list
        if movement.reference_type == "goods_receipt" and movement.reference_id
    }
    reserve_sale_ids = {
        movement.reference_id
        for movement in page.object_list
        if movement.reference_type == "sale_reserve" and movement.reference_id
    }
    guide_map = {
        guide.id: guide
        for guide in DeliveryGuide.objects.filter(
            business=request.business, id__in=guide_ids
        ).only("id", "guide_number", "code")
    }
    receipt_map = {
        receipt.id: receipt
        for receipt in GoodsReceipt.objects.filter(
            business=request.business, id__in=receipt_ids
        ).only("id", "document_number")
    }
    sale_map = {
        sale.id: sale
        for sale in Sale.objects.filter(
            business=request.business, id__in=reserve_sale_ids
        ).only("id", "code")
    }
    for movement in page.object_list:
        movement.reference_label = "-"
        movement.reference_url = ""
        if movement.reference_type == "delivery_guide" and movement.reference_id:
            guide = guide_map.get(movement.reference_id)
            if guide:
                movement.reference_label = guide.code or f"Guia #{guide.guide_number}"
                movement.reference_url = reverse("deliveries:guide_detail", args=[guide.id])
        elif movement.reference_type == "goods_receipt" and movement.reference_id:
            receipt = receipt_map.get(movement.reference_id)
            if receipt:
                movement.reference_label = f"Rececao {receipt.document_number}"
                movement.reference_url = reverse("inventory:receipt_detail", args=[receipt.id])
        elif movement.reference_type == "sale_reserve" and movement.reference_id:
            sale = sale_map.get(movement.reference_id)
            if sale:
                movement.reference_label = sale.code or f"Venda #{sale.id}"
                movement.reference_url = reverse("sales:detail", args=[sale.id])
        elif movement.reference_type:
            movement.reference_label = movement.reference_type.replace("_", " ").title()
    return render(
        request,
        "inventory/movement_list.html",
        {
            "page": page,
            "query": query,
            "movement_type": movement_type,
            "date_from": date_from,
            "date_to": date_to,
            "movement_choices": StockMovement.MOVEMENT_CHOICES,
        },
    )


@login_required
@business_required
@permission_required("inventory.add_stockmovement", raise_exception=True)
def movement_create(request):
    if request.method == "POST":
        form = StockMovementForm(request.POST)
        form.fields["product"].queryset = request.business.products.all()
        product_label = request.business.ui_labels.get("product", "Produto").lower()
        form.fields["product"].widget.attrs["data-placeholder"] = (
            f"Pesquisar {product_label}..."
        )
        if form.is_valid():
            movement = form.save(commit=False)
            movement.business = request.business
            movement.created_by = request.user
            movement.reference_type = "manual"
            movement.save()
            messages.success(request, "Movimento registado com sucesso.")
            if request.headers.get("HX-Request"):
                form = StockMovementForm()
                form.fields["product"].queryset = request.business.products.all()
                return render(
                    request,
                    "inventory/partials/movement_modal.html",
                    {"form": form, "created": True},
                )
            return redirect("inventory:movement_list")
    else:
        form = StockMovementForm()
        form.fields["product"].queryset = request.business.products.all()
        product_label = request.business.ui_labels.get("product", "Produto").lower()
        form.fields["product"].widget.attrs["data-placeholder"] = (
            f"Pesquisar {product_label}..."
        )
    if request.headers.get("HX-Request"):
        return render(
            request,
            "inventory/partials/movement_modal.html",
            {"form": form},
        )
    return render(request, "inventory/movement_form.html", {"form": form})


@login_required
@business_required
@permission_required("inventory.view_stockmovement", raise_exception=True)
def product_movements(request, pk):
    product = get_object_or_404(Product, pk=pk, business=request.business)
    movements = (
        StockMovement.objects.filter(business=request.business, product=product)
        .order_by("-created_at")[:10]
    )
    guide_ids = {
        movement.reference_id
        for movement in movements
        if movement.reference_type == "delivery_guide" and movement.reference_id
    }
    receipt_ids = {
        movement.reference_id
        for movement in movements
        if movement.reference_type == "goods_receipt" and movement.reference_id
    }
    reserve_sale_ids = {
        movement.reference_id
        for movement in movements
        if movement.reference_type == "sale_reserve" and movement.reference_id
    }
    guide_map = {
        guide.id: guide
        for guide in DeliveryGuide.objects.filter(
            business=request.business, id__in=guide_ids
        ).only("id", "guide_number", "code")
    }
    receipt_map = {
        receipt.id: receipt
        for receipt in GoodsReceipt.objects.filter(
            business=request.business, id__in=receipt_ids
        ).only("id", "document_number")
    }
    sale_map = {
        sale.id: sale
        for sale in Sale.objects.filter(
            business=request.business, id__in=reserve_sale_ids
        ).only("id", "code")
    }
    for movement in movements:
        movement.reference_label = "-"
        movement.reference_url = ""
        if movement.reference_type == "delivery_guide" and movement.reference_id:
            guide = guide_map.get(movement.reference_id)
            if guide:
                movement.reference_label = guide.code or f"Guia #{guide.guide_number}"
                movement.reference_url = reverse(
                    "deliveries:guide_detail", args=[guide.id]
                )
        elif movement.reference_type == "goods_receipt" and movement.reference_id:
            receipt = receipt_map.get(movement.reference_id)
            if receipt:
                movement.reference_label = f"Rececao {receipt.document_number}"
                movement.reference_url = reverse(
                    "inventory:receipt_detail", args=[receipt.id]
                )
        elif movement.reference_type == "sale_reserve" and movement.reference_id:
            sale = sale_map.get(movement.reference_id)
            if sale:
                movement.reference_label = sale.code or f"Venda #{sale.id}"
                movement.reference_url = reverse("sales:detail", args=[sale.id])
        elif movement.reference_type:
            movement.reference_label = movement.reference_type.replace("_", " ").title()
    return render(
        request,
        "inventory/partials/product_movements_modal.html",
        {"product": product, "movements": movements},
    )


def _receipt_error_summary(form, formset):
    errors = []
    if form.errors:
        for field, field_errors in form.errors.items():
            label = form.fields.get(field).label if field in form.fields else field
            for err in field_errors:
                errors.append(f"{label}: {err}")
    if formset.non_form_errors():
        for err in formset.non_form_errors():
            errors.append(str(err))
    for index, item_form in enumerate(formset.forms, start=1):
        if item_form.errors:
            for field, field_errors in item_form.errors.items():
                label = item_form.fields.get(field).label if field in item_form.fields else field
                for err in field_errors:
                    errors.append(f"Linha {index} - {label}: {err}")
    return errors


def _extract_receipt_items(formset):
    items = []
    for item_form in formset.forms:
        if not item_form.cleaned_data or item_form.cleaned_data.get("DELETE"):
            continue
        product = item_form.cleaned_data.get("product")
        quantity = item_form.cleaned_data.get("quantity")
        if not product or not quantity:
            continue
        sale_price = item_form.cleaned_data.get("sale_price") or product.sale_price
        items.append(
            {
                "product": product,
                "quantity": quantity,
                "unit_cost": item_form.cleaned_data.get("unit_cost"),
                "sale_price": sale_price,
            }
        )
    return items


@login_required
@business_required
@permission_required("inventory.view_goodsreceipt", raise_exception=True)
def receipt_list(request):
    query = request.GET.get("q", "").strip()
    supplier_id = request.GET.get("supplier", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if not date_from and not date_to:
        today = timezone.localdate()
        date_from = (today - timedelta(days=6)).isoformat()
        date_to = today.isoformat()
    receipts = (
        GoodsReceipt.objects.filter(business=request.business)
        .select_related("supplier", "purchase")
        .prefetch_related("items")
    )
    if query:
        receipts = receipts.filter(
            Q(document_number__icontains=query)
            | Q(supplier__name__icontains=query)
        )
    if supplier_id:
        receipts = receipts.filter(supplier_id=supplier_id)
    if date_from:
        receipts = receipts.filter(document_date__gte=date_from)
    if date_to:
        receipts = receipts.filter(document_date__lte=date_to)
    total_receipts = receipts.count()
    total_items = receipts.aggregate(total=Sum("items__quantity")).get("total") or 0
    supplier_count = receipts.values("supplier_id").distinct().count()
    paginator = Paginator(receipts.order_by("-document_date", "-created_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    suppliers = request.business.suppliers.filter(is_active=True).order_by("name")
    return render(
        request,
        "inventory/receipt_list.html",
        {
            "page": page,
            "query": query,
            "supplier_id": supplier_id,
            "date_from": date_from,
            "date_to": date_to,
            "suppliers": suppliers,
            "total_receipts": total_receipts,
            "total_items": total_items,
            "supplier_count": supplier_count,
        },
    )


@login_required
@business_required
@permission_required("inventory.add_goodsreceipt", raise_exception=True)
def receipt_create(request):
    products = Product.objects.filter(business=request.business).order_by("name")
    purchases = (
        Purchase.objects.filter(
            business=request.business, purchase_type=Purchase.TYPE_STOCK
        )
        .exclude(status=Purchase.STATUS_CANCELED)
        .order_by("-purchase_date")
    )
    product_prices = {
        str(product.id): {"sale": str(product.sale_price), "cost": str(product.cost_price)}
        for product in products
    }
    purchase_map = {
        str(purchase.id): {"supplier": purchase.supplier_id or "", "code": purchase.code or ""}
        for purchase in purchases
    }
    if request.method == "POST":
        form = GoodsReceiptForm(request.POST, business=request.business)
        formset = GoodsReceiptItemFormSet(
            request.POST,
            prefix="items",
            form_kwargs={"products": products},
        )
        if form.is_valid() and formset.is_valid():
            if form.cleaned_data.get("cash_movement") and not request.user.has_perm(
                "finance.add_cashmovement"
            ):
                form.add_error(
                    "cash_movement", "Sem permissao para registar movimento de caixa."
                )
                return render(
                    request,
                    "inventory/receipt_form.html",
                    {
                        "form": form,
                        "formset": formset,
                        "error_summary": _receipt_error_summary(form, formset),
                        "product_prices": json.dumps(product_prices),
                    },
                )
            items = _extract_receipt_items(formset)
            try:
                receipt = receive_goods(
                    business=request.business,
                    user=request.user,
                    receipt_data=form.cleaned_data,
                    items_data=items,
                    create_cash_movement=form.cleaned_data.get("cash_movement", False),
                    payment_method=form.cleaned_data.get("payment_method"),
                    purchase=form.cleaned_data.get("purchase"),
                )
            except ValueError as exc:
                return render(
                    request,
                    "inventory/receipt_form.html",
                    {
                        "form": form,
                        "formset": formset,
                        "error_summary": [str(exc)],
                        "product_prices": json.dumps(product_prices),
                        "purchase_map": json.dumps(purchase_map),
                    },
                )
            messages.success(request, "Rececao registada com sucesso.")
            return redirect("inventory:receipt_detail", pk=receipt.id)
        error_summary = _receipt_error_summary(form, formset)
        return render(
            request,
            "inventory/receipt_form.html",
            {
                "form": form,
                "formset": formset,
                "error_summary": error_summary,
                "product_prices": json.dumps(product_prices),
                "purchase_map": json.dumps(purchase_map),
            },
        )
    form = GoodsReceiptForm(business=request.business)
    formset = GoodsReceiptItemFormSet(prefix="items", form_kwargs={"products": products})
    return render(
        request,
        "inventory/receipt_form.html",
        {
            "form": form,
            "formset": formset,
            "product_prices": json.dumps(product_prices),
            "purchase_map": json.dumps(purchase_map),
        },
    )


@login_required
@business_required
@permission_required("inventory.view_goodsreceipt", raise_exception=True)
def receipt_detail(request, pk):
    receipt = get_object_or_404(
        GoodsReceipt.objects.select_related(
            "supplier",
            "created_by",
            "cash_movement",
            "cash_movement__payment_method",
            "purchase",
        ),
        pk=pk,
        business=request.business,
    )
    items = receipt.items.select_related("product").all()
    total_quantity = items.aggregate(total=Sum("quantity")).get("total") or 0
    total_cost = sum(
        [item.quantity * item.unit_cost for item in items if item.unit_cost is not None],
        Decimal("0"),
    )
    return render(
        request,
        "inventory/receipt_detail.html",
        {
            "receipt": receipt,
            "items": items,
            "total_quantity": total_quantity,
            "total_cost": total_cost,
        },
    )


@login_required
@business_required
@permission_required("catalog.add_product", raise_exception=True)
def stock_import(request):
    if request.method == "POST":
        form = StockImportForm(request.POST, request.FILES)
        if form.is_valid():
            service = ExcelImportService(business=request.business, user=request.user)
            result = service.import_workbook(form.cleaned_data["file"])
            if result.rows_failed:
                messages.warning(
                    request,
                    (
                        f"Importacao concluida com {result.rows_failed} linha(s) com erro. "
                        f"{result.failed_products_count} produto(s) nao carregado(s)."
                    ),
                )
            else:
                messages.success(request, "Importacao concluida sem erros.")
            return render(
                request,
                "inventory/stock_import.html",
                {"form": StockImportForm(), "result": result},
            )
    else:
        form = StockImportForm()
    return render(request, "inventory/stock_import.html", {"form": form})
