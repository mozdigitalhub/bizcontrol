from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from finance.services import _create_cash_in
from sales.services import calculate_line_totals
from tenants.services import generate_document_code
from food.models import (
    DeliveryInfo,
    FoodIngredient,
    IngredientMovement,
    IngredientStockEntry,
    IngredientStockEntryItem,
    MenuItem,
    MenuItemRecipe,
    Order,
    OrderItem,
    OrderPayment,
)


def _calculate_totals(*, business, items):
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    total = Decimal("0")
    prepared = []
    for item in items:
        effective_unit = item["unit_price"]
        line_subtotal, line_tax, line_total = calculate_line_totals(
            business=business,
            unit_price=effective_unit,
            quantity=item["quantity"],
        )
        prepared.append(
            {
                **item,
                "line_subtotal": line_subtotal,
                "line_tax": line_tax,
                "line_total": line_total,
                "effective_unit": effective_unit,
            }
        )
        subtotal += line_subtotal
        tax_total += line_tax
        total += line_total
    return prepared, subtotal, tax_total, total


def create_order(*, business, user, order_data, items, delivery_data=None):
    if not items:
        raise ValidationError("Adicione pelo menos um item.")
    with transaction.atomic():
        _assert_ingredients_available(business=business, items=items)
        prepared, subtotal, tax_total, total = _calculate_totals(
            business=business, items=items
        )
        delivery_fee = Decimal("0")
        if delivery_data and delivery_data.get("delivery_fee"):
            delivery_fee = Decimal(delivery_data.get("delivery_fee"))
            total += delivery_fee
        pay_before = business.feature_enabled("pay_before_service")
        payment_method = order_data.get("payment_method") or ""
        if pay_before and not payment_method:
            raise ValidationError("Selecione o metodo de pagamento.")
        amount_paid = total if payment_method else Decimal("0")
        payment_status = Order.PAYMENT_PAID if amount_paid >= total and total > 0 else Order.PAYMENT_UNPAID
        order = Order.objects.create(
            business=business,
            customer=order_data.get("customer"),
            channel=order_data.get("channel"),
            payment_method=payment_method,
            notes=order_data.get("notes", ""),
            subtotal=subtotal,
            tax_total=tax_total,
            total=total,
            status=Order.STATUS_CONFIRMED,
            payment_status=payment_status,
            amount_paid=amount_paid,
            created_by=user,
        )
        order.code = generate_document_code(
            business=business,
            doc_type="order",
            prefix="P",
            date=timezone.localdate(),
        )
        order.save(update_fields=["code"])
        for item in prepared:
            order_item = OrderItem.objects.create(
                order=order,
                menu_item=item["menu_item"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                line_subtotal=item["line_subtotal"],
                line_tax=item["line_tax"],
                line_total=item["line_total"],
                notes=item.get("notes", ""),
            )
        if order.channel == Order.CHANNEL_DELIVERY and delivery_data:
            DeliveryInfo.objects.create(order=order, **delivery_data)
        if amount_paid > 0:
            OrderPayment.objects.create(
                order=order,
                method=payment_method,
                amount=amount_paid,
                paid_at=timezone.now(),
                created_by=user,
            )
            _create_cash_in(
                business=business,
                amount=amount_paid,
                method=payment_method,
                reference_type="order",
                reference_id=order.id,
                user=user,
                notes=f"Pedido {order.code}",
            )
        _deduct_ingredients(business=business, items=items, user=user, order=order)
        return order


def update_order_status(*, order, status, user):
    allowed = {Order.STATUS_IN_PREPARATION, Order.STATUS_READY, Order.STATUS_DELIVERED}
    if status not in allowed:
        raise ValidationError("Estado invalido.")
    order.status = status
    order.updated_by = user
    order.save(update_fields=["status", "updated_by"])
    return order


def _assert_ingredients_available(*, business, items):
    required = {}
    for item in items:
        menu_item = item["menu_item"]
        qty = item["quantity"]
        if menu_item.item_type == MenuItem.TYPE_FOOD:
            for recipe in MenuItemRecipe.objects.select_related("ingredient").filter(
                menu_item=menu_item
            ):
                needed = recipe.quantity * Decimal(qty)
                required[recipe.ingredient_id] = required.get(recipe.ingredient_id, Decimal("0")) + needed
        elif menu_item.ingredient_id:
            required[menu_item.ingredient_id] = required.get(menu_item.ingredient_id, Decimal("0")) + Decimal(qty)
    if not required:
        return
    ingredients = FoodIngredient.objects.filter(
        business=business, id__in=required.keys(), is_active=True
    )
    for ingredient in ingredients:
        needed = required.get(ingredient.id, Decimal("0"))
        if ingredient.stock_qty < needed:
            raise ValidationError(
                f"Ingredientes insuficientes para {ingredient.name}."
            )


def _deduct_ingredients(*, business, items, user, order):
    required = {}
    for item in items:
        menu_item = item["menu_item"]
        qty = item["quantity"]
        if menu_item.item_type == MenuItem.TYPE_FOOD:
            for recipe in MenuItemRecipe.objects.select_related("ingredient").filter(
                menu_item=menu_item
            ):
                needed = recipe.quantity * Decimal(qty)
                required[recipe.ingredient_id] = required.get(recipe.ingredient_id, Decimal("0")) + needed
        elif menu_item.ingredient_id:
            required[menu_item.ingredient_id] = required.get(menu_item.ingredient_id, Decimal("0")) + Decimal(qty)
    if not required:
        return
    ingredients = FoodIngredient.objects.select_for_update().filter(
        business=business, id__in=required.keys(), is_active=True
    )
    for ingredient in ingredients:
        needed = required.get(ingredient.id, Decimal("0"))
        ingredient.stock_qty = ingredient.stock_qty - needed
        ingredient.save(update_fields=["stock_qty"])
        IngredientMovement.objects.create(
            business=business,
            ingredient=ingredient,
            movement_type=IngredientMovement.MOVEMENT_OUT,
            quantity=needed,
            reference_type="order",
            reference_id=order.id,
            notes=f"Pedido {order.code}",
            created_by=user,
        )


def create_ingredient_entry(*, business, user, entry_data, items):
    if not items:
        raise ValidationError("Adicione pelo menos um ingrediente.")
    with transaction.atomic():
        entry = IngredientStockEntry.objects.create(
            business=business,
            supplier_name=entry_data.get("supplier_name", ""),
            reference_number=entry_data.get("reference_number", ""),
            entry_date=entry_data.get("entry_date"),
            notes=entry_data.get("notes", ""),
            created_by=user,
        )
        for item in items:
            ingredient = item.get("ingredient")
            quantity = item.get("quantity")
            if not ingredient or not quantity or quantity <= 0:
                continue
            unit_cost = item.get("unit_cost")
            IngredientStockEntryItem.objects.create(
                entry=entry,
                ingredient=ingredient,
                quantity=quantity,
                unit_cost=unit_cost,
            )
            ingredient.stock_qty = ingredient.stock_qty + quantity
            if unit_cost:
                ingredient.cost_price = unit_cost
            ingredient.save(update_fields=["stock_qty", "cost_price"])
            IngredientMovement.objects.create(
                business=business,
                ingredient=ingredient,
                movement_type=IngredientMovement.MOVEMENT_IN,
                quantity=quantity,
                reference_type="ingredient_entry",
                reference_id=entry.id,
                notes=f"Entrada {entry.id}",
                created_by=user,
            )
        return entry
