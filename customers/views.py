from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render

from customers.forms import CustomerForm, QuickCustomerForm
from customers.models import Customer
from billing.models import Invoice
from receivables.models import Payment, Receivable
from sales.models import Sale
from deliveries.models import DeliveryGuide, DeliveryGuideItem
from quotations.models import Quotation
from tenants.decorators import business_required


@login_required
@business_required
@permission_required("customers.view_customer", raise_exception=True)
def customer_list(request):
    query = request.GET.get("q", "").strip()
    customers = Customer.objects.filter(business=request.business)
    if query:
        customers = customers.filter(
            Q(name__icontains=query) | Q(phone__icontains=query)
        )

    total_customers = customers.count()
    company_customers = customers.filter(
        customer_type=Customer.TYPE_COMPANY
    ).count()
    individual_customers = customers.filter(
        customer_type=Customer.TYPE_INDIVIDUAL
    ).count()
    customers_with_email = customers.exclude(email="").count()

    open_receivable_customer_ids = set(
        Receivable.objects.filter(
            business=request.business,
            status=Receivable.STATUS_OPEN,
            customer_id__in=customers.values("id"),
        )
        .values_list("customer_id", flat=True)
        .distinct()
    )
    customers_with_open_credit = len(open_receivable_customer_ids)

    paginator = Paginator(customers.order_by("name"), 20)
    page = paginator.get_page(request.GET.get("page"))
    open_receivables = {}
    open_receivable_totals = {}
    customer_ids = [customer.id for customer in page.object_list]
    if customer_ids:
        receivables = (
            Receivable.objects.filter(
                business=request.business,
                customer_id__in=customer_ids,
                status=Receivable.STATUS_OPEN,
            )
            .order_by("customer_id", "-created_at")
        )
        for receivable in receivables:
            if receivable.customer_id not in open_receivables:
                open_receivables[receivable.customer_id] = receivable
        totals = (
            Receivable.objects.filter(
                business=request.business,
                customer_id__in=customer_ids,
                status=Receivable.STATUS_OPEN,
            )
            .values("customer_id")
            .annotate(
                total=Coalesce(
                    Sum(
                        ExpressionWrapper(
                            F("original_amount") - F("total_paid"),
                            output_field=DecimalField(
                                max_digits=12,
                                decimal_places=2,
                            ),
                        )
                    ),
                    Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                )
            )
        )
        open_receivable_totals = {
            row["customer_id"]: row["total"] for row in totals
        }
    for customer in page.object_list:
        customer.open_receivable = open_receivables.get(customer.id)
        customer.open_receivable_total = open_receivable_totals.get(customer.id, 0)
    return render(
        request,
        "customers/customer_list.html",
        {
            "page": page,
            "query": query,
            "total_customers": total_customers,
            "company_customers": company_customers,
            "individual_customers": individual_customers,
            "customers_with_email": customers_with_email,
            "customers_with_open_credit": customers_with_open_credit,
        },
    )


@login_required
@business_required
@permission_required("customers.add_customer", raise_exception=True)
def customer_create(request):
    if request.method == "POST":
        form = CustomerForm(request.POST, business=request.business)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.business = request.business
            customer.created_by = request.user
            customer.save()
            messages.success(request, "Cliente criado com sucesso.")
            return redirect("customers:list")
    else:
        form = CustomerForm(business=request.business)
    return render(request, "customers/customer_form.html", {"form": form})


@login_required
@business_required
@permission_required("customers.change_customer", raise_exception=True)
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk, business=request.business)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer, business=request.business)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.updated_by = request.user
            customer.save()
            messages.success(request, "Cliente atualizado com sucesso.")
            return redirect("customers:list")
    else:
        form = CustomerForm(instance=customer, business=request.business)
    return render(
        request, "customers/customer_form.html", {"form": form, "customer": customer}
    )


