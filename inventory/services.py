from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from inventory.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    ProductCostHistory,
    ProductSalePriceHistory,
    StockMovement,
)


def _compose_stock_balance(summary):
    incoming = summary.get(StockMovement.MOVEMENT_IN) or 0
    outgoing = summary.get(StockMovement.MOVEMENT_OUT) or 0
    adjust = summary.get(StockMovement.MOVEMENT_ADJUST) or 0
    return int(incoming) - int(outgoing) + int(adjust)


def get_stock_snapshot_by_product_ids(business, product_ids):
    if not product_ids:
        return {}
    totals = (
        StockMovement.objects.filter(business=business, product_id__in=product_ids)
        .values("product_id", "movement_type")
        .annotate(total=Sum("quantity"))
    )
    grouped = {}
    for row in totals:
        product_id = row["product_id"]
        grouped.setdefault(product_id, {})[row["movement_type"]] = row["total"] or 0
    return {product_id: _compose_stock_balance(summary) for product_id, summary in grouped.items()}


def get_product_stock(business, product):
    totals = (
        StockMovement.objects.filter(business=business, product=product)
        .values("movement_type")
        .annotate(total=Sum("quantity"))
    )
    summary = {row["movement_type"]: row["total"] for row in totals}
    return _compose_stock_balance(summary)


def record_movement(
    *,
    business,
    product,
    movement_type,
    quantity,
    created_by=None,
    reference_type="",
    reference_id=None,
    notes="",
):
    return StockMovement.objects.create(
        business=business,
        product=product,
        movement_type=movement_type,
        quantity=int(quantity),
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
        created_by=created_by,
    )


def receive_goods(
    *,
    business,
    user,
    receipt_data,
    items_data,
    create_cash_movement=False,
    payment_method=None,
    purchase=None,
):
    if not items_data:
        raise ValueError("Adicione pelo menos um produto.")
    supplier = receipt_data["supplier"]
    if purchase:
        if purchase.business_id != business.id:
            raise ValueError("Compra invalida para este negocio.")
        if purchase.purchase_type != purchase.TYPE_STOCK:
            raise ValueError("Compra selecionada nao e de reposicao.")
        if purchase.supplier_id and purchase.supplier_id != supplier.id:
            raise ValueError("Fornecedor nao corresponde a compra selecionada.")
    if supplier.business_id != business.id:
        raise ValueError("Fornecedor invalido para este negocio.")
    if create_cash_movement and payment_method is None:
        raise ValueError("Selecione o metodo de pagamento.")
    if create_cash_movement and payment_method is not None:
        if payment_method.business_id != business.id or not payment_method.is_active:
            raise ValueError("Metodo de pagamento invalido.")
    total_cost = None
    if create_cash_movement:
        total_cost = Decimal("0")
        for item in items_data:
            unit_cost = item.get("unit_cost")
            if unit_cost is None or unit_cost <= 0:
                raise ValueError(
                    "Informe o custo de aquisicao de todos os produtos para gerar movimento de caixa."
                )
            total_cost += unit_cost * item["quantity"]

    with transaction.atomic():
        receipt = GoodsReceipt.objects.create(
            business=business,
            purchase=purchase,
            supplier=supplier,
            document_number=receipt_data["document_number"],
            document_date=receipt_data["document_date"],
            storage_location=receipt_data.get("storage_location", ""),
            notes=receipt_data.get("notes", ""),
            created_by=user,
        )

        for item in items_data:
            product = item["product"]
            quantity = item["quantity"]
            unit_cost = item.get("unit_cost")
            sale_price = item["sale_price"]

            GoodsReceiptItem.objects.create(
                receipt=receipt,
                product=product,
                quantity=quantity,
                unit_cost=unit_cost,
                sale_price=sale_price,
                storage_location="",
            )

            if not purchase or not purchase.stock_received:
                record_movement(
                    business=business,
                    product=product,
                    movement_type=StockMovement.MOVEMENT_IN,
                    quantity=quantity,
                    created_by=user,
                    reference_type="goods_receipt",
                    reference_id=receipt.id,
                    notes=f"Guia {receipt.document_number}",
                )

            update_fields = []
            if unit_cost is not None:
                ProductCostHistory.objects.create(
                    business=business,
                    product=product,
                    receipt=receipt,
                    unit_cost=unit_cost,
                    created_by=user,
                )
                if product.cost_price != unit_cost:
                    product.cost_price = unit_cost
                    update_fields.append("cost_price")

            if product.sale_price != sale_price:
                ProductSalePriceHistory.objects.create(
                    business=business,
                    product=product,
                    receipt=receipt,
                    old_price=product.sale_price,
                    new_price=sale_price,
                    created_by=user,
                )
                product.sale_price = sale_price
                update_fields.append("sale_price")

            if update_fields:
                product.save(update_fields=update_fields)

        if purchase and not purchase.stock_received:
            purchase.stock_received = True
            purchase.updated_by = user
            purchase.save(update_fields=["stock_received", "updated_by"])

        if create_cash_movement:
            from finance.services import _create_cash_out

            cash_movement = _create_cash_out(
                business=business,
                amount=total_cost,
                method=payment_method.code if payment_method else "",
                reference_type="goods_receipt",
                reference_id=receipt.id,
                user=user,
                notes=f"Fornecedor: {supplier.name} | Guia: {receipt.document_number}",
                happened_at=receipt.document_date,
            )
            receipt.cash_movement = cash_movement
            receipt.save(update_fields=["cash_movement"])

        return receipt
