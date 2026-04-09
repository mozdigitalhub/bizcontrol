from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from receivables.forms import PaymentForm
from receivables.models import Receivable
from receivables.services import register_payment
from tenants.decorators import business_required, feature_required
from tenants.models import Business


@login_required
@business_required
@feature_required(
    Business.FEATURE_ALLOW_CREDIT_SALES,
    message="Crédito não está ativo para este negócio.",
)
@permission_required("receivables.view_receivable", raise_exception=True)
def receivable_list(request):
    status = request.GET.get("status", Receivable.STATUS_OPEN)
    query = request.GET.get("q", "").strip()
    customer_id = request.GET.get("customer", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if not date_from and not date_to:
        today = timezone.localdate()
        date_from = (today - timedelta(days=6)).isoformat()
        date_to = today.isoformat()
    receivables = Receivable.objects.filter(business=request.business).select_related("customer")
    if query:
        receivables = receivables.filter(customer__name__icontains=query)
    if customer_id:
        receivables = receivables.filter(customer_id=customer_id)
    if date_from:
        receivables = receivables.filter(created_at__date__gte=date_from)
    if date_to:
        receivables = receivables.filter(created_at__date__lte=date_to)
    if status in [Receivable.STATUS_OPEN, Receivable.STATUS_SETTLED]:
        receivables = receivables.filter(status=status)
    totals = receivables.aggregate(
        total_amount=Sum("original_amount"),
        total_paid_amount=Sum("total_paid"),
    )
    total_amount = totals["total_amount"] or 0
    total_paid_amount = totals["total_paid_amount"] or 0
    total_balance = total_amount - total_paid_amount
    paginator = Paginator(receivables.order_by("-created_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "receivables/receivable_list.html",
        {
            "page": page,
            "status": status,
            "query": query,
            "customer_id": customer_id,
            "date_from": date_from,
            "date_to": date_to,
            "customers": request.business.customers.order_by("name"),
            "total_amount": total_amount,
            "total_paid": total_paid_amount,
            "total_balance": total_balance,
        },
    )


@login_required
@business_required
@feature_required(
    Business.FEATURE_ALLOW_CREDIT_SALES,
    message="Crédito não está ativo para este negócio.",
)
@permission_required("receivables.view_receivable", raise_exception=True)
def receivable_detail(request, pk):
    receivable = get_object_or_404(Receivable, pk=pk, business=request.business)
    payment_form = PaymentForm()
    return render(
        request,
        "receivables/receivable_detail.html",
        {"receivable": receivable, "payment_form": payment_form},
    )


@login_required
@business_required
@feature_required(
    Business.FEATURE_ALLOW_CREDIT_SALES,
    message="Crédito não está ativo para este negócio.",
)
@permission_required("receivables.add_payment", raise_exception=True)
def payment_modal(request, pk):
    receivable = get_object_or_404(Receivable, pk=pk, business=request.business)
    target_id = request.GET.get("target", "receivable-summary")
    form = PaymentForm()
    return render(
        request,
        "receivables/partials/payment_modal.html",
        {"receivable": receivable, "form": form, "target_id": target_id},
    )


@login_required
@business_required
@feature_required(
    Business.FEATURE_ALLOW_CREDIT_SALES,
    message="Crédito não está ativo para este negócio.",
)
@permission_required("receivables.add_payment", raise_exception=True)
def payment_create(request, pk):
    receivable = get_object_or_404(Receivable, pk=pk, business=request.business)
    target_id = request.POST.get("target", "receivable-summary")
    form = PaymentForm()
    payment_success = False
    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                register_payment(
                    receivable_id=receivable.id,
                    business=request.business,
                    amount=form.cleaned_data["amount"],
                    method=form.cleaned_data["method"],
                    user=request.user,
                    notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(request, "Pagamento registado.")
                payment_success = True
                if request.headers.get("HX-Request") and target_id == "modal-container":
                    receivable.refresh_from_db()
                    return render(
                        request,
                        "receivables/partials/payment_modal.html",
                        {
                            "receivable": receivable,
                            "form": PaymentForm(),
                            "target_id": target_id,
                            "success": True,
                        },
                    )
            except Exception as exc:
                messages.error(request, str(exc))
        else:
            messages.error(request, "Dados invalidos.")
    if request.headers.get("HX-Request") and target_id == "receivable-summary":
        receivable.refresh_from_db()
        response = render(
            request,
            "receivables/partials/receivable_summary.html",
            {"receivable": receivable},
        )
        if payment_success:
            response["HX-Trigger"] = "receivablePaymentSuccess"
        return response
    if request.headers.get("HX-Request"):
        return render(
            request,
            "receivables/partials/payment_modal.html",
            {"receivable": receivable, "form": form, "target_id": target_id},
        )
    return redirect("receivables:detail", pk=receivable.id)
