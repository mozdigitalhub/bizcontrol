from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

from inventory.models import StockMovement
from inventory.services import record_movement
from billing.models import Invoice
from receivables.models import Receivable
from receivables.services import register_payment
from sales.models import ContingencyBatch, Sale, SaleItem, SaleRefund
from deliveries.models import DeliveryGuideItem
from tenants.services import generate_document_code


def calculate_line_totals(*, business, unit_price, quantity):
    rate = business.vat_rate if business.vat_enabled else Decimal("0")
    unit_price = Decimal(unit_price)
    quantity = Decimal(quantity)
    if rate and business.prices_include_vat:
        base = unit_price / (Decimal("1") + rate)
        tax = unit_price - base
    elif rate:
        base = unit_price
        tax = unit_price * rate
    else:
        base = unit_price
        tax = Decimal("0")
    line_subtotal = base * quantity
    line_tax = tax * quantity
    line_total = (base + tax) * quantity
    return line_subtotal, line_tax, line_total


def recalculate_sale_totals(sale):
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for item in sale.items.all():
        subtotal += item.line_subtotal
        tax_total += item.line_tax
    total_before_discount = subtotal + tax_total
    discount_total = Decimal("0")
    discount_value = sale.discount_value or Decimal("0")
    if sale.discount_type == Sale.DISCOUNT_PERCENT:
        discount_total = (total_before_discount * discount_value) / Decimal("100")
    elif sale.discount_type == Sale.DISCOUNT_FIXED:
        discount_total = discount_value
    if discount_total < 0:
        discount_total = Decimal("0")
    if discount_total > total_before_discount:
        discount_total = total_before_discount
    total = total_before_discount - discount_total
    sale.subtotal = subtotal
    sale.tax_total = tax_total
    sale.discount_total = discount_total
    sale.total = total
    sale.save(update_fields=["subtotal", "tax_total", "discount_total", "total"])
    return sale


def _draft_session_key(sale_id):
    return f"sale_draft_items_{sale_id}"


def get_draft_items(request, sale_id):
    return request.session.get(_draft_session_key(sale_id), [])


def set_draft_items(request, sale_id, items):
    request.session[_draft_session_key(sale_id)] = items
    request.session.modified = True


def clear_draft_items(request, sale_id):
    key = _draft_session_key(sale_id)
    if key in request.session:
        del request.session[key]
        request.session.modified = True


def _decimal_to_str(value, places):
    quant = Decimal(places)
    return str(value.quantize(quant))


def build_draft_item(*, business, product, quantity):
    line_subtotal, line_tax, line_total = calculate_line_totals(
        business=business,
        unit_price=product.sale_price,
        quantity=quantity,
    )
    return {
        "product_id": product.id,
        "name": product.name,
        "quantity": _decimal_to_str(Decimal(quantity), "1"),
        "unit_price": _decimal_to_str(Decimal(product.sale_price), "0.01"),
        "line_subtotal": _decimal_to_str(line_subtotal, "0.01"),
        "line_tax": _decimal_to_str(line_tax, "0.01"),
        "line_total": _decimal_to_str(line_total, "0.01"),
    }


def build_draft_item_from_sale_item(item):
    return {
        "product_id": item.product_id,
        "name": item.product.name,
        "quantity": _decimal_to_str(Decimal(item.quantity), "1"),
        "unit_price": _decimal_to_str(Decimal(item.unit_price), "0.01"),
        "line_subtotal": _decimal_to_str(Decimal(item.line_subtotal), "0.01"),
        "line_tax": _decimal_to_str(Decimal(item.line_tax), "0.01"),
        "line_total": _decimal_to_str(Decimal(item.line_total), "0.01"),
    }


def add_draft_item(*, business, items, product, quantity):
    quantity = Decimal(quantity)
    for item in items:
        if item["product_id"] == product.id:
            new_quantity = Decimal(item["quantity"]) + quantity
            updated = build_draft_item(
                business=business,
                product=product,
                quantity=new_quantity,
            )
            item.update(updated)
            return items
    items.append(
        build_draft_item(
            business=business,
            product=product,
            quantity=quantity,
        )
    )
    return items


def remove_draft_item(*, items, product_id):
    return [item for item in items if item["product_id"] != product_id]


def calculate_draft_totals(*, business, items, discount_type, discount_value):
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for item in items:
        subtotal += Decimal(item["line_subtotal"])
        tax_total += Decimal(item["line_tax"])
    total_before_discount = subtotal + tax_total
    discount_total = Decimal("0")
    discount_value = Decimal(discount_value or 0)
    if discount_type == Sale.DISCOUNT_PERCENT:
        discount_total = (total_before_discount * discount_value) / Decimal("100")
    elif discount_type == Sale.DISCOUNT_FIXED:
        discount_total = discount_value
    if discount_total < 0:
        discount_total = Decimal("0")
    if discount_total > total_before_discount:
        discount_total = total_before_discount
    total = total_before_discount - discount_total
    return {
        "subtotal": subtotal,
        "tax_total": tax_total,
        "discount_total": discount_total,
        "total": total,
    }


