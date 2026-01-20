from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventory.models import StockMovement
from inventory.services import record_movement
from finance.models import CashMovement, Expense, FinancialAccount, PaymentMethod, Purchase
from tenants.services import generate_document_code


DEFAULT_ACCOUNT_NAMES = {
    FinancialAccount.CATEGORY_CASH: "Caixa Principal",
    FinancialAccount.CATEGORY_BANK: "Banco Principal",
    FinancialAccount.CATEGORY_MOBILE: "Carteira Principal",
}

DEFAULT_METHOD_CATEGORY = {
    CashMovement.METHOD_CASH: FinancialAccount.CATEGORY_CASH,
    CashMovement.METHOD_CARD: FinancialAccount.CATEGORY_BANK,
    CashMovement.METHOD_TRANSFER: FinancialAccount.CATEGORY_BANK,
    CashMovement.METHOD_CHEQUE: FinancialAccount.CATEGORY_BANK,
    CashMovement.METHOD_MPESA: FinancialAccount.CATEGORY_MOBILE,
    CashMovement.METHOD_EMOLA: FinancialAccount.CATEGORY_MOBILE,
    CashMovement.METHOD_MKESH: FinancialAccount.CATEGORY_MOBILE,
    CashMovement.METHOD_OTHER: FinancialAccount.CATEGORY_CASH,
}


def ensure_default_payment_methods(business):
    account_defaults = {
        FinancialAccount.CATEGORY_CASH: "Caixa Principal",
        FinancialAccount.CATEGORY_BANK: "Banco Principal",
        FinancialAccount.CATEGORY_MOBILE: "Carteira Principal",
    }
    accounts = {}
    for category, name in account_defaults.items():
        account, _ = FinancialAccount.objects.get_or_create(
            business=business,
            name=name,
            defaults={"category": category},
        )
        if account.category != category:
            account.category = category
            account.save(update_fields=["category"])
        accounts[category] = account

    methods = [
        ("cash", "Numerario", FinancialAccount.CATEGORY_CASH),
        ("card", "Cartao", FinancialAccount.CATEGORY_BANK),
        ("bank_transfer", "Transferencia", FinancialAccount.CATEGORY_BANK),
        ("cheque", "Cheque", FinancialAccount.CATEGORY_BANK),
        ("mpesa", "MPesa", FinancialAccount.CATEGORY_MOBILE),
        ("emola", "Emola", FinancialAccount.CATEGORY_MOBILE),
        ("mkesh", "MKesh", FinancialAccount.CATEGORY_MOBILE),
        ("other", "Outro", FinancialAccount.CATEGORY_CASH),
    ]
    for code, name, category in methods:
        PaymentMethod.objects.get_or_create(
            business=business,
            code=code,
            defaults={
                "name": name,
                "category": category,
                "account": accounts.get(category),
            },
        )


def _resolve_payment_method(business, method_code):
    if not method_code:
        return None, None, None
    payment_method = PaymentMethod.objects.filter(
        business=business, code=method_code, is_active=True
    ).select_related("account").first()
    if payment_method:
        return payment_method, payment_method.category, payment_method.account
    category = DEFAULT_METHOD_CATEGORY.get(method_code, FinancialAccount.CATEGORY_CASH)
    account, _ = FinancialAccount.objects.get_or_create(
        business=business,
        name=DEFAULT_ACCOUNT_NAMES.get(category, "Conta Principal"),
        defaults={"category": category},
    )
    return None, category, account


def _create_cash_out(*, business, amount, method, reference_type, reference_id, user, notes=""):
    if amount <= 0:
        return None
    if not method:
        raise ValidationError("Selecione o metodo de pagamento.")
    payment_method, category, account = _resolve_payment_method(business, method)
    return CashMovement.objects.create(
        business=business,
        payment_method=payment_method,
        category=category or "",
        account=account,
        movement_type=CashMovement.MOVEMENT_OUT,
        amount=amount,
        method=method,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
        happened_at=timezone.now(),
        created_by=user,
    )


def _create_cash_in(*, business, amount, method, reference_type, reference_id, user, notes=""):
    if amount <= 0:
        return None
    payment_method, category, account = _resolve_payment_method(business, method)
    return CashMovement.objects.create(
        business=business,
        payment_method=payment_method,
        category=category or "",
        account=account,
        movement_type=CashMovement.MOVEMENT_IN,
        amount=amount,
        method=method,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
        happened_at=timezone.now(),
        created_by=user,
    )


