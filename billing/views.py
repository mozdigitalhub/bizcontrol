from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from itertools import groupby
from django.template.loader import render_to_string

from billing.forms import InvoicePaymentForm
from billing.models import Invoice, InvoicePayment, Receipt
from receivables.models import Payment as ReceivablePayment, Receivable
from billing.services import generate_invoice, register_invoice_payment
from tenants.decorators import business_required

try:
    from weasyprint import HTML
except Exception:  # pragma: no cover - optional dependency
    HTML = None


@login_required
@business_required
@permission_required("billing.view_invoice", raise_exception=True)
def invoice_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    customer_id = request.GET.get("customer", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    min_total = request.GET.get("min_total", "").strip()
    max_total = request.GET.get("max_total", "").strip()
    invoices = Invoice.objects.filter(business=request.business).select_related("customer")
    if query:
        invoices = invoices.filter(
            Q(code__icontains=query)
            | Q(invoice_number__icontains=query)
            | Q(customer__name__icontains=query)
        )
    if status:
        invoices = invoices.filter(status=status)
    if customer_id:
        invoices = invoices.filter(customer_id=customer_id)
    if date_from:
        invoices = invoices.filter(issue_date__gte=date_from)
    if date_to:
        invoices = invoices.filter(issue_date__lte=date_to)
    if min_total:
        try:
            invoices = invoices.filter(total__gte=Decimal(min_total.replace(",", ".")))
        except Exception:
            pass
    if max_total:
        try:
            invoices = invoices.filter(total__lte=Decimal(max_total.replace(",", ".")))
        except Exception:
            pass
    paginator = Paginator(invoices.order_by("-issue_date"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "billing/invoice_list.html",
        {
            "page": page,
            "query": query,
            "status": status,
            "customer_id": customer_id,
            "date_from": date_from,
            "date_to": date_to,
            "min_total": min_total,
            "max_total": max_total,
            "status_choices": Invoice.STATUS_CHOICES,
            "customers": request.business.customers.order_by("name"),
        },
    )


@login_required
@business_required
@permission_required("billing.view_invoice", raise_exception=True)
def invoice_detail(request, pk):
    is_htmx = request.headers.get("HX-Request") == "true"
    invoice = get_object_or_404(
        Invoice.objects.select_related("customer"),
        pk=pk,
        business=request.business,
    )
    items = invoice.sale.items.all() if invoice.sale else []
    payments = list(invoice.payments.select_related("created_by").order_by("-paid_at"))
    if invoice.sale_id:
        receivable = Receivable.objects.filter(
            business=request.business, sale_id=invoice.sale_id
        ).first()
        if receivable:
            extra_payments = (
                ReceivablePayment.objects.filter(
                    receivable=receivable, invoice_payment__isnull=True
                )
                .select_related("created_by")
                .order_by("-paid_at")
            )
            payments.extend(list(extra_payments))
    payments.sort(key=lambda payment: payment.paid_at, reverse=True)
    template = "billing/partials/invoice_detail_modal.html" if is_htmx else "billing/invoice_detail.html"
    return render(
        request,
        template,
        {
            "invoice": invoice,
            "items": items,
            "payments": payments,
            "payment_form": InvoicePaymentForm(),
        },
    )


@login_required
@business_required
@permission_required("billing.add_invoice", raise_exception=True)
def invoice_create_from_sale(request, sale_id):
    if request.method == "POST":
        try:
            invoice = generate_invoice(
                sale_id=sale_id,
                business=request.business,
                user=request.user,
            )
            messages.success(request, "Fatura gerada com sucesso.")
            return redirect("billing:invoice_detail", pk=invoice.id)
        except Exception as exc:
            messages.error(request, str(exc))
    return redirect("sales:detail", pk=sale_id)


@login_required
@business_required
@permission_required("billing.view_receipt", raise_exception=True)
def receipt_list(request):
    query = request.GET.get("q", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    receipts = Receipt.objects.filter(business=request.business).select_related(
        "invoice",
        "invoice__sale",
        "invoice_payment",
        "invoice_payment__invoice",
        "invoice_payment__invoice__sale",
        "payment",
        "payment__receivable",
        "payment__receivable__sale",
    )
    if query:
        receipts = receipts.filter(
            Q(code__icontains=query)
            | Q(receipt_number__icontains=query)
            | Q(invoice__invoice_number__icontains=query)
            | Q(invoice__code__icontains=query)
        )
    if date_from:
        receipts = receipts.filter(issue_date__gte=date_from)
    if date_to:
        receipts = receipts.filter(issue_date__lte=date_to)
    paginator = Paginator(receipts.order_by("-issue_date"), 20)
    page = paginator.get_page(request.GET.get("page"))
    grouped_receipts = []
    def receipt_sale_id(receipt):
        if receipt.invoice and receipt.invoice.sale_id:
            return receipt.invoice.sale_id
        if receipt.invoice_payment and receipt.invoice_payment.invoice_id:
            return receipt.invoice_payment.invoice.sale_id
        if receipt.payment and receipt.payment.receivable_id:
            return receipt.payment.receivable.sale_id
        return None
    for sale_id, items in groupby(page.object_list, key=receipt_sale_id):
        items_list = list(items)
        sale = None
        if items_list:
            sample = items_list[0]
            if sample.invoice and sample.invoice.sale_id:
                sale = sample.invoice.sale
            elif sample.invoice_payment and sample.invoice_payment.invoice_id:
                sale = sample.invoice_payment.invoice.sale
            elif sample.payment and sample.payment.receivable_id:
                sale = sample.payment.receivable.sale
        grouped_receipts.append({"sale": sale, "receipts": items_list})
    return render(
        request,
        "billing/receipt_list.html",
        {
            "page": page,
            "grouped_receipts": grouped_receipts,
            "query": query,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@login_required
@business_required
@permission_required("billing.view_receipt", raise_exception=True)
def receipt_detail(request, pk):
    is_htmx = request.headers.get("HX-Request") == "true"
    receipt = get_object_or_404(Receipt, pk=pk, business=request.business)
    template = (
        "billing/partials/receipt_detail_modal.html"
        if is_htmx
        else "billing/receipt_detail.html"
    )
    return render(request, template, {"receipt": receipt})


@login_required
@business_required
@permission_required("billing.add_invoicepayment", raise_exception=True)
def invoice_payment_modal(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, business=request.business)
    initial = {"amount": invoice.balance}
    if invoice.sale and invoice.sale.payment_method:
        allowed = dict(InvoicePayment.METHOD_CHOICES)
        if invoice.sale.payment_method in allowed:
            initial["method"] = invoice.sale.payment_method
    form = InvoicePaymentForm(initial=initial)
    form.fields["amount"].widget.attrs["max"] = str(invoice.balance)
    return render(
        request,
        "billing/partials/invoice_payment_modal.html",
        {"invoice": invoice, "form": form},
    )


@login_required
@business_required
@permission_required("billing.add_invoicepayment", raise_exception=True)
def invoice_payment_create(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, business=request.business)
    form = InvoicePaymentForm()
    if request.method == "POST":
        form = InvoicePaymentForm(request.POST)
        if form.is_valid():
            try:
                register_invoice_payment(
                    invoice_id=invoice.id,
                    business=request.business,
                    amount=form.cleaned_data["amount"],
                    method=form.cleaned_data["method"],
                    user=request.user,
                    notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(request, "Pagamento registado.")
                if request.headers.get("HX-Request"):
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = request.build_absolute_uri(
                        redirect("billing:invoice_list").url
                    )
                    return response
                return redirect("billing:invoice_list")
            except Exception as exc:
                form.add_error(None, str(exc))
                messages.error(request, str(exc))
        else:
            messages.error(request, "Dados invalidos.")
    if request.headers.get("HX-Request"):
        return render(
            request,
            "billing/partials/invoice_payment_modal.html",
            {"invoice": invoice, "form": form},
        )
    return redirect("billing:invoice_detail", pk=invoice.id)


def _render_invoice_pdf(invoice, request, download=False):
    if HTML is None:
        return HttpResponse("WeasyPrint nao instalado.", status=500)
    items = invoice.sale.items.all() if invoice.sale else []
    html = render_to_string(
        "billing/invoice_pdf.html",
        {"invoice": invoice, "business": invoice.business, "items": items},
    )
    pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()
    response = HttpResponse(pdf, content_type="application/pdf")
    if download:
        response["Content-Disposition"] = f'attachment; filename="fatura-{invoice.invoice_number}.pdf"'
    return response


def _render_receipt_pdf(receipt, request, download=False):
    if HTML is None:
        return HttpResponse("WeasyPrint nao instalado.", status=500)
    html = render_to_string(
        "billing/receipt_pdf.html",
        {"receipt": receipt, "business": receipt.business},
    )
    pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()
    response = HttpResponse(pdf, content_type="application/pdf")
    if download:
        response["Content-Disposition"] = f'attachment; filename="recibo-{receipt.receipt_number}.pdf"'
    return response


@login_required
@business_required
@permission_required("billing.view_invoice", raise_exception=True)
def invoice_pdf_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, business=request.business)
    return _render_invoice_pdf(invoice, request, download=False)


@login_required
@business_required
@permission_required("billing.view_invoice", raise_exception=True)
def invoice_pdf_download(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, business=request.business)
    return _render_invoice_pdf(invoice, request, download=True)


@login_required
@business_required
@permission_required("billing.view_receipt", raise_exception=True)
def receipt_pdf_view(request, pk):
    receipt = get_object_or_404(Receipt, pk=pk, business=request.business)
    return _render_receipt_pdf(receipt, request, download=False)


@login_required
@business_required
@permission_required("billing.view_receipt", raise_exception=True)
def receipt_pdf_download(request, pk):
    receipt = get_object_or_404(Receipt, pk=pk, business=request.business)
    return _render_receipt_pdf(receipt, request, download=True)