def calculate_down_payment_total(*, sale_total, down_payment_type, down_payment_value):
    down_payment_value = Decimal(down_payment_value or 0)
    if down_payment_type == Sale.DOWNPAY_PERCENT:
        amount = (sale_total * down_payment_value) / Decimal("100")
    elif down_payment_type == Sale.DOWNPAY_FIXED:
        amount = down_payment_value
    else:
        amount = Decimal("0")
    if amount < 0:
        amount = Decimal("0")
    if amount > sale_total:
        amount = sale_total
    return amount


def add_item_to_sale(*, sale, product, quantity, unit_price, user=None):
    line_subtotal, line_tax, line_total = calculate_line_totals(
        business=sale.business,
        unit_price=unit_price,
        quantity=quantity,
    )
    item = SaleItem.objects.create(
        sale=sale,
        product=product,
        quantity=int(quantity),
        unit_price=unit_price,
        line_subtotal=line_subtotal,
        line_tax=line_tax,
        line_total=line_total,
    )
    recalculate_sale_totals(sale)
    return item


def _open_receivable_total(*, business, customer, exclude_sale_id=None):
    queryset = Receivable.objects.filter(
        business=business,
        customer=customer,
        status=Receivable.STATUS_OPEN,
    )
    if exclude_sale_id:
        queryset = queryset.exclude(sale_id=exclude_sale_id)
    total = (
        queryset.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("original_amount") - F("total_paid"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
        ).get("total")
        or Decimal("0")
    )
    return total


def _ensure_contingency_batch(*, sale, user):
    operation_date = timezone.localtime(sale.sale_date).date()
    existing = (
        ContingencyBatch.objects.filter(
            business=sale.business,
            status=ContingencyBatch.STATUS_OPEN,
            date_from__lte=operation_date,
            date_to__gte=operation_date,
        )
        .order_by("-created_at")
        .first()
    )
    if existing:
        return existing
    base = operation_date.strftime("%Y%m%d")
    seq = (
        ContingencyBatch.objects.filter(
            business=sale.business,
            code__startswith=f"CTG-{base}-",
        ).count()
        + 1
    )
    code = f"CTG-{base}-{seq:02d}"
    return ContingencyBatch.objects.create(
        business=sale.business,
        code=code,
        date_from=operation_date,
        date_to=operation_date,
        notes="Lote criado automaticamente a partir de venda retroativa.",
        opened_by=user,
    )