def confirm_purchase(*, purchase_id, business, user):
    with transaction.atomic():
        purchase = (
            Purchase.objects.select_for_update()
            .select_related("business")
            .get(id=purchase_id, business=business)
        )
        if purchase.status != Purchase.STATUS_DRAFT:
            raise ValidationError("A compra nao esta em rascunho.")
        if purchase.purchase_type == Purchase.TYPE_STOCK:
            items = purchase.items.select_related("product")
            if not items.exists():
                raise ValidationError("Adicione pelo menos um produto.")
            subtotal = Decimal("0")
            for item in items:
                subtotal += item.line_total
            purchase.subtotal = subtotal
            purchase.total = subtotal
        else:
            if purchase.internal_amount <= 0:
                raise ValidationError("Informe o valor da compra interna.")
            purchase.subtotal = purchase.internal_amount
            purchase.total = purchase.internal_amount

        purchase.status = Purchase.STATUS_CONFIRMED
        purchase.updated_by = user
        if not purchase.code:
            purchase.code = generate_document_code(
                business=purchase.business,
                doc_type="purchase",
                prefix="C",
                date=purchase.purchase_date,
            )
        purchase.save(update_fields=["status", "subtotal", "total", "updated_by", "code"])

        if purchase.purchase_type == Purchase.TYPE_STOCK:
            for item in purchase.items.select_related("product"):
                record_movement(
                    business=purchase.business,
                    product=item.product,
                    movement_type=StockMovement.MOVEMENT_IN,
                    quantity=item.quantity,
                    created_by=user,
                    reference_type="purchase",
                    reference_id=purchase.id,
                )
            purchase.stock_received = True
            purchase.save(update_fields=["stock_received"])

        _create_cash_out(
            business=purchase.business,
            amount=purchase.total,
            method=purchase.payment_method,
            reference_type="purchase",
            reference_id=purchase.id,
            user=user,
        )
        return purchase


def cancel_purchase(*, purchase_id, business, user, notes=""):
    with transaction.atomic():
        purchase = (
            Purchase.objects.select_for_update()
            .select_related("business")
            .get(id=purchase_id, business=business)
        )
        if purchase.status != Purchase.STATUS_CONFIRMED:
            raise ValidationError("A compra nao esta confirmada.")
        if purchase.purchase_type == Purchase.TYPE_STOCK:
            for item in purchase.items.select_related("product"):
                record_movement(
                    business=purchase.business,
                    product=item.product,
                    movement_type=StockMovement.MOVEMENT_OUT,
                    quantity=item.quantity,
                    created_by=user,
                    reference_type="purchase_cancel",
                    reference_id=purchase.id,
                    notes=notes,
                )
            if purchase.stock_received:
                purchase.stock_received = False
        _create_cash_in(
            business=purchase.business,
            amount=purchase.total,
            method=purchase.payment_method,
            reference_type="purchase_cancel",
            reference_id=purchase.id,
            user=user,
            notes=notes,
        )
        purchase.status = Purchase.STATUS_CANCELED
        purchase.updated_by = user
        update_fields = ["status", "updated_by"]
        if purchase.purchase_type == Purchase.TYPE_STOCK:
            update_fields.append("stock_received")
        purchase.save(update_fields=update_fields)
        return purchase


def pay_expense(*, expense_id, business, user):
    with transaction.atomic():
        expense = (
            Expense.objects.select_for_update()
            .select_related("business")
            .get(id=expense_id, business=business)
        )
        if expense.status != Expense.STATUS_DRAFT:
            raise ValidationError("A despesa nao esta em rascunho.")
        if expense.amount <= 0:
            raise ValidationError("Informe o valor da despesa.")
        if not expense.payment_method:
            raise ValidationError("Selecione o metodo de pagamento.")
        expense.status = Expense.STATUS_PAID
        expense.updated_by = user
        expense.save(update_fields=["status", "updated_by"])
        _create_cash_out(
            business=expense.business,
            amount=expense.amount,
            method=expense.payment_method,
            reference_type="expense",
            reference_id=expense.id,
            user=user,
        )
        return expense


def cancel_expense(*, expense_id, business, user, notes=""):
    with transaction.atomic():
        expense = (
            Expense.objects.select_for_update()
            .select_related("business")
            .get(id=expense_id, business=business)
        )
        if expense.status != Expense.STATUS_PAID:
            raise ValidationError("A despesa nao esta paga.")
        _create_cash_in(
            business=expense.business,
            amount=expense.amount,
            method=expense.payment_method,
            reference_type="expense_cancel",
            reference_id=expense.id,
            user=user,
            notes=notes,
        )
        expense.status = Expense.STATUS_CANCELED
        expense.updated_by = user
        expense.save(update_fields=["status", "updated_by"])
        return expense
