from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from billing.services import generate_receipt, _sync_invoice_and_sale
from finance.services import _create_cash_in
from receivables.models import Payment, Receivable
from sales.models import Sale


def register_payment(*, receivable_id, business, amount, method, user, notes=""):
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError("O valor do pagamento deve ser maior que zero.")

    with transaction.atomic():
        receivable = (
            Receivable.objects.select_for_update()
            .get(id=receivable_id, business=business)
        )
        if amount > receivable.balance:
            raise ValidationError("O valor excede o saldo em aberto.")

        payment = Payment.objects.create(
            business=business,
            receivable=receivable,
            amount=amount,
            method=method,
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
            notes=f"Pagamento de crédito #{receivable.id}",
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