def confirm_sale(*, sale_id, business, user, items_data=None, confirm_open_debt=False):
    with transaction.atomic():
        sale = (
            Sale.objects.select_for_update()
            .select_related("business")
            .get(id=sale_id, business=business)
        )
        if sale.status != Sale.STATUS_DRAFT:
            raise ValidationError("A venda nao esta em rascunho.")
        if items_data and not sale.items.exists():
            for item in items_data:
                SaleItem.objects.create(
                    sale=sale,
                    product_id=item["product_id"],
                    quantity=int(Decimal(item["quantity"])),
                    unit_price=Decimal(item["unit_price"]),
                    line_subtotal=Decimal(item["line_subtotal"]),
                    line_tax=Decimal(item["line_tax"]),
                    line_total=Decimal(item["line_total"]),
                )
        items = sale.items.select_related("product")
        if not items.exists():
            raise ValidationError("Adicione pelo menos um item.")

        operation_date = timezone.localtime(sale.sale_date).date()
        today = timezone.localdate()
        if operation_date < today and sale.entry_mode != Sale.ENTRY_MODE_CONTINGENCY:
            raise ValidationError(
                "Venda retroativa deve ser marcada como registo de contingencia."
            )
        if sale.entry_mode == Sale.ENTRY_MODE_CONTINGENCY:
            if not (sale.contingency_reason or "").strip():
                raise ValidationError(
                    "Indique o motivo da contingencia para confirmar a venda."
                )
            if not sale.contingency_batch_id:
                sale.contingency_batch = _ensure_contingency_batch(sale=sale, user=user)
                sale.save(update_fields=["contingency_batch"])
        elif sale.contingency_batch_id or sale.contingency_reason:
            sale.contingency_batch = None
            sale.contingency_reason = ""
            sale.save(update_fields=["contingency_batch", "contingency_reason"])

        if sale.is_credit and not business.feature_enabled("allow_credit_sales"):
            raise ValidationError("Crédito não está disponível para este negócio.")

        if sale.is_credit and not sale.customer:
            raise ValidationError("Selecione um cliente para crédito.")

        if sale.sale_type == Sale.SALE_TYPE_DEPOSIT and sale.is_credit:
            raise ValidationError("Depósito não pode ser a crédito.")

        recalculate_sale_totals(sale)

        if sale.is_credit and sale.customer:
            open_total = _open_receivable_total(
                business=business,
                customer=sale.customer,
                exclude_sale_id=sale.id,
            )
            if open_total > 0 and not confirm_open_debt:
                raise ValidationError(
                    f"Cliente com crédito em aberto: {open_total:.2f} MZN."
                )
            credit_limit = sale.customer.credit_limit or Decimal("0")
            if credit_limit > 0 and (open_total + sale.total) > credit_limit:
                raise ValidationError(
                    "Limite de credito excedido para este cliente."
                )

        if sale.is_credit and not sale.payment_due_date:
            raise ValidationError("Indique a data prevista de pagamento.")

        if (
            sale.sale_type != Sale.SALE_TYPE_DEPOSIT
            and not sale.is_credit
            and not sale.payment_method
        ):
            raise ValidationError("Selecione o metodo de pagamento.")
        sale.down_payment_total = Decimal("0")
        if sale.sale_type == Sale.SALE_TYPE_DEPOSIT:
            sale.delivery_mode = Sale.DELIVERY_SCHEDULED
        update_fields = ["down_payment_total"]
        if sale.sale_type == Sale.SALE_TYPE_DEPOSIT:
            update_fields.append("delivery_mode")
        if not sale.code:
            sale.code = generate_document_code(
                business=sale.business,
                doc_type="sale",
                prefix="V",
                date=sale.sale_date.date(),
            )
            update_fields.append("code")
        sale.save(update_fields=update_fields)

        sale.status = Sale.STATUS_CONFIRMED
        sale.payment_status = Sale.PAYMENT_UNPAID
        sale.updated_by = user
        if sale.delivery_status != Sale.DELIVERY_STATUS_DELIVERED:
            sale.delivery_status = Sale.DELIVERY_STATUS_PENDING
            sale.save(update_fields=["status", "payment_status", "updated_by", "delivery_status"])
        else:
            sale.save(update_fields=["status", "payment_status", "updated_by"])

        for item in items:
            if item.product.stock_control_mode == item.product.STOCK_AUTOMATIC:
                record_movement(
                    business=sale.business,
                    product=item.product,
                    movement_type=StockMovement.MOVEMENT_RESERVE,
                    quantity=item.quantity,
                    created_by=user,
                    reference_type="sale_reserve",
                    reference_id=sale.id,
                    notes=f"Reserva {sale.code or sale.id}",
                )

        if sale.is_credit:
            receivable = Receivable.objects.create(
                business=sale.business,
                customer=sale.customer,
                sale=sale,
                original_amount=sale.total,
                total_paid=Decimal("0"),
                status=Receivable.STATUS_OPEN,
            )
    return sale


