from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from billing.models import Invoice, InvoicePayment, Receipt, Sequence
from tenants.services import generate_document_code
from finance.services import _create_cash_in
from receivables.models import Payment, Receivable
from sales.models import Sale


def _next_sequence_value(*, business, name):
    seq = Sequence.objects.select_for_update().filter(business=business, name=name).first()
    if not seq:
        seq = Sequence.objects.create(business=business, name=name, current_value=0)
    seq.current_value += 1
    seq.save(update_fields=["current_value"])
    return seq.current_value


def generate_invoice(*, sale_id, business, user):
    with transaction.atomic():
        sale = (
            Sale.objects.select_for_update()
            .select_related("business")
            .get(id=sale_id, business=business)
        )
        if sale.status != Sale.STATUS_CONFIRMED:
            raise ValidationError("A venda precisa estar confirmada.")
        if sale.invoices.exists():
            raise ValidationError("Esta venda ja tem fatura.")

        invoice_number = _next_sequence_value(business=business, name="invoice")
        issue_date = timezone.localdate()
        if sale.entry_mode == Sale.ENTRY_MODE_CONTINGENCY and sale.sale_date:
            issue_date = timezone.localtime(sale.sale_date).date()
        due_date = sale.payment_due_date if sale.is_credit else None
        code = generate_document_code(
            business=business,
            doc_type="invoice",
            prefix="F",
            date=issue_date,
        )
        payment_snapshot = business.get_payment_snapshot()
        invoice = Invoice.objects.create(
            business=business,
            customer=sale.customer,
            sale=sale,
            code=code,
            invoice_number=invoice_number,
            issue_date=issue_date,
            due_date=due_date,
            status=Invoice.STATUS_ISSUED,
            subtotal=sale.subtotal,
            tax_total=sale.tax_total,
            total=sale.total,
            payment_snapshot=payment_snapshot,
            created_by=user,
        )
    return invoice


def generate_receipt(*, business, user, payment=None, invoice_payment=None):
    with transaction.atomic():
        receipt_number = _next_sequence_value(business=business, name="receipt")
        if not payment and not invoice_payment:
            raise ValidationError("Pagamento invalido para recibo.")
        invoice = None
        amount = Decimal("0")
        if invoice_payment:
            invoice = invoice_payment.invoice
            amount = invoice_payment.amount
        if payment:
            amount = payment.amount
            if payment.receivable and payment.receivable.sale:
                invoice = payment.receivable.sale.invoices.first()
        issue_date = timezone.now().date()
        code = generate_document_code(
            business=business,
            doc_type="receipt",
            prefix="R",
            date=issue_date,
        )
        receipt = Receipt.objects.create(
            business=business,
            invoice=invoice,
            payment=payment,
            invoice_payment=invoice_payment,
            code=code,
            receipt_number=receipt_number,
            issue_date=issue_date,
            amount=amount,
            created_by=user,
        )
    return receipt


def _sync_invoice_and_sale(invoice):
    if invoice.status == Invoice.STATUS_CANCELED:
        return
    if hasattr(invoice, "_amount_paid_cache"):
        delattr(invoice, "_amount_paid_cache")
    amount_paid = invoice.amount_paid
    balance = invoice.total - amount_paid
    if balance <= 0:
        new_status = Invoice.STATUS_PAID
    elif amount_paid > 0:
        new_status = Invoice.STATUS_PARTIAL
    else:
        new_status = Invoice.STATUS_ISSUED
    if invoice.status != new_status:
        invoice.status = new_status
        invoice.save(update_fields=["status"])
    if invoice.sale:
        sale_status = {
            Invoice.STATUS_PAID: Sale.PAYMENT_PAID,
            Invoice.STATUS_PARTIAL: Sale.PAYMENT_PARTIAL,
            Invoice.STATUS_ISSUED: Sale.PAYMENT_UNPAID,
        }.get(new_status, Sale.PAYMENT_UNPAID)
        if invoice.sale.payment_status != sale_status:
            invoice.sale.payment_status = sale_status
            invoice.sale.save(update_fields=["payment_status"])


