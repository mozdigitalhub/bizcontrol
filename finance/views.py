from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from finance.forms import (
    ExpenseCategoryForm,
    ExpenseForm,
    PurchaseForm,
    PurchaseItemFormSet,
    SupplierForm,
)
from finance.models import CashMovement, Expense, ExpenseCategory, FinancialAccount, Purchase, Supplier
from billing.models import InvoicePayment
from finance.services import cancel_expense, cancel_purchase, confirm_purchase, pay_expense
from tenants.decorators import business_required, module_required
from tenants.models import Business


def _purchase_error_summary(form, formset):
    errors = []
    for field, field_errors in form.errors.items():
        label = form.fields.get(field).label if field in form.fields else "Geral"
        for err in field_errors:
            errors.append(f"{label}: {err}")
    for idx, item_errors in enumerate(formset.errors):
        if not item_errors:
            continue
        for field, field_errors in item_errors.items():
            label = (
                formset.forms[idx].fields.get(field).label
                if field in formset.forms[idx].fields
                else "Geral"
            )
            for err in field_errors:
                errors.append(f"Item {idx + 1} - {label}: {err}")
    for err in formset.non_form_errors():
        errors.append(str(err))
    return errors


@login_required
@business_required
@module_required(Business.MODULE_CASHFLOW, message="Modulo financeiro desativado.")
@permission_required("finance.view_purchase", raise_exception=True)
def purchase_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if not date_from and not date_to:
        today = timezone.localdate()
        date_from = (today - timedelta(days=6)).isoformat()
        date_to = today.isoformat()
    purchases = Purchase.objects.filter(business=request.business).select_related("supplier")
    if query:
        purchases = purchases.filter(
            Q(supplier__name__icontains=query)
            | Q(id__icontains=query)
            | Q(code__icontains=query)
        )
    if status:
        purchases = purchases.filter(status=status)
    if date_from:
        purchases = purchases.filter(purchase_date__gte=date_from)
    if date_to:
        purchases = purchases.filter(purchase_date__lte=date_to)
    totals = purchases.aggregate(total=Sum("total"))
    confirmed_count = purchases.filter(status=Purchase.STATUS_CONFIRMED).count()
    draft_count = purchases.filter(status=Purchase.STATUS_DRAFT).count()
    paginator = Paginator(purchases.order_by("-purchase_date"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "finance/purchase_list.html",
        {
            "page": page,
            "query": query,
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
            "status_choices": Purchase.STATUS_CHOICES,
            "total_amount": totals["total"] or Decimal("0"),
            "confirmed_count": confirmed_count,
            "draft_count": draft_count,
        },
    )


@login_required
@business_required
@module_required(Business.MODULE_CASHFLOW, message="Modulo financeiro desativado.")
@permission_required("finance.view_cashmovement", raise_exception=True)
def cashflow_list(request):
    query = request.GET.get("q", "").strip()
    movement_type = request.GET.get("movement_type", "").strip()
    method = request.GET.get("method", "").strip()
    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()

    movements = CashMovement.objects.filter(business=request.business)
    if not start_date and not end_date:
        today = timezone.localdate()
        start_date = today.isoformat()
        end_date = today.isoformat()
    if query:
        movements = movements.filter(Q(notes__icontains=query))
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    if method:
        movements = movements.filter(method=method)
    if start_date:
        movements = movements.filter(happened_at__date__gte=start_date)
    if end_date:
        movements = movements.filter(happened_at__date__lte=end_date)

    totals = movements.aggregate(
        total_in=Sum("amount", filter=Q(movement_type=CashMovement.MOVEMENT_IN)),
        total_out=Sum("amount", filter=Q(movement_type=CashMovement.MOVEMENT_OUT)),
    )
    total_in = totals.get("total_in") or Decimal("0")
    total_out = totals.get("total_out") or Decimal("0")
    net_total = total_in - total_out

    category_labels = {
        FinancialAccount.CATEGORY_CASH: "Caixa",
        FinancialAccount.CATEGORY_BANK: "Banco",
        FinancialAccount.CATEGORY_MOBILE: "Carteiras moveis",
    }
    category_totals = []
    for category_key, label in category_labels.items():
        category_movements = movements.filter(category=category_key)
        category_totals.append(
            {
                "key": category_key,
                "label": label,
                "total_in": category_movements.aggregate(
                    total=Sum("amount", filter=Q(movement_type=CashMovement.MOVEMENT_IN))
                ).get("total")
                or Decimal("0"),
                "total_out": category_movements.aggregate(
                    total=Sum("amount", filter=Q(movement_type=CashMovement.MOVEMENT_OUT))
                ).get("total")
                or Decimal("0"),
            }
        )
    for item in category_totals:
        item["net_total"] = item["total_in"] - item["total_out"]

    paginator = Paginator(movements.order_by("-happened_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    invoice_payment_ids = {
        movement.reference_id
        for movement in page.object_list
        if movement.reference_type == "invoice_payment" and movement.reference_id
    }
    purchase_ids = {
        movement.reference_id
        for movement in page.object_list
        if movement.reference_type in {"purchase", "purchase_cancel"} and movement.reference_id
    }
    invoice_payment_map = {
        payment.id: payment
        for payment in InvoicePayment.objects.filter(
            business=request.business, id__in=invoice_payment_ids
        ).select_related("invoice")
    }
    purchase_map = {
        purchase.id: purchase
        for purchase in Purchase.objects.filter(
            business=request.business, id__in=purchase_ids
        ).only("id", "code")
    }
    for movement in page.object_list:
        movement.reference_label = "-"
        movement.reference_invoice_id = None
        movement.reference_invoice_code = ""
        movement.reference_purchase_id = None
        movement.reference_purchase_code = ""
        movement.notes_label = movement.notes or "-"
        if movement.reference_type == "invoice_payment" and movement.reference_id:
            payment = invoice_payment_map.get(movement.reference_id)
            if payment and payment.invoice:
                invoice_code = payment.invoice.code or str(payment.invoice.invoice_number)
                movement.reference_label = f"IP-{invoice_code}-{payment.id}"
                movement.reference_invoice_id = payment.invoice_id
                movement.reference_invoice_code = invoice_code
                movement.notes_label = invoice_code
            else:
                movement.reference_label = f"Pagamento #{movement.reference_id}"
        elif movement.reference_type in {"purchase", "purchase_cancel"} and movement.reference_id:
            purchase = purchase_map.get(movement.reference_id)
            if purchase:
                purchase_code = purchase.code or f"C-{purchase.id}"
                movement.reference_label = purchase_code
                movement.reference_purchase_id = purchase.id
                movement.reference_purchase_code = purchase_code
                movement.notes_label = purchase_code
        elif movement.reference_type:
            movement.reference_label = movement.reference_type.replace("_", " ").title()
    return render(
        request,
        "finance/cashflow_list.html",
        {
            "page": page,
            "query": query,
            "movement_type": movement_type,
            "method": method,
            "start_date": start_date,
            "end_date": end_date,
            "movement_choices": CashMovement.MOVEMENT_CHOICES,
            "method_choices": CashMovement.METHOD_CHOICES,
            "total_in": total_in,
            "total_out": total_out,
            "net_total": net_total,
            "category_totals": category_totals,
        },
    )


@login_required
@business_required
@module_required(Business.MODULE_CASHFLOW, message="Modulo financeiro desativado.")
@permission_required("finance.view_cashmovement", raise_exception=True)
def cashflow_detail_modal(request, pk):
    movement = get_object_or_404(CashMovement, pk=pk, business=request.business)
    return render(
        request,
        "finance/partials/cashmovement_detail_modal.html",
        {"movement": movement},
    )


@login_required
@business_required
@module_required(Business.MODULE_CASHFLOW, message="Modulo financeiro desativado.")
@permission_required("finance.add_purchase", raise_exception=True)
def purchase_create(request):
    is_htmx = request.headers.get("HX-Request") == "true"
    if request.method == "POST":
        form = PurchaseForm(request.POST)
        form.fields["supplier"].queryset = Supplier.objects.filter(business=request.business)
        form.fields["supplier"].widget.attrs["data-placeholder"] = "Pesquisar fornecedor..."
        formset = PurchaseItemFormSet(request.POST, prefix="items")
        for item_form in formset:
            if "product" in item_form.fields:
                item_form.fields["product"].queryset = Product.objects.filter(
                    business=request.business
                )
                product_label = request.business.ui_labels.get("product", "Produto").lower()
                item_form.fields["product"].widget.attrs["data-placeholder"] = (
                    f"Pesquisar {product_label}..."
                )
        if hasattr(formset, "empty_form"):
            formset.empty_form.fields["product"].widget.attrs["data-placeholder"] = (
                f"Pesquisar {request.business.ui_labels.get('product', 'Produto').lower()}..."
            )
        form_valid = form.is_valid()
        formset_valid = formset.is_valid()
        if not (form_valid and formset_valid):
            messages.error(request, "Revise os campos obrigatorios antes de confirmar.")
            error_summary = _purchase_error_summary(form, formset)
            template = "finance/partials/purchase_modal.html" if is_htmx else "finance/purchase_form.html"
            return render(
                request,
                template,
                {"form": form, "formset": formset, "error_summary": error_summary},
            )

        if form_valid and formset_valid:
            action = request.POST.get("action", "confirm")
            if action == "confirm" and not form.cleaned_data.get("payment_method"):
                form.add_error("payment_method", "Selecione o metodo de pagamento.")
            if form.cleaned_data.get("purchase_type") == Purchase.TYPE_INTERNAL:
                if not form.cleaned_data.get("internal_description"):
                    form.add_error("internal_description", "Informe a descricao.")
                if (form.cleaned_data.get("internal_amount") or Decimal("0")) <= 0:
                    form.add_error("internal_amount", "Informe o valor.")

            valid_items = []
            if form.cleaned_data.get("purchase_type") == Purchase.TYPE_STOCK:
                for item_form in formset:
                    if not item_form.cleaned_data or item_form.cleaned_data.get("DELETE"):
                        continue
                    product = item_form.cleaned_data.get("product")
                    quantity = item_form.cleaned_data.get("quantity")
                    unit_cost = item_form.cleaned_data.get("unit_cost")
                    if not product and not quantity and not unit_cost:
                        continue
                    if not product:
                        item_form.add_error("product", "Selecione o produto.")
                    if not quantity:
                        item_form.add_error("quantity", "Informe a quantidade.")
                    if not unit_cost:
                        item_form.add_error("unit_cost", "Informe o custo unitario.")
                    if item_form.errors:
                        continue
                    valid_items.append(item_form)
                if not valid_items:
                    form.add_error(None, "Adicione pelo menos um produto.")

            if form.errors or formset.non_form_errors() or any(f.errors for f in formset):
                error_summary = _purchase_error_summary(form, formset)
                template = "finance/partials/purchase_modal.html" if is_htmx else "finance/purchase_form.html"
                return render(
                    request,
                    template,
                    {"form": form, "formset": formset, "error_summary": error_summary},
                )

            purchase = form.save(commit=False)
            purchase.business = request.business
            purchase.created_by = request.user
            purchase.status = Purchase.STATUS_DRAFT
            purchase.save()
            if purchase.purchase_type == Purchase.TYPE_STOCK:
                for item_form in valid_items:
                    product = item_form.cleaned_data["product"]
                    quantity = item_form.cleaned_data["quantity"]
                    unit_cost = item_form.cleaned_data["unit_cost"]
                    line_total = quantity * unit_cost
                    purchase.items.create(
                        product=product,
                        quantity=quantity,
                        unit_cost=unit_cost,
                        line_total=line_total,
                    )
            action = request.POST.get("action", "confirm")
            if action == "confirm":
                try:
                    confirm_purchase(
                        purchase_id=purchase.id,
                        business=request.business,
                        user=request.user,
                    )
                    messages.success(request, "Compra confirmada.")
                    if is_htmx:
                        response = HttpResponse()
                        response["HX-Redirect"] = reverse("finance:purchase_list")
                        return response
                    return redirect("finance:purchase_list")
                except Exception as exc:
                    form.add_error(None, str(exc))
                    error_summary = _purchase_error_summary(form, formset)
                    template = "finance/partials/purchase_modal.html" if is_htmx else "finance/purchase_form.html"
                    return render(
                        request,
                        template,
                        {"form": form, "formset": formset, "error_summary": error_summary},
                    )
            else:
                messages.success(request, "Compra guardada como rascunho.")
                if is_htmx:
                    response = HttpResponse()
                    response["HX-Redirect"] = reverse("finance:purchase_detail", kwargs={"pk": purchase.id})
                    return response
                return redirect("finance:purchase_detail", pk=purchase.id)
    else:
        form = PurchaseForm()
        form.fields["supplier"].queryset = Supplier.objects.filter(business=request.business)
        form.fields["supplier"].widget.attrs["data-placeholder"] = "Pesquisar fornecedor..."
        formset = PurchaseItemFormSet(prefix="items")
        for item_form in formset:
            if "product" in item_form.fields:
                item_form.fields["product"].queryset = Product.objects.filter(
                    business=request.business
                )
                product_label = request.business.ui_labels.get("product", "Produto").lower()
                item_form.fields["product"].widget.attrs["data-placeholder"] = (
                    f"Pesquisar {product_label}..."
                )
        if hasattr(formset, "empty_form"):
            formset.empty_form.fields["product"].widget.attrs["data-placeholder"] = (
                f"Pesquisar {request.business.ui_labels.get('product', 'Produto').lower()}..."
            )
    template = "finance/partials/purchase_modal.html" if is_htmx else "finance/purchase_form.html"
    return render(request, template, {"form": form, "formset": formset})


@login_required
@business_required
@module_required(Business.MODULE_CASHFLOW, message="Modulo financeiro desativado.")
@permission_required("finance.view_purchase", raise_exception=True)
def purchase_detail(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk, business=request.business)
    items = purchase.items.select_related("product").all()
    receipts = purchase.receipts.select_related("supplier").order_by("-document_date")
    template = (
        "finance/partials/purchase_detail_modal.html"
        if request.headers.get("HX-Request") == "true"
        else "finance/purchase_detail.html"
    )
    return render(
        request,
        template,
        {"purchase": purchase, "items": items, "receipts": receipts},
    )


@login_required
@business_required
@module_required(Business.MODULE_CASHFLOW, message="Modulo financeiro desativado.")
@permission_required("finance.change_purchase", raise_exception=True)
def purchase_cancel(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk, business=request.business)
    if request.method == "POST":
        notes = request.POST.get("notes", "")
        try:
            cancel_purchase(
                purchase_id=purchase.id,
                business=request.business,
                user=request.user,
                notes=notes,
            )
            messages.success(request, "Compra cancelada.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("finance:purchase_detail", pk=purchase.id)
    return render(
        request,
        "finance/purchase_cancel.html",
        {"purchase": purchase},
    )


@login_required
@business_required
@module_required(Business.MODULE_CASHFLOW, message="Modulo financeiro desativado.")
@permission_required("finance.view_expense", raise_exception=True)
def expense_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    category_id = request.GET.get("category", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if not date_from and not date_to:
        today = timezone.localdate()
        date_from = (today - timedelta(days=6)).isoformat()
        date_to = today.isoformat()
    expenses = Expense.objects.filter(business=request.business).select_related("category")
    if query:
        expenses = expenses.filter(Q(title__icontains=query))
    if status:
        expenses = expenses.filter(status=status)
    if category_id:
        expenses = expenses.filter(category_id=category_id)
    if date_from:
        expenses = expenses.filter(expense_date__gte=date_from)
    if date_to:
        expenses = expenses.filter(expense_date__lte=date_to)
    totals = expenses.aggregate(total=Sum("amount"))
    paginator = Paginator(expenses.order_by("-expense_date"), 20)
    page = paginator.get_page(request.GET.get("page"))
    categories = ExpenseCategory.objects.filter(business=request.business).order_by("name")
    return render(
        request,
        "finance/expense_list.html",
        {
            "page": page,
            "query": query,
            "status": status,
            "category_id": category_id,
            "date_from": date_from,
            "date_to": date_to,
            "status_choices": Expense.STATUS_CHOICES,
            "categories": categories,
            "total_amount": totals["total"] or Decimal("0"),
        },
    )


@login_required
@business_required
@module_required(Business.MODULE_CASHFLOW, message="Modulo financeiro desativado.")
@permission_required("finance.add_expense", raise_exception=True)
def expense_create(request):
    is_htmx = request.headers.get("HX-Request") == "true"
    if request.method == "POST":
        form = ExpenseForm(request.POST, request.FILES)
        form.fields["category"].queryset = ExpenseCategory.objects.filter(
            business=request.business
        )
        form.fields["category"].widget.attrs["data-placeholder"] = "Pesquisar categoria..."
        if form.is_valid():
            action = request.POST.get("action", "confirm")
            if action == "confirm" and not form.cleaned_data.get("payment_method"):
                form.add_error("payment_method", "Selecione o metodo de pagamento.")
            if form.errors:
                template = "finance/partials/expense_modal.html" if is_htmx else "finance/expense_form.html"
                return render(request, template, {"form": form})

            expense = form.save(commit=False)
            expense.business = request.business
            expense.created_by = request.user
            expense.status = Expense.STATUS_DRAFT
            expense.save()
            if action == "confirm":
                try:
                    pay_expense(
                        expense_id=expense.id,
                        business=request.business,
                        user=request.user,
                    )
                    messages.success(request, "Despesa registada.")
                    if is_htmx:
                        response = HttpResponse()
                        response["HX-Redirect"] = reverse("finance:expense_list")
                        return response
                    return redirect("finance:expense_list")
                except Exception as exc:
                    messages.error(request, str(exc))
            else:
                messages.success(request, "Despesa guardada como rascunho.")
                if is_htmx:
                    response = HttpResponse()
                    response["HX-Redirect"] = reverse("finance:expense_detail", kwargs={"pk": expense.id})
                    return response
                return redirect("finance:expense_detail", pk=expense.id)
    else:
        form = ExpenseForm()
        form.fields["category"].queryset = ExpenseCategory.objects.filter(
            business=request.business
        )
        form.fields["category"].widget.attrs["data-placeholder"] = "Pesquisar categoria..."
    template = "finance/partials/expense_modal.html" if is_htmx else "finance/expense_form.html"
    return render(request, template, {"form": form})


@login_required
@business_required
@module_required(Business.MODULE_CASHFLOW, message="Modulo financeiro desativado.")
@permission_required("finance.view_expense", raise_exception=True)
def expense_detail(request, pk):
    expense = get_object_or_404(Expense, pk=pk, business=request.business)
    template = "finance/partials/expense_detail_modal.html" if request.headers.get("HX-Request") == "true" else "finance/expense_detail.html"
    return render(request, template, {"expense": expense})


@login_required
@business_required
@module_required(Business.MODULE_CASHFLOW, message="Modulo financeiro desativado.")
@permission_required("finance.change_expense", raise_exception=True)
def expense_cancel(request, pk):
    expense = get_object_or_404(Expense, pk=pk, business=request.business)
    if request.method == "POST":
        notes = request.POST.get("notes", "")
        try:
            cancel_expense(
                expense_id=expense.id,
                business=request.business,
                user=request.user,
                notes=notes,
            )
            messages.success(request, "Despesa cancelada.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("finance:expense_detail", pk=expense.id)
    return render(
        request,
        "finance/expense_cancel.html",
        {"expense": expense},
    )


@login_required
@business_required
@module_required(Business.MODULE_CASHFLOW, message="Modulo financeiro desativado.")
@permission_required("finance.add_supplier", raise_exception=True)
def supplier_create(request):
    if request.method == "POST":
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.business = request.business
            supplier.save()
            form = SupplierForm()
            messages.success(request, "Fornecedor criado.")
            return render(
                request,
                "finance/partials/supplier_modal.html",
                {"form": form, "created": True, "supplier": supplier},
            )
    else:
        form = SupplierForm()
    return render(request, "finance/partials/supplier_modal.html", {"form": form})


@login_required
@business_required
@module_required(Business.MODULE_CASHFLOW, message="Modulo financeiro desativado.")
@permission_required("finance.add_expensecategory", raise_exception=True)
def expense_category_create(request):
    if request.method == "POST":
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.business = request.business
            category.save()
            form = ExpenseCategoryForm()
            messages.success(request, "Categoria criada.")
            return render(
                request,
                "finance/partials/expense_category_modal.html",
                {"form": form, "created": True, "category": category},
            )
    else:
        form = ExpenseCategoryForm()
    return render(request, "finance/partials/expense_category_modal.html", {"form": form})

# Create your views here.
