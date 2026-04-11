from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from django.db.models import ExpressionWrapper, F, IntegerField, Sum

from deliveries.models import DeliveryGuide, DeliveryGuideItem
from inventory.models import StockMovement
from inventory.services import get_product_stock, record_movement
from sales.models import Sale, SaleItem
from sales.services import calculate_line_totals
from tenants.services import generate_document_code
from quotations.models import Quotation, QuotationItem, QuotationStatusHistory


def _decimal(value):
    try:
        return Decimal(value)
    except Exception:
        return Decimal("0")


def recalculate_quotation_totals(quotation):
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for item in quotation.items.all():
        subtotal += item.line_subtotal
        tax_total += item.line_tax
    total_before_discount = subtotal + tax_total
    discount_total = Decimal("0")
    discount_value = quotation.discount_value or Decimal("0")
    if quotation.discount_type == Quotation.DISCOUNT_PERCENT:
        discount_total = (total_before_discount * discount_value) / Decimal("100")
    elif quotation.discount_type == Quotation.DISCOUNT_FIXED:
        discount_total = discount_value
    if discount_total < 0:
        discount_total = Decimal("0")
    if discount_total > total_before_discount:
        discount_total = total_before_discount
    total = total_before_discount - discount_total
    quotation.subtotal = subtotal
    quotation.tax_total = tax_total
    quotation.discount_total = discount_total
    quotation.total = total
    quotation.save(update_fields=["subtotal", "tax_total", "discount_total", "total"])
    return quotation


def add_status_history(*, quotation, status, user=None, notes=""):
    QuotationStatusHistory.objects.create(
        quotation=quotation,
        status=status,
        changed_by=user,
        notes=notes,
    )


def update_quotation_items(*, quotation, items_data):
    quotation.items.all().delete()
    for item in items_data:
        product = item.get("product")
        description = (item.get("description") or "").strip()
        if product and not description:
            description = product.name
        if not description:
            raise ValidationError("Informe a descricao do item.")
        quantity = int(item.get("quantity") or 0)
        if quantity <= 0:
            raise ValidationError("Quantidade invalida.")
        unit_price = _decimal(item.get("unit_price"))
        if unit_price <= 0 and product and product.sale_price:
            unit_price = Decimal(product.sale_price)
        if unit_price <= 0:
            raise ValidationError("Informe o preco unitario.")
        line_subtotal, line_tax, line_total = calculate_line_totals(
            business=quotation.business,
            unit_price=unit_price,
            quantity=quantity,
        )
        tax_rate = quotation.business.vat_rate if quotation.business.vat_enabled else Decimal("0")
        QuotationItem.objects.create(
            quotation=quotation,
            product=product,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            tax_rate=tax_rate,
            line_subtotal=line_subtotal,
            line_tax=line_tax,
            line_total=line_total,
        )
    recalculate_quotation_totals(quotation)
    return quotation


def get_quotation_stock_shortages(*, quotation):
    items = quotation.items.select_related("product")
    product_ids = [item.product_id for item in items if item.product_id]
    if not product_ids:
        return []

    ordered_quantities = (
        SaleItem.objects.filter(
            sale__business=quotation.business,
            sale__status=Sale.STATUS_CONFIRMED,
            product_id__in=product_ids,
        )
        .values("product_id")
        .annotate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") - F("returned_quantity"),
                    output_field=IntegerField(),
                )
            )
        )
    )
    ordered_map = {row["product_id"]: row["total"] or 0 for row in ordered_quantities}

    delivered_quantities = (
        DeliveryGuideItem.objects.filter(
            guide__business=quotation.business,
            guide__status__in=[
                DeliveryGuide.STATUS_ISSUED,
                DeliveryGuide.STATUS_PARTIAL,
                DeliveryGuide.STATUS_DELIVERED,
            ],
            product_id__in=product_ids,
        )
        .values("product_id")
        .annotate(total=Sum("quantity"))
    )
    delivered_map = {row["product_id"]: row["total"] or 0 for row in delivered_quantities}

    shortages = []
    for item in items:
        product = item.product
        if not product or product.stock_control_mode != product.STOCK_AUTOMATIC:
            continue
        stock_qty = int(get_product_stock(quotation.business, product))
        reserved_qty = int(ordered_map.get(product.id, 0)) - int(
            delivered_map.get(product.id, 0)
        )
        if reserved_qty < 0:
            reserved_qty = 0
        available_qty = stock_qty - reserved_qty
        if available_qty < 0:
            available_qty = 0
        if item.quantity > available_qty:
            shortages.append(
                {
                    "product_id": product.id,
                    "product": product.name,
                    "requested": int(item.quantity),
                    "available": int(available_qty),
                }
            )
    return shortages


