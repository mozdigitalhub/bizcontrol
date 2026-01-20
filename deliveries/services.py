from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from billing.models import Sequence
from tenants.services import generate_document_code
from deliveries.models import DeliveryGuide, DeliveryGuideItem
from inventory.models import StockMovement
from inventory.services import get_product_stock, record_movement
from sales.models import Sale


def get_deposit_limits(*, sale):
    if sale.sale_type != Sale.SALE_TYPE_DEPOSIT:
        return None
    invoice = sale.invoices.order_by("-created_at").first()
    paid = Decimal("0")
    if invoice:
        paid = Decimal(invoice.amount_paid or 0)
    total = Decimal(sale.total or 0)
    if total <= 0:
        ratio = Decimal("0")
    else:
        ratio = paid / total
    if ratio < 0:
        ratio = Decimal("0")
    if ratio > 1:
        ratio = Decimal("1")
    allowed_map = {}
    for item in sale.items.all():
        net_qty = item.quantity - (item.returned_quantity or 0)
        if net_qty < 0:
            net_qty = 0
        allowed_map[item.id] = int(Decimal(net_qty) * ratio)
    return {"ratio": ratio, "paid": paid, "invoice": invoice, "allowed_map": allowed_map}


def _next_sequence_value(*, business, name):
    seq = Sequence.objects.select_for_update().filter(business=business, name=name).first()
    if not seq:
        seq = Sequence.objects.create(business=business, name=name, current_value=0)
    seq.current_value += 1
    seq.save(update_fields=["current_value"])
    return seq.current_value


def _delivered_map(sale):
    delivered = (
        DeliveryGuideItem.objects.filter(
            guide__sale=sale,
            guide__status__in=[
                DeliveryGuide.STATUS_ISSUED,
                DeliveryGuide.STATUS_PARTIAL,
                DeliveryGuide.STATUS_DELIVERED,
            ],
        )
        .values("sale_item_id")
        .annotate(total=Sum("quantity"))
    )
    return {item["sale_item_id"]: item["total"] or 0 for item in delivered}


def _remaining_for_item(sale_item, delivered_map):
    delivered_qty = delivered_map.get(sale_item.id, 0)
    net_qty = sale_item.quantity - (sale_item.returned_quantity or 0)
    remaining = net_qty - delivered_qty
    if remaining < 0:
        remaining = 0
    return int(remaining)


def _origin_type_for_sale(sale):
    if sale.sale_type == Sale.SALE_TYPE_DEPOSIT:
        return DeliveryGuide.ORIGIN_DEPOSIT
    if sale.is_credit:
        return DeliveryGuide.ORIGIN_CREDIT
    return DeliveryGuide.ORIGIN_SALE


def _update_sale_delivery_status(*, sale, delivered_map):
    remaining_total = 0
    delivered_total = 0
    for item in sale.items.all():
        remaining = _remaining_for_item(item, delivered_map)
        remaining_total += remaining
        delivered_total += item.quantity - remaining
    if remaining_total <= 0 and delivered_total > 0:
        sale.delivery_status = Sale.DELIVERY_STATUS_DELIVERED
    elif delivered_total > 0:
        sale.delivery_status = Sale.DELIVERY_STATUS_PARTIAL
    else:
        sale.delivery_status = Sale.DELIVERY_STATUS_PENDING
    sale.save(update_fields=["delivery_status"])