def _resolve_payment_timestamp(*, paid_at, allow_backdated, reference_date=None):
    now = timezone.now()
    if paid_at is None:
        return now
    if not allow_backdated:
        raise ValidationError(
            "Data de pagamento retroativa so esta disponivel para vendas em contingencia."
        )
    if timezone.is_naive(paid_at):
        paid_at = timezone.make_aware(paid_at, timezone.get_current_timezone())
    if paid_at > now:
        raise ValidationError("A data do pagamento nao pode ser futura.")
    max_days = int(getattr(settings, "BACKDATED_SALE_MAX_DAYS", 30))
    min_date = timezone.localdate() - timedelta(days=max_days)
    if paid_at.date() < min_date:
        raise ValidationError(
            f"Data de pagamento retroativa limitada a {max_days} dias."
        )
    if reference_date and paid_at.date() < timezone.localtime(reference_date).date():
        raise ValidationError(
            "A data do pagamento nao pode ser anterior a data da venda."
        )
    return paid_at


def register_invoice_payment(
    *, invoice_id, business, amount, method, user, notes="", paid_at=None
):
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError("O valor do pagamento deve ser maior que zero.")
    if not method:
        raise ValidationError("Selecione o metodo de pagamento.")
    with transaction.atomic():
        invoice = (
            Invoice.objects.select_for_update()
            .get(id=invoice_id, business=business)
        )
        if invoice.status == Invoice.STATUS_CANCELED:
            raise ValidationError("A fatura esta cancelada.")
        if amount > invoice.balance:
            raise ValidationError("O valor excede o saldo em aberto.")
        sale = None
        if invoice.sale_id:
            sale = Sale.objects.filter(
                id=invoice.sale_id,
                business=business,
            ).first()
        allow_backdated = bool(
            sale and sale.entry_mode == Sale.ENTRY_MODE_CONTINGENCY
        )
        resolved_paid_at = _resolve_payment_timestamp(
            paid_at=paid_at,
            allow_backdated=allow_backdated,
            reference_date=sale.sale_date if sale else None,
        )
        invoice_payment = InvoicePayment.objects.create(
            business=business,
            invoice=invoice,
            amount=amount,
            method=method,
            paid_at=resolved_paid_at,
            notes=notes,
            created_by=user,
        )
        receivable_payment = None
        receivable = None
        if invoice.sale_id:
            receivable = Receivable.objects.filter(
                business=business, sale_id=invoice.sale_id
            ).first()
        if receivable:
            mapped_method = method
            if mapped_method not in dict(Payment.METHOD_CHOICES):
                mapped_method = Payment.METHOD_OTHER
            receivable_payment = Payment.objects.create(
                business=business,
                receivable=receivable,
                amount=amount,
                method=mapped_method,
                paid_at=resolved_paid_at,
                notes=notes,
                created_by=user,
            )
            invoice_payment.receivable_payment = receivable_payment
            invoice_payment.save(update_fields=["receivable_payment"])
            receivable.total_paid += amount
            receivable.status = (
                Receivable.STATUS_SETTLED
                if receivable.balance <= 0
                else Receivable.STATUS_OPEN
            )
            receivable.save(update_fields=["total_paid", "status"])
        _create_cash_in(
            business=business,
            amount=amount,
            method=method,
            reference_type="invoice_payment",
            reference_id=invoice_payment.id,
            user=user,
            notes=f"Pagamento fatura {invoice.invoice_number}",
            happened_at=resolved_paid_at,
        )
        invoice.refresh_from_db()
        _sync_invoice_and_sale(invoice)
        generate_receipt(
            business=business,
            user=user,
            payment=receivable_payment,
            invoice_payment=invoice_payment,
        )
        return invoice_payment
