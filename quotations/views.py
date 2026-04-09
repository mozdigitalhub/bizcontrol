import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from catalog.models import Product
from quotations.forms import QuotationForm, QuotationItemFormSet
from quotations.models import Quotation
from quotations.services import (
    add_status_history,
    approve_quotation,
    cancel_quotation,
    get_quotation_stock_shortages,
    mark_quotation_sent,
    recalculate_quotation_totals,
    reject_quotation,
    update_quotation_items,
)
from bizcontrol.emailing import (
    build_pdf_attachment,
    get_tenant_sender_email,
    send_transactional_email,
)
from bizcontrol.pdf_utils import build_logo_src
from tenants.forms import EmailSendForm
from tenants.decorators import business_required, module_required, owner_required
from tenants.models import Business

try:
    from weasyprint import HTML
except Exception:  # pragma: no cover - optional dependency
    HTML = None


def _quotation_error_summary(form, formset):
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


def _extract_items(formset):
    items = []
    for item_form in formset.forms:
        if not item_form.cleaned_data or item_form.cleaned_data.get("DELETE"):
            continue
        product = item_form.cleaned_data.get("product")
        description = (item_form.cleaned_data.get("description") or "").strip()
        quantity = item_form.cleaned_data.get("quantity")
        unit_price = item_form.cleaned_data.get("unit_price")
        if not product and not description and not quantity and not unit_price:
            continue
        items.append(
            {
                "product": product,
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
            }
        )
    return items