@login_required
@business_required
@permission_required("customers.view_customer", raise_exception=True)
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk, business=request.business)
    sales_queryset = Sale.objects.filter(business=request.business, customer=customer)
    sales_total_count = sales_queryset.count()
    sales_confirmed_count = sales_queryset.filter(status=Sale.STATUS_CONFIRMED).count()
    sales = sales_queryset.order_by("-sale_date")[:10]
    receivables_queryset = Receivable.objects.filter(
        business=request.business, customer=customer
    )
    receivables_total_count = receivables_queryset.count()
    receivables_open_count = receivables_queryset.filter(
        status=Receivable.STATUS_OPEN
    ).count()
    receivables = receivables_queryset.order_by("-created_at")
    invoices = Invoice.objects.filter(
        business=request.business, customer=customer
    ).order_by("-issue_date")
    invoices_count = invoices.count()
    quotations = Quotation.objects.filter(
        business=request.business, customer=customer
    ).order_by("-issue_date")
    quotations_count = quotations.count()
    delivery_guides = DeliveryGuide.objects.filter(
        business=request.business, customer=customer
    ).order_by("-issued_at")
    delivery_guides_count = delivery_guides.count()
    payments_queryset = Payment.objects.filter(
        business=request.business, receivable__customer=customer
    ).select_related("receivable")
    payments_count = payments_queryset.count()
    payments = payments_queryset.order_by("-paid_at")[:10]

    deposit_sales_queryset = (
        sales_queryset.filter(
            sale_type=Sale.SALE_TYPE_DEPOSIT,
            status=Sale.STATUS_CONFIRMED,
        )
        .prefetch_related("items__product", "invoices__payments")
        .order_by("-sale_date")
    )
    deposit_sales = list(deposit_sales_queryset)
    deposit_sales_count = len(deposit_sales)
    deposit_sale_ids = [sale.id for sale in deposit_sales]
    delivered_map = {}
    if deposit_sale_ids:
        delivered_rows = (
            DeliveryGuideItem.objects.filter(
                sale_item__sale_id__in=deposit_sale_ids,
                guide__status__in=[
                    DeliveryGuide.STATUS_ISSUED,
                    DeliveryGuide.STATUS_PARTIAL,
                    DeliveryGuide.STATUS_DELIVERED,
                ],
            )
            .values("sale_item_id")
            .annotate(total=Coalesce(Sum("quantity"), 0))
        )
        delivered_map = {
            row["sale_item_id"]: int(row["total"] or 0) for row in delivered_rows
        }

    deposit_total_amount = 0
    deposit_total_paid = 0
    deposit_total_balance = 0
    deposit_pending_total_qty = 0
    deposit_open_count = 0
    for sale in deposit_sales:
        latest_invoice = None
        invoices = sorted(
            sale.invoices.all(),
            key=lambda inv: inv.created_at or inv.issue_date,
            reverse=True,
        )
        if invoices:
            latest_invoice = invoices[0]
        deposit_paid = latest_invoice.amount_paid if latest_invoice else 0
        deposit_balance = sale.total - deposit_paid
        if deposit_balance < 0:
            deposit_balance = 0

        pending_items = []
        remaining_total_qty = 0
        for item in sale.items.all():
            net_qty = item.quantity - (item.returned_quantity or 0)
            if net_qty < 0:
                net_qty = 0
            delivered_qty = delivered_map.get(item.id, 0)
            remaining_qty = net_qty - delivered_qty
            if remaining_qty < 0:
                remaining_qty = 0
            remaining_total_qty += remaining_qty
            if remaining_qty > 0:
                pending_items.append(
                    {
                        "product_name": item.product.name,
                        "remaining_qty": remaining_qty,
                    }
                )

        sale.deposit_invoice = latest_invoice
        sale.deposit_paid = deposit_paid
        sale.deposit_balance = deposit_balance
        sale.deposit_pending_items = pending_items
        sale.deposit_remaining_qty = remaining_total_qty
        sale.deposit_open = remaining_total_qty > 0
        if sale.deposit_open:
            deposit_open_count += 1

        deposit_total_amount += sale.total
        deposit_total_paid += deposit_paid
        deposit_total_balance += deposit_balance
        deposit_pending_total_qty += remaining_total_qty

    total_spent = (
        sales_queryset.filter(status=Sale.STATUS_CONFIRMED).aggregate(
            total=Coalesce(
                Sum("total"),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
            )
        )["total"]
        or 0
    )
    balance_expression = ExpressionWrapper(
        F("original_amount") - F("total_paid"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    open_balance = (
        receivables_queryset.filter(status=Receivable.STATUS_OPEN).aggregate(
            total=Coalesce(
                Sum(balance_expression),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
            )
        )["total"]
        or 0
    )
    return render(
        request,
        "customers/customer_detail.html",
        {
            "customer": customer,
            "sales": sales,
            "receivables": receivables,
            "invoices": invoices,
            "quotations": quotations,
            "delivery_guides": delivery_guides,
            "payments": payments,
            "total_spent": total_spent,
            "open_balance": open_balance,
            "sales_total_count": sales_total_count,
            "sales_confirmed_count": sales_confirmed_count,
            "receivables_total_count": receivables_total_count,
            "receivables_open_count": receivables_open_count,
            "invoices_count": invoices_count,
            "quotations_count": quotations_count,
            "delivery_guides_count": delivery_guides_count,
            "payments_count": payments_count,
            "deposit_sales": deposit_sales,
            "deposit_sales_count": deposit_sales_count,
            "deposit_open_count": deposit_open_count,
            "deposit_total_amount": deposit_total_amount,
            "deposit_total_paid": deposit_total_paid,
            "deposit_total_balance": deposit_total_balance,
            "deposit_pending_total_qty": deposit_pending_total_qty,
        },
    )


@login_required
@business_required
@permission_required("customers.add_customer", raise_exception=True)
def customer_quick_create(request):
    if request.method == "POST":
        form = QuickCustomerForm(request.POST, business=request.business)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.business = request.business
            customer.created_by = request.user
            customer.save()
            form = QuickCustomerForm(business=request.business)
            return render(
                request,
                "customers/partials/customer_quick_modal.html",
                {"form": form, "created": True, "customer": customer},
            )
    else:
        form = QuickCustomerForm(business=request.business)
    return render(
        request,
        "customers/partials/customer_quick_modal.html",
        {"form": form},
    )