def approve_quotation(*, quotation_id, business, user, confirm_stock=False):
    quotation = Quotation.objects.select_related("business").get(
        id=quotation_id, business=business
    )
    if quotation.valid_until and quotation.valid_until < timezone.localdate():
        if quotation.status != Quotation.STATUS_EXPIRED:
            quotation.status = Quotation.STATUS_EXPIRED
            quotation.save(update_fields=["status"])
            add_status_history(quotation=quotation, status=quotation.status, user=user)
        raise ValidationError("A cotacao expirou e nao pode ser aprovada.")

    with transaction.atomic():
        quotation = (
            Quotation.objects.select_for_update()
            .select_related("business")
            .get(id=quotation_id, business=business)
        )
        shortages = get_quotation_stock_shortages(quotation=quotation)
        if shortages and not confirm_stock:
            raise ValidationError("Stock insuficiente para aprovar a cotacao.")
        if quotation.status not in {Quotation.STATUS_SENT, Quotation.STATUS_DRAFT}:
            raise ValidationError("A cotacao nao pode ser aprovada.")
        if quotation.sale_id:
            raise ValidationError("Esta cotacao ja foi convertida em venda.")
        if not quotation.customer_id:
            raise ValidationError("Selecione um cliente para aprovar.")
        items = list(quotation.items.select_related("product"))
        if not items:
            raise ValidationError("Cotacao sem itens.")
        for item in items:
            if not item.product_id:
                raise ValidationError("Itens sem produto nao podem ser aprovados.")

        sale_code = generate_document_code(
            business=quotation.business,
            doc_type="sale",
            prefix="V",
            date=timezone.localdate(),
        )
        sale = Sale.objects.create(
            business=quotation.business,
            customer=quotation.customer,
            sale_type=Sale.SALE_TYPE_NORMAL,
            delivery_mode=Sale.DELIVERY_SCHEDULED,
            status=Sale.STATUS_CONFIRMED,
            sale_date=timezone.now(),
            subtotal=quotation.subtotal,
            tax_total=quotation.tax_total,
            discount_type=quotation.discount_type,
            discount_value=quotation.discount_value,
            discount_total=quotation.discount_total,
            total=quotation.total,
            payment_status=Sale.PAYMENT_UNPAID,
            code=sale_code,
            created_by=user,
            updated_by=user,
        )

        for item in items:
            SaleItem.objects.create(
                sale=sale,
                product=item.product,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_subtotal=item.line_subtotal,
                line_tax=item.line_tax,
                line_total=item.line_total,
            )
            if item.product.stock_control_mode == item.product.STOCK_AUTOMATIC:
                record_movement(
                    business=quotation.business,
                    product=item.product,
                    movement_type=StockMovement.MOVEMENT_RESERVE,
                    quantity=item.quantity,
                    created_by=user,
                    reference_type="sale_reserve",
                    reference_id=sale.id,
                    notes=f"Reserva {sale.code or sale.id}",
                )

        quotation.status = Quotation.STATUS_APPROVED
        quotation.approved_at = timezone.now()
        quotation.approved_by = user
        quotation.sale = sale
        if not quotation.code:
            quotation.code = generate_document_code(
                business=quotation.business,
                doc_type="quotation",
                prefix="Q",
                date=quotation.issue_date,
            )
        if quotation.payment_snapshot is None:
            quotation.payment_snapshot = quotation.business.get_payment_snapshot()
        quotation.save(update_fields=["status", "approved_at", "approved_by", "sale", "code", "payment_snapshot"])
        add_status_history(quotation=quotation, status=quotation.status, user=user)
        return quotation


def mark_quotation_sent(*, quotation, user):
    if quotation.status != Quotation.STATUS_DRAFT:
        raise ValidationError("A cotacao nao esta em rascunho.")
    quotation.status = Quotation.STATUS_SENT
    quotation.sent_at = timezone.now()
    if not quotation.code:
        quotation.code = generate_document_code(
            business=quotation.business,
            doc_type="quotation",
            prefix="Q",
            date=quotation.issue_date,
        )
    if quotation.payment_snapshot is None:
        quotation.payment_snapshot = quotation.business.get_payment_snapshot()
    quotation.save(update_fields=["status", "sent_at", "code", "payment_snapshot"])
    add_status_history(quotation=quotation, status=quotation.status, user=user)
    return quotation


def reject_quotation(*, quotation, user, notes=""):
    if quotation.status not in {Quotation.STATUS_SENT, Quotation.STATUS_DRAFT}:
        raise ValidationError("A cotacao nao pode ser rejeitada.")
    quotation.status = Quotation.STATUS_REJECTED
    quotation.rejected_at = timezone.now()
    quotation.rejected_by = user
    quotation.save(update_fields=["status", "rejected_at", "rejected_by"])
    add_status_history(quotation=quotation, status=quotation.status, user=user, notes=notes)
    return quotation


def cancel_quotation(*, quotation, user, notes=""):
    if quotation.status in {Quotation.STATUS_APPROVED, Quotation.STATUS_CANCELED}:
        raise ValidationError("A cotacao nao pode ser cancelada.")
    quotation.status = Quotation.STATUS_CANCELED
    quotation.canceled_at = timezone.now()
    quotation.canceled_by = user
    quotation.save(update_fields=["status", "canceled_at", "canceled_by"])
    add_status_history(quotation=quotation, status=quotation.status, user=user, notes=notes)
    return quotation