@login_required
@business_required
@module_required(Business.MODULE_QUOTATIONS, message="Modulo de cotacoes desativado.")
@permission_required("quotations.view_quotation", raise_exception=True)
def quotation_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    customer_id = request.GET.get("customer", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if not date_from and not date_to:
        today = timezone.localdate()
        date_from = (today - timedelta(days=6)).isoformat()
        date_to = today.isoformat()
    quotations = Quotation.objects.filter(business=request.business).select_related("customer")
    if query:
        quotations = quotations.filter(
            Q(code__icontains=query) | Q(customer__name__icontains=query)
        )
    if status:
        quotations = quotations.filter(status=status)
    if customer_id:
        quotations = quotations.filter(customer_id=customer_id)
    if date_from:
        quotations = quotations.filter(issue_date__gte=date_from)
    if date_to:
        quotations = quotations.filter(issue_date__lte=date_to)
    totals = quotations.aggregate(total=Sum("total"))
    total_amount = totals["total"] or 0
    approved_count = quotations.filter(status=Quotation.STATUS_APPROVED).count()
    open_count = quotations.filter(
        status__in=[Quotation.STATUS_DRAFT, Quotation.STATUS_SENT]
    ).count()
    paginator = Paginator(quotations.order_by("-issue_date", "-created_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    today = timezone.localdate()
    for quotation in page.object_list:
        quotation.mark_expired_if_needed(today=today)
    return render(
        request,
        "quotations/quotation_list.html",
        {
            "page": page,
            "query": query,
            "status": status,
            "customer_id": customer_id,
            "date_from": date_from,
            "date_to": date_to,
            "status_choices": Quotation.STATUS_CHOICES,
            "customers": request.business.customers.order_by("name"),
            "editable_statuses": [Quotation.STATUS_DRAFT, Quotation.STATUS_SENT],
            "total_amount": total_amount,
            "approved_count": approved_count,
            "open_count": open_count,
        },
    )


@login_required
@business_required
@module_required(Business.MODULE_QUOTATIONS, message="Modulo de cotacoes desativado.")
@permission_required("quotations.add_quotation", raise_exception=True)
def quotation_create(request):
    return _quotation_form(request)


@login_required
@business_required
@module_required(Business.MODULE_QUOTATIONS, message="Modulo de cotacoes desativado.")
@permission_required("quotations.change_quotation", raise_exception=True)
def quotation_edit(request, pk):
    return _quotation_form(request, pk=pk)


def _quotation_form(request, pk=None):
    quotation = None
    if pk:
        quotation = get_object_or_404(Quotation, pk=pk, business=request.business)
        if quotation.status not in {Quotation.STATUS_DRAFT, Quotation.STATUS_SENT}:
            messages.error(request, "Esta cotacao nao pode ser editada.")
            return redirect("quotations:detail", pk=quotation.id)

    if request.method == "POST":
        form = QuotationForm(request.POST, instance=quotation)
        form.fields["customer"].queryset = request.business.customers.order_by("name")
        formset = QuotationItemFormSet(request.POST, prefix="items")
        for item_form in formset:
            if "product" in item_form.fields:
                item_form.fields["product"].queryset = Product.objects.filter(
                    business=request.business
                )
        form_valid = form.is_valid()
        formset_valid = formset.is_valid()
        if not (form_valid and formset_valid):
            messages.error(request, "Revise os campos obrigatorios antes de confirmar.")
            error_summary = _quotation_error_summary(form, formset)
            return render(
                request,
                "quotations/quotation_form.html",
                {
                    "form": form,
                    "formset": formset,
                    "quotation": quotation,
                    "error_summary": error_summary,
                    "products_json": _product_json(request),
                    "vat_rate": request.business.vat_rate,
                    "prices_include_vat": request.business.prices_include_vat,
                },
            )

        items_data = _extract_items(formset)
        if not items_data:
            form.add_error(None, "Adicione pelo menos um item.")
            error_summary = _quotation_error_summary(form, formset)
            return render(
                request,
                "quotations/quotation_form.html",
                {
                    "form": form,
                    "formset": formset,
                    "quotation": quotation,
                    "error_summary": error_summary,
                    "products_json": _product_json(request),
                    "vat_rate": request.business.vat_rate,
                    "prices_include_vat": request.business.prices_include_vat,
                },
            )

        quotation = form.save(commit=False)
        quotation.business = request.business
        if not quotation.pk or not quotation.currency:
            quotation.currency = request.business.currency
        if not quotation.pk:
            quotation.created_by = request.user
        quotation.updated_by = request.user
        quotation.save()

        try:
            update_quotation_items(quotation=quotation, items_data=items_data)
        except ValidationError as exc:
            form.add_error(None, str(exc))
            error_summary = _quotation_error_summary(form, formset)
            return render(
                request,
                "quotations/quotation_form.html",
                {
                    "form": form,
                    "formset": formset,
                    "quotation": quotation,
                    "error_summary": error_summary,
                    "products_json": _product_json(request),
                    "vat_rate": request.business.vat_rate,
                    "prices_include_vat": request.business.prices_include_vat,
                },
            )

        action = request.POST.get("action", "draft")
        if action == "send":
            try:
                mark_quotation_sent(quotation=quotation, user=request.user)
                messages.success(request, "Cotacao enviada.")
            except ValidationError as exc:
                messages.error(request, str(exc))
        else:
            if quotation.status == Quotation.STATUS_DRAFT:
                add_status_history(quotation=quotation, status=Quotation.STATUS_DRAFT, user=request.user)
            messages.success(request, "Cotacao guardada como rascunho.")
        return redirect("quotations:detail", pk=quotation.id)

    form = QuotationForm(instance=quotation)
    form.fields["customer"].queryset = request.business.customers.order_by("name")
    formset = QuotationItemFormSet(prefix="items")
    if quotation:
        items = quotation.items.all()
        initial = []
        for item in items:
            initial.append(
                {
                    "product": item.product,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                }
            )
        formset = QuotationItemFormSet(prefix="items", initial=initial)
    return render(
        request,
        "quotations/quotation_form.html",
        {
            "form": form,
            "formset": formset,
            "quotation": quotation,
            "products_json": _product_json(request),
            "vat_rate": request.business.vat_rate,
            "prices_include_vat": request.business.prices_include_vat,
        },
    )


@login_required
@business_required
@module_required(Business.MODULE_QUOTATIONS, message="Modulo de cotacoes desativado.")
@permission_required("quotations.view_quotation", raise_exception=True)
def quotation_detail(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk, business=request.business)
    quotation.mark_expired_if_needed()
    items = quotation.items.select_related("product")
    status_history = quotation.status_history.select_related("changed_by").order_by("-changed_at")
    return render(
        request,
        "quotations/quotation_detail.html",
        {
            "quotation": quotation,
            "items": items,
            "status_history": status_history,
            "editable_statuses": [Quotation.STATUS_DRAFT, Quotation.STATUS_SENT],
            "cancel_blocked_statuses": [Quotation.STATUS_APPROVED, Quotation.STATUS_CANCELED],
        },
    )


@login_required
@business_required
@module_required(Business.MODULE_QUOTATIONS, message="Modulo de cotacoes desativado.")
@owner_required
def quotation_approve(request, pk):
    if request.method != "POST":
        return redirect("quotations:detail", pk=pk)
    try:
        quotation = approve_quotation(
            quotation_id=pk,
            business=request.business,
            user=request.user,
            confirm_stock=request.POST.get("confirm_stock") == "1",
        )
        messages.success(request, "Cotacao aprovada e convertida em venda.")
        return redirect("sales:detail", pk=quotation.sale_id)
    except Exception as exc:
        messages.error(request, str(exc))
        return redirect("quotations:detail", pk=pk)


@login_required
@business_required
@module_required(Business.MODULE_QUOTATIONS, message="Modulo de cotacoes desativado.")
@owner_required
def quotation_reject(request, pk):
    if request.method != "POST":
        return redirect("quotations:detail", pk=pk)
    notes = request.POST.get("notes", "")
    try:
        reject_quotation(
            quotation=get_object_or_404(Quotation, pk=pk, business=request.business),
            user=request.user,
            notes=notes,
        )
        messages.success(request, "Cotacao rejeitada.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("quotations:detail", pk=pk)


@login_required
@business_required
@module_required(Business.MODULE_QUOTATIONS, message="Modulo de cotacoes desativado.")
@owner_required
def quotation_cancel(request, pk):
    if request.method != "POST":
        return redirect("quotations:detail", pk=pk)
    notes = request.POST.get("notes", "")
    try:
        cancel_quotation(
            quotation=get_object_or_404(Quotation, pk=pk, business=request.business),
            user=request.user,
            notes=notes,
        )
        messages.success(request, "Cotacao cancelada.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("quotations:detail", pk=pk)


@login_required
@business_required
@module_required(Business.MODULE_QUOTATIONS, message="Modulo de cotacoes desativado.")
@permission_required("quotations.add_quotation", raise_exception=True)
def quotation_duplicate(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk, business=request.business)
    new_quote = Quotation.objects.create(
        business=request.business,
        customer=quotation.customer,
        status=Quotation.STATUS_DRAFT,
        issue_date=timezone.localdate(),
        valid_until=quotation.valid_until,
        currency=quotation.currency or request.business.currency,
        notes=quotation.notes,
        terms=quotation.terms,
        discount_type=quotation.discount_type,
        discount_value=quotation.discount_value,
        created_by=request.user,
        updated_by=request.user,
    )
    for item in quotation.items.all():
        new_quote.items.create(
            product=item.product,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax_rate=item.tax_rate,
            line_subtotal=item.line_subtotal,
            line_tax=item.line_tax,
            line_total=item.line_total,
        )
    recalculate_quotation_totals(new_quote)
    add_status_history(quotation=new_quote, status=Quotation.STATUS_DRAFT, user=request.user)
    messages.success(request, "Cotacao duplicada.")
    return redirect("quotations:edit", pk=new_quote.id)


def _product_json(request):
    products = Product.objects.filter(business=request.business).order_by("name")
    data = {}
    for product in products:
        data[str(product.id)] = {
            "name": product.name,
            "price": str(product.sale_price),
        }
    return json.dumps(data)


def _build_quotation_pdf_bytes(quotation, request):
    if HTML is None:
        raise ValueError("WeasyPrint nao instalado.")
    logo_url = build_logo_src(quotation.business, request)
    html = render_to_string(
        "quotations/quotation_pdf.html",
        {
            "quotation": quotation,
            "business": quotation.business,
            "items": quotation.items.select_related("product"),
            "logo_url": logo_url,
        },
    )
    return HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()


def _render_quotation_pdf(quotation, request):
    try:
        pdf = _build_quotation_pdf_bytes(quotation, request)
    except ValueError as exc:
        return HttpResponse(str(exc), status=500)
    response = HttpResponse(pdf, content_type="application/pdf")
    return response


@login_required
@business_required
@module_required(Business.MODULE_QUOTATIONS, message="Modulo de cotacoes desativado.")
@permission_required("quotations.view_quotation", raise_exception=True)
def quotation_pdf_view(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk, business=request.business)
    return _render_quotation_pdf(quotation, request)


@login_required
@business_required
@module_required(Business.MODULE_QUOTATIONS, message="Modulo de cotacoes desativado.")
@permission_required("quotations.view_quotation", raise_exception=True)
def quotation_email_modal(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk, business=request.business)
    initial_email = quotation.customer.email if quotation.customer and quotation.customer.email else ""
    form = EmailSendForm(initial={"email": initial_email})
    success = False
    if request.method == "POST":
        form = EmailSendForm(request.POST)
        if form.is_valid():
            try:
                pdf_bytes = _build_quotation_pdf_bytes(quotation, request)
            except ValueError as exc:
                form.add_error(None, str(exc))
            else:
                attachment = build_pdf_attachment(
                    f"cotacao-{quotation.code or quotation.id}.pdf",
                    pdf_bytes,
                )
                subject = f"Cotacao {quotation.code or quotation.id} - {request.business.name}"
                html = render_to_string(
                    "emails/document_email.html",
                    {
                        "recipient_name": quotation.customer.name if quotation.customer else "Cliente",
                        "document_label": "a cotacao",
                        "document_code": quotation.code or quotation.id,
                        "business": request.business,
                        "message": form.cleaned_data.get("message", ""),
                    },
                )
                reply_to = request.business.contact_email or None
                ok, error = send_transactional_email(
                    to_email=form.cleaned_data["email"],
                    subject=subject,
                    html=html,
                    attachments=[attachment],
                    reply_to=reply_to,
                    from_email=get_tenant_sender_email(request.business.name),
                )
                if ok:
                    success = True
                    messages.success(request, "Email enviado com sucesso.")
                else:
                    form.add_error(None, error)
        else:
            messages.error(request, "Revise os campos antes de enviar.")
    return render(
        request,
        "quotations/partials/quotation_email_modal.html",
        {"quotation": quotation, "form": form, "success": success},
    )


@login_required
@business_required
@module_required(Business.MODULE_QUOTATIONS, message="Modulo de cotacoes desativado.")
@owner_required
def quotation_stock_check(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk, business=request.business)
    shortages = get_quotation_stock_shortages(quotation=quotation)
    return JsonResponse({"shortages": shortages})
