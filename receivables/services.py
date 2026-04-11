from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from billing.services import _sync_invoice_and_sale, generate_receipt
from finance.services import _create_cash_in
from receivables.models import Payment, Receivable
from sales.models import Sale


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


def register_payment(*, receivable_id, business, amount, method, user, notes="", paid_at=None):
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError("O valor do pagamento deve ser maior que zero.")

    with transaction.atomic():
        receivable = Receivable.objects.select_for_update().get(
            id=receivable_id, business=business
        )
        if amount > receivable.balance:
            raise ValidationError("O valor excede o saldo em aberto.")
        sale = None
        if receivable.sale_id:
            sale = Sale.objects.filter(
                id=receivable.sale_id,
                business=business,
            ).first()
        allow_backdated = bool(sale and sale.entry_mode == Sale.ENTRY_MODE_CONTINGENCY)
        resolved_paid_at = _resolve_payment_timestamp(
            paid_at=paid_at,
            allow_backdated=allow_backdated,
            reference_date=sale.sale_date if sale else None,
        )

        payment = Payment.objects.create(
            business=business,
            receivable=receivable,
            amount=amount,
            method=method,
            paid_at=resolved_paid_at,
            notes=notes,
            created_by=user,
        )

        _create_cash_in(
            business=business,
            amount=amount,
            method=method,
            reference_type="receivable_payment",
            reference_id=payment.id,
            user=user,
            notes=f"Pagamento de credito #{receivable.id}",
            happened_at=resolved_paid_at,
        )

        receivable.total_paid += amount
        receivable.status = (
            Receivable.STATUS_SETTLED
            if receivable.balance <= 0
            else Receivable.STATUS_OPEN
        )
        receivable.save(update_fields=["total_paid", "status"])

        if receivable.sale:
            sale = receivable.sale
            if sale.invoices.exists():
                _sync_invoice_and_sale(sale.invoices.first())
            else:
                sale.payment_status = (
                    Sale.PAYMENT_PAID
                    if receivable.balance <= 0
                    else Sale.PAYMENT_PARTIAL
                )
                sale.save(update_fields=["payment_status"])

        generate_receipt(
            business=business,
            payment=payment,
            user=user,
        )
    return payment