def cancel_sale(*, sale_id, business, user, return_type, return_items=None, notes=""):
    with transaction.atomic():
        sale = (
            Sale.objects.select_for_update()
            .select_related("business")
            .get(id=sale_id, business=business)
        )
        if sale.status != Sale.STATUS_CONFIRMED:
            raise ValidationError("A venda nao esta confirmada.")
        delivered_map = {
            row["sale_item_id"]: row["total"] or 0
            for row in (
                DeliveryGuideItem.objects.filter(
                    guide__sale=sale,
                    guide__status__in=["issued", "partial", "delivered"],
                )
                .values("sale_item_id")
                .annotate(total=Sum("quantity"))
            )
        }
        delivery_remaining_total = 0
        for item in sale.items.all():
            delivered_qty = delivered_map.get(item.id, 0)
            net_qty = item.quantity - (item.returned_quantity or 0)
            remaining = net_qty - delivered_qty
            if remaining < 0:
                remaining = 0
            delivery_remaining_total += remaining
        if sale.items.exists() and delivery_remaining_total == 0:
            raise ValidationError("Levantamento concluido. Nao pode cancelar esta venda.")
        if not business.feature_enabled("enable_returns") and return_type != Sale.RETURN_NONE:
            raise ValidationError("Devolucoes nao estao ativas para este negocio.")
        if return_type not in {
            Sale.RETURN_NONE,
            Sale.RETURN_PARTIAL,
            Sale.RETURN_TOTAL,
        }:
            raise ValidationError("Tipo de devolucao invalido.")
        prev_subtotal = sale.subtotal
        prev_tax = sale.tax_total
        prev_discount = sale.discount_total
        prev_total = sale.total
        prev_before_discount = prev_subtotal + prev_tax
        items = sale.items.select_related("product")
        delivered_map = {
            row["sale_item_id"]: row["total"] or 0
            for row in (
                DeliveryGuideItem.objects.filter(
                    guide__sale=sale,
                    guide__status__in=["issued", "partial", "delivered"],
                )
                .values("sale_item_id")
                .annotate(total=Sum("quantity"))
            )
        }
        return_subtotal = Decimal("0")
        return_tax = Decimal("0")
        return_total_before_discount = Decimal("0")
        if return_type == Sale.RETURN_TOTAL:
            for item in items:
                delivered_qty = delivered_map.get(item.id, Decimal("0"))
                returnable = delivered_qty - item.returned_quantity
                if returnable < 0:
                    returnable = Decimal("0")
                returned_now = returnable
                if item.quantity > 0 and returned_now > 0:
                    ratio = Decimal(returned_now) / Decimal(item.quantity)
                    return_subtotal += item.line_subtotal * ratio
                    return_tax += item.line_tax * ratio
                    return_total_before_discount += item.line_total * ratio
                    item.returned_quantity = item.returned_quantity + returned_now
                    item.save(update_fields=["returned_quantity"])
                    if item.product.stock_control_mode == item.product.STOCK_AUTOMATIC:
                        record_movement(
                            business=sale.business,
                            product=item.product,
                            movement_type=StockMovement.MOVEMENT_IN,
                            quantity=returned_now,
                            created_by=user,
                            reference_type="sale_cancel",
                            reference_id=sale.id,
                        )
        elif return_type == Sale.RETURN_PARTIAL:
            return_items = return_items or {}
            any_returned = False
            for item in items:
                qty = int(return_items.get(item.id, 0) or 0)
                if qty <= 0:
                    continue
                any_returned = True
                delivered_qty = delivered_map.get(item.id, Decimal("0"))
                returnable = delivered_qty - item.returned_quantity
                if returnable < 0:
                    returnable = Decimal("0")
                if qty > returnable:
                    raise ValidationError(
                        f"Quantidade invalida para {item.product.name}."
                    )
                if item.quantity > 0:
                    ratio = Decimal(qty) / Decimal(item.quantity)
                    return_subtotal += item.line_subtotal * ratio
                    return_tax += item.line_tax * ratio
                    return_total_before_discount += item.line_total * ratio
                item.returned_quantity = item.returned_quantity + qty
                item.save(update_fields=["returned_quantity"])
                if item.product.stock_control_mode == item.product.STOCK_AUTOMATIC:
                    record_movement(
                        business=sale.business,
                        product=item.product,
                        movement_type=StockMovement.MOVEMENT_IN,
                        quantity=qty,
                        created_by=user,
                        reference_type="sale_cancel_partial",
                        reference_id=sale.id,
                    )
            if not any_returned:
                raise ValidationError("Indique pelo menos uma quantidade para devolucao.")
        return_discount = Decimal("0")
        if prev_before_discount > 0 and return_total_before_discount > 0:
            return_discount = (prev_discount * return_total_before_discount) / prev_before_discount
        return_total = return_total_before_discount - return_discount
        if return_total < 0:
            return_total = Decimal("0")
        sale.subtotal = max(prev_subtotal - return_subtotal, Decimal("0"))
        sale.tax_total = max(prev_tax - return_tax, Decimal("0"))
        sale.discount_total = max(prev_discount - return_discount, Decimal("0"))
        sale.total = max(prev_total - return_total, Decimal("0"))
        if sale.down_payment_total > sale.total:
            sale.down_payment_total = sale.total
        sale.status = Sale.STATUS_CANCELED
        sale.updated_by = user
        sale.canceled_at = timezone.now()
        sale.canceled_by = user
        sale.cancel_reason = notes
        sale.return_type = return_type
        sale.payment_status = Sale.PAYMENT_UNPAID
        sale.save(
            update_fields=[
                "status",
                "updated_by",
                "canceled_at",
                "canceled_by",
                "cancel_reason",
                "return_type",
                "payment_status",
                "subtotal",
                "tax_total",
                "discount_total",
                "total",
                "down_payment_total",
            ]
        )
        SaleRefund.objects.create(
            business=sale.business,
            sale=sale,
            return_type=return_type,
            amount=return_total,
            status=SaleRefund.STATUS_REFUNDED,
            notes=notes,
            created_by=user,
        )
        if sale.receivables.exists():
            receivable = sale.receivables.first()
            receivable.original_amount = sale.total
            if receivable.total_paid > receivable.original_amount:
                receivable.total_paid = receivable.original_amount
            receivable.status = (
                Receivable.STATUS_SETTLED
                if receivable.balance <= 0
                else Receivable.STATUS_OPEN
            )
            receivable.save(update_fields=["original_amount", "total_paid", "status"])
        if sale.invoices.exists():
            invoice = sale.invoices.first()
            invoice.status = Invoice.STATUS_CANCELED
            invoice.save(update_fields=["status"])
    return sale
