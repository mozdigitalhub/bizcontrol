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
from deliveries.models import DeliveryGuide
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
    paginator = Paginator(customers.order_by("name"), 20)
    page = paginator.get_page(request.GET.get("page"))
    open_receivables = {}
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
    for customer in page.object_list:
        customer.open_receivable = open_receivables.get(customer.id)
    return render(
        request,
        "customers/customer_list.html",
        {
            "page": page,
            "query": query,
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
    sales = sales_queryset.order_by("-sale_date")[:10]
    receivables_queryset = Receivable.objects.filter(
        business=request.business, customer=customer
    )
    receivables = receivables_queryset.order_by("-created_at")
    invoices = Invoice.objects.filter(
        business=request.business, customer=customer
    ).order_by("-issue_date")
    quotations = Quotation.objects.filter(
        business=request.business, customer=customer
    ).order_by("-issue_date")
    delivery_guides = DeliveryGuide.objects.filter(
        business=request.business, customer=customer
    ).order_by("-issued_at")
    payments = Payment.objects.filter(
        business=request.business, receivable__customer=customer
    ).select_related("receivable").order_by("-paid_at")[:10]

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