def _create_guide(
    *,
    sale,
    user,
    items_map,
    notes="",
    delivery_kind="partial",
    expected_delivery_date=None,
    transport_responsible="",
    transport_cost=None,
):
    delivered_map = _delivered_map(sale)
    items_to_deliver = []
    remaining_total = 0
    allowed_remaining_total = 0
    deposit_data = get_deposit_limits(sale=sale)
    allow_over = bool(sale.business.allow_over_delivery_deposit)
    if deposit_data:
        if not deposit_data["invoice"]:
            raise ValidationError("Gere a fatura antes do levantamento.")
        if deposit_data["paid"] <= 0 and not allow_over:
            raise ValidationError("Registe um pagamento do deposito antes do levantamento.")
    for item in sale.items.all():
        remaining = _remaining_for_item(item, delivered_map)
        remaining_total += remaining
        if deposit_data and not allow_over:
            allowed_total = deposit_data["allowed_map"].get(item.id, 0)
            delivered_qty = delivered_map.get(item.id, 0)
            allowed_remaining = allowed_total - delivered_qty
            if allowed_remaining < 0:
                allowed_remaining = 0
            allowed_remaining_total += min(remaining, allowed_remaining)
    requested_total = 0
    for item in sale.items.select_related("product"):
        qty_raw = items_map.get(str(item.id), "0")
        try:
            qty_decimal = Decimal(qty_raw)
        except Exception:
            qty_decimal = Decimal("0")
        if qty_decimal != qty_decimal.to_integral_value():
            raise ValidationError(
                f"Quantidade deve ser inteira para {item.product.name}."
            )
        qty = int(qty_decimal)
        if qty <= 0:
            continue
        remaining = _remaining_for_item(item, delivered_map)
        allowed_remaining = remaining
        if deposit_data and not allow_over:
            allowed_total = deposit_data["allowed_map"].get(item.id, 0)
            delivered_qty = delivered_map.get(item.id, 0)
            allowed_remaining = allowed_total - delivered_qty
            if allowed_remaining < 0:
                allowed_remaining = 0
        if qty > remaining:
            raise ValidationError(
                f"Quantidade acima do pendente para {item.product.name}."
            )
        if deposit_data and not allow_over and qty > allowed_remaining:
            raise ValidationError(
                f"Quantidade acima do permitido pelo pagamento para {item.product.name}. Disponivel: {allowed_remaining}."
            )
        if item.product.stock_control_mode == item.product.STOCK_AUTOMATIC:
            if not sale.business.allow_negative_stock:
                current_stock = get_product_stock(sale.business, item.product)
                if current_stock < qty:
                    raise ValidationError(
                        f"Stock insuficiente para {item.product.name}."
                    )
        items_to_deliver.append((item, qty))
        requested_total += qty

    if not items_to_deliver:
        raise ValidationError("Indique pelo menos um item para levantamento.")
    if deposit_data and not allow_over and delivery_kind == "total" and allowed_remaining_total < remaining_total:
        raise ValidationError("Pagamento insuficiente para levantamento total.")
    if delivery_kind == "partial" and remaining_total > 0 and requested_total >= remaining_total:
        raise ValidationError("Para levantamento total selecione a opcao total.")

    guide_number = _next_sequence_value(business=sale.business, name="delivery_guide")
    issued_at = timezone.now()
    code = generate_document_code(
        business=sale.business,
        doc_type="delivery",
        prefix="G",
        date=issued_at.date(),
    )
    guide = DeliveryGuide.objects.create(
        business=sale.business,
        sale=sale,
        customer=sale.customer,
        code=code,
        guide_number=guide_number,
        origin_type=_origin_type_for_sale(sale),
        issued_at=issued_at,
        status=DeliveryGuide.STATUS_DELIVERED
        if delivery_kind == "total"
        else DeliveryGuide.STATUS_PARTIAL,
        notes=notes,
        created_by=user,
        delivered_by=user,
        expected_delivery_date=expected_delivery_date,
        transport_responsible=transport_responsible,
        transport_cost=transport_cost,
    )

    for item, qty in items_to_deliver:
        DeliveryGuideItem.objects.create(
            guide=guide,
            sale_item=item,
            product=item.product,
            quantity=qty,
        )
        if item.product.stock_control_mode == item.product.STOCK_AUTOMATIC:
            record_movement(
                business=sale.business,
                product=item.product,
                movement_type=StockMovement.MOVEMENT_OUT,
                quantity=qty,
                created_by=user,
                reference_type="delivery_guide",
                reference_id=guide.id,
            )

    delivered_map = _delivered_map(sale)
    _update_sale_delivery_status(sale=sale, delivered_map=delivered_map)
    return guide


def register_delivery(
    *,
    sale_id,
    business,
    user,
    items_map,
    notes="",
    delivery_kind="partial",
    expected_delivery_date=None,
    transport_responsible="",
    transport_cost=None,
):
    with transaction.atomic():
        sale = (
            Sale.objects.select_for_update()
            .select_related("business")
            .get(id=sale_id, business=business)
        )
        if sale.status != Sale.STATUS_CONFIRMED:
            raise ValidationError("A venda precisa estar confirmada.")
        if not sale.invoices.exists():
            raise ValidationError("Gere a fatura antes de registar o levantamento.")
        if sale.sale_type == Sale.SALE_TYPE_DEPOSIT:
            invoice = sale.invoices.order_by("-created_at").first()
            allow_over = bool(sale.business.allow_over_delivery_deposit)
            if not invoice:
                raise ValidationError("Registe a fatura antes de levantar o material.")
            if invoice.amount_paid <= 0 and not allow_over:
                raise ValidationError("Registe o pagamento do deposito antes de levantar o material.")
        elif not sale.is_credit and sale.payment_status != Sale.PAYMENT_PAID:
            raise ValidationError("Registe o pagamento antes de levantar o material.")
        return _create_guide(
            sale=sale,
            user=user,
            items_map=items_map,
            notes=notes,
            delivery_kind=delivery_kind,
            expected_delivery_date=expected_delivery_date,
            transport_responsible=transport_responsible,
            transport_cost=transport_cost,
        )


def create_delivery_for_sale(*, sale, user):
    items_map = {str(item.id): str(item.quantity) for item in sale.items.all()}
    return _create_guide(
        sale=sale,
        user=user,
        items_map=items_map,
        delivery_kind="total",
    )


def cancel_delivery(*, guide_id, business, user, notes=""):
    with transaction.atomic():
        guide = (
            DeliveryGuide.objects.select_for_update()
            .select_related("sale")
            .get(id=guide_id, business=business)
        )
        if guide.status == DeliveryGuide.STATUS_CANCELED:
            raise ValidationError("A guia ja esta cancelada.")
        for item in guide.items.select_related("product"):
            if item.product.stock_control_mode == item.product.STOCK_AUTOMATIC:
                record_movement(
                    business=guide.business,
                    product=item.product,
                    movement_type=StockMovement.MOVEMENT_IN,
                    quantity=item.quantity,
                    created_by=user,
                    reference_type="delivery_cancel",
                    reference_id=guide.id,
                    notes=notes,
                )
        guide.status = DeliveryGuide.STATUS_CANCELED
        guide.notes = notes
        guide.save(update_fields=["status", "notes"])
        delivered_map = _delivered_map(guide.sale)
        _update_sale_delivery_status(sale=guide.sale, delivered_map=delivered_map)
        return guide
