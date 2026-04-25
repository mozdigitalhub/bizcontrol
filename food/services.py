from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from finance.services import _create_cash_in
from sales.services import calculate_line_totals
from tenants.models import Business
from tenants.services import generate_document_code
from food.models import (
    DeliveryInfo,
    FoodIngredient,
    FoodIngredientCategory,
    FoodIngredientUnit,
    FoodExtra,
    IngredientMovement,
    IngredientStockEntry,
    IngredientStockEntryItem,
    MenuCategory,
    MenuItem,
    MenuItemType,
    MenuItemRecipe,
    Order,
    OrderItem,
    OrderItemExtra,
    OrderPayment,
    RestaurantTable,
)


DEFAULT_INGREDIENT_CATEGORIES = [
    ("meat", "Carnes"),
    ("bread", "Paes"),
    ("dairy", "Laticinios"),
    ("beverage", "Bebidas"),
    ("sauce", "Molhos"),
    ("packaging", "Embalagens"),
    ("extra", "Extras"),
    ("condiment", "Condimentos"),
    ("other", "Outros"),
]

DEFAULT_INGREDIENT_UNITS = [
    ("unidade", "Unidade"),
    ("fatia", "Fatia"),
    ("grama", "Grama"),
    ("ml", "Mililitro"),
    ("kg", "Kg"),
    ("litro", "Litro"),
    ("embalagem", "Embalagem"),
]

DEFAULT_MENU_CATEGORIES = [
    "Hamburgueres",
    "Combos",
    "Bebidas",
    "Acompanhamentos",
    "Sobremesas",
]

DEFAULT_MENU_TYPES = [
    ("food", "Prato"),
    ("complement", "Complemento"),
    ("beverage", "Bebida"),
]


def ensure_default_ingredient_options(business):
    if not business or business.business_type not in {
        business.BUSINESS_BURGER,
        business.BUSINESS_RESTAURANT,
    }:
        return
    for code, name in DEFAULT_INGREDIENT_CATEGORIES:
        FoodIngredientCategory.objects.get_or_create(
            business=business,
            code=code,
            defaults={"name": name, "is_active": True},
        )
    for code, name in DEFAULT_INGREDIENT_UNITS:
        FoodIngredientUnit.objects.get_or_create(
            business=business,
            code=code,
            defaults={"name": name, "is_active": True},
        )


def ensure_default_menu_options(business):
    if not business or business.business_type != business.BUSINESS_BURGER:
        return
    for name in DEFAULT_MENU_CATEGORIES:
        MenuCategory.objects.get_or_create(
            business=business,
            name=name,
            defaults={"is_active": True},
        )
    for code, name in DEFAULT_MENU_TYPES:
        item_type, created = MenuItemType.objects.get_or_create(
            business=business,
            code=code,
            defaults={"name": name, "is_active": True},
        )
        if not created:
            update_fields = []
            if item_type.name != name:
                item_type.name = name
                update_fields.append("name")
            if not item_type.is_active:
                item_type.is_active = True
                update_fields.append("is_active")
            if update_fields:
                item_type.save(update_fields=update_fields)


def _calculate_totals(*, business, items):
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    total = Decimal("0")
    prepared = []
    for item in items:
        extras = list(item.get("extras") or [])
        variant = item.get("variant")
        extras_unit_total = sum((extra.extra_price for extra in extras), Decimal("0"))
        if variant:
            extras_unit_total += variant.extra_price
        effective_unit = Decimal(item["unit_price"]) + extras_unit_total
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
                "variant": variant,
                "extras": extras,
            }
        )
        subtotal += line_subtotal
        tax_total += line_tax
        total += line_total
    return prepared, subtotal, tax_total, total


def _compose_order_item_notes(*, base_notes, variant, extras):
    parts = []
    if variant:
        parts.append(f"Variante: {variant.name}")
    if extras:
        parts.append("Extras: " + ", ".join(extra.name for extra in extras))
    if base_notes:
        parts.append(base_notes.strip())
    return " | ".join(part for part in parts if part).strip()


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
        payment_method = (order_data.get("payment_method") or "").strip()
        if business.business_type == Business.BUSINESS_BURGER:
            pay_before = False
            payment_method = ""
        table = order_data.get("table")
        if table and table.business_id != business.id:
            raise ValidationError("Mesa invalida para este negocio.")
        if table and order_data.get("channel") != Order.CHANNEL_DINE_IN:
            raise ValidationError("Mesa so pode ser usada em pedidos de servico a mesa.")
        if (
            table
            and business.feature_enabled("use_tables")
            and table.status == RestaurantTable.STATUS_RESERVED
        ):
            raise ValidationError("A mesa selecionada esta reservada.")
        if pay_before and not payment_method:
            raise ValidationError("Selecione o metodo de pagamento.")
        amount_paid = total if payment_method else Decimal("0")
        payment_status = Order.PAYMENT_PAID if amount_paid >= total and total > 0 else Order.PAYMENT_UNPAID
        order = Order.objects.create(
            business=business,
            customer=order_data.get("customer"),
            channel=order_data.get("channel"),
            table=table if business.feature_enabled("use_tables") else None,
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
        if order.table_id:
            RestaurantTable.objects.filter(id=order.table_id).update(
                status=RestaurantTable.STATUS_OCCUPIED
            )
        for item in prepared:
            item_notes = _compose_order_item_notes(
                base_notes=item.get("notes", ""),
                variant=item.get("variant"),
                extras=item.get("extras", []),
            )
            order_item = OrderItem.objects.create(
                order=order,
                menu_item=item["menu_item"],
                quantity=item["quantity"],
                unit_price=item["effective_unit"],
                line_subtotal=item["line_subtotal"],
                line_tax=item["line_tax"],
                line_total=item["line_total"],
                notes=item_notes,
            )
            if item.get("variant"):
                variant = item["variant"]
                OrderItemExtra.objects.create(
                    order_item=order_item,
                    extra=variant,
                    quantity=item["quantity"],
                    unit_price=variant.extra_price,
                    line_total=variant.extra_price * item["quantity"],
                )
            for extra in item.get("extras", []):
                OrderItemExtra.objects.create(
                    order_item=order_item,
                    extra=extra,
                    quantity=item["quantity"],
                    unit_price=extra.extra_price,
                    line_total=extra.extra_price * item["quantity"],
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


def register_order_payment(*, order, business, user, method, amount):
    if amount <= 0:
        raise ValidationError("Informe um valor maior que zero.")
    if not method:
        raise ValidationError("Selecione o metodo de pagamento.")
    with transaction.atomic():
        locked = (
            Order.objects.select_for_update()
            .get(pk=order.pk, business_id=business.id)
        )
        if locked.status == Order.STATUS_CANCELED:
            raise ValidationError("Pedido cancelado nao pode receber pagamento.")
        open_balance = max(locked.total - locked.amount_paid, Decimal("0"))
        if open_balance <= 0:
            raise ValidationError("Pedido ja esta totalmente pago.")
        if amount > open_balance and not business.allow_over_delivery_deposit:
            raise ValidationError("Valor acima do saldo em aberto.")

        payment = OrderPayment.objects.create(
            order=locked,
            method=method,
            amount=amount,
            paid_at=timezone.now(),
            created_by=user,
        )
        _create_cash_in(
            business=business,
            amount=amount,
            method=method,
            reference_type="order_payment",
            reference_id=payment.id,
            user=user,
            notes=f"Pagamento {payment.id} do pedido {locked.code}",
        )
        locked.amount_paid = locked.amount_paid + amount
        if locked.total > 0 and locked.amount_paid >= locked.total:
            locked.payment_status = Order.PAYMENT_PAID
        elif locked.amount_paid > 0:
            locked.payment_status = Order.PAYMENT_PARTIAL
        else:
            locked.payment_status = Order.PAYMENT_UNPAID
        if not locked.payment_method:
            locked.payment_method = method
        locked.updated_by = user
        locked.save(
            update_fields=[
                "amount_paid",
                "payment_status",
                "payment_method",
                "updated_by",
                "updated_at",
            ]
        )
        return locked, payment


def update_order_status(*, order, status, user):
    allowed = {
        Order.STATUS_IN_PREPARATION,
        Order.STATUS_READY,
        Order.STATUS_DELIVERED,
        Order.STATUS_CANCELED,
    }
    if status not in allowed:
        raise ValidationError("Estado invalido.")
    with transaction.atomic():
        order = (
            Order.objects.select_for_update()
            .get(pk=order.pk, business_id=order.business_id)
        )
        if status == order.status:
            return order

        transitions = {
            Order.STATUS_CONFIRMED: {
                Order.STATUS_IN_PREPARATION,
                Order.STATUS_READY,
                Order.STATUS_CANCELED,
            },
            Order.STATUS_IN_PREPARATION: {
                Order.STATUS_READY,
                Order.STATUS_DELIVERED,
                Order.STATUS_CANCELED,
            },
            Order.STATUS_READY: {
                Order.STATUS_DELIVERED,
                Order.STATUS_CANCELED,
            },
            Order.STATUS_DELIVERED: set(),
            Order.STATUS_CANCELED: set(),
        }
        if status not in transitions.get(order.status, set()):
            raise ValidationError("Transicao de estado invalida.")
        if status == Order.STATUS_DELIVERED and order.total > 0 and order.amount_paid < order.total:
            raise ValidationError("O pedido precisa estar pago antes da entrega.")

        if status == Order.STATUS_CANCELED and order.status == Order.STATUS_CONFIRMED:
            _restore_ingredients_from_order(order=order, user=user)

        now = timezone.now()
        order.status = status
        order.updated_by = user
        update_fields = {"status", "updated_by"}
        if status == Order.STATUS_IN_PREPARATION and not order.preparation_started_at:
            order.preparation_started_at = now
            update_fields.add("preparation_started_at")
        if status == Order.STATUS_READY:
            if not order.preparation_started_at:
                order.preparation_started_at = now
                update_fields.add("preparation_started_at")
            order.ready_at = now
            update_fields.add("ready_at")
        if status == Order.STATUS_DELIVERED:
            if not order.preparation_started_at:
                order.preparation_started_at = now
                update_fields.add("preparation_started_at")
            if not order.ready_at:
                order.ready_at = now
                update_fields.add("ready_at")
            order.delivered_at = now
            update_fields.add("delivered_at")
        order.save(update_fields=list(update_fields))

        if status in {Order.STATUS_DELIVERED, Order.STATUS_CANCELED} and order.table_id:
            _release_table_if_no_pending_orders(order=order)
    return order


def _release_table_if_no_pending_orders(*, order):
    has_pending = Order.objects.filter(
        business=order.business,
        table=order.table,
        status__in=[
            Order.STATUS_CONFIRMED,
            Order.STATUS_IN_PREPARATION,
            Order.STATUS_READY,
        ],
    ).exclude(id=order.id).exists()
    if not has_pending:
        RestaurantTable.objects.filter(id=order.table_id).update(
            status=RestaurantTable.STATUS_FREE,
            reserved_for="",
            reserved_until=None,
        )


def _restore_ingredients_from_order(*, order, user):
    order_items = list(
        order.items.select_related("menu_item").prefetch_related("extras__extra")
    )
    if not order_items:
        return

    recipe_menu_item_ids = [
        row.menu_item_id
        for row in order_items
        if row.menu_item_id and row.menu_item and row.menu_item.item_type == MenuItem.TYPE_FOOD
    ]
    recipes_map = {}
    if recipe_menu_item_ids:
        for recipe in MenuItemRecipe.objects.select_related("ingredient").filter(
            menu_item_id__in=recipe_menu_item_ids
        ):
            recipes_map.setdefault(recipe.menu_item_id, []).append(recipe)

    required = {}
    for row in order_items:
        menu_item = row.menu_item
        if not menu_item:
            continue
        quantity = Decimal(row.quantity)
        if menu_item.item_type == MenuItem.TYPE_FOOD:
            for recipe in recipes_map.get(menu_item.id, []):
                required[recipe.ingredient_id] = required.get(
                    recipe.ingredient_id, Decimal("0")
                ) + (recipe.quantity * quantity)
        elif menu_item.ingredient_id:
            required[menu_item.ingredient_id] = required.get(
                menu_item.ingredient_id, Decimal("0")
            ) + quantity
        for order_extra in row.extras.all():
            extra = order_extra.extra
            if extra and extra.ingredient_id:
                required[extra.ingredient_id] = required.get(
                    extra.ingredient_id, Decimal("0")
                ) + Decimal(order_extra.quantity)

    if not required:
        return

    ingredients = FoodIngredient.objects.select_for_update().filter(
        business=order.business,
        id__in=required.keys(),
        is_active=True,
        stock_control=True,
    )
    for ingredient in ingredients:
        quantity = required.get(ingredient.id, Decimal("0"))
        if quantity <= 0:
            continue
        ingredient.stock_qty = ingredient.stock_qty + quantity
        ingredient.save(update_fields=["stock_qty"])
        IngredientMovement.objects.create(
            business=order.business,
            ingredient=ingredient,
            movement_type=IngredientMovement.MOVEMENT_CANCEL,
            quantity=quantity,
            unit=ingredient.unit,
            reference_type="order_cancel",
            reference_id=order.id,
            notes=f"Cancelamento pedido {order.code}",
            created_by=user,
        )


def _assert_ingredients_available(*, business, items):
    required = _build_required_ingredient_quantities(items=items)
    if not required:
        return
    ingredients = FoodIngredient.objects.filter(
        business=business,
        id__in=required.keys(),
        is_active=True,
        stock_control=True,
    )
    for ingredient in ingredients:
        needed = required.get(ingredient.id, Decimal("0"))
        if needed <= 0:
            continue
        if not business.allow_negative_stock and ingredient.stock_qty < needed:
            raise ValidationError(
                f"Ingredientes insuficientes para {ingredient.name}."
            )


def _build_required_ingredient_quantities(*, items):
    required = {}
    for item in items:
        menu_item = item["menu_item"]
        qty = Decimal(item["quantity"])
        if menu_item.item_type == MenuItem.TYPE_FOOD:
            for recipe in MenuItemRecipe.objects.select_related("ingredient").filter(
                menu_item=menu_item
            ):
                needed = recipe.quantity * qty
                required[recipe.ingredient_id] = required.get(recipe.ingredient_id, Decimal("0")) + needed
        elif menu_item.ingredient_id:
            required[menu_item.ingredient_id] = required.get(menu_item.ingredient_id, Decimal("0")) + qty
        for extra in [item.get("variant")] + list(item.get("extras") or []):
            if extra and extra.ingredient_id:
                required[extra.ingredient_id] = required.get(
                    extra.ingredient_id, Decimal("0")
                ) + qty
    return required


def _deduct_ingredients(*, business, items, user, order):
    required = _build_required_ingredient_quantities(items=items)
    if not required:
        return
    ingredients = FoodIngredient.objects.select_for_update().filter(
        business=business,
        id__in=required.keys(),
        is_active=True,
        stock_control=True,
    )
    for ingredient in ingredients:
        needed = required.get(ingredient.id, Decimal("0"))
        if needed <= 0:
            continue
        if not business.allow_negative_stock and ingredient.stock_qty < needed:
            raise ValidationError(
                f"Ingredientes insuficientes para {ingredient.name}."
            )
        ingredient.stock_qty = ingredient.stock_qty - needed
        ingredient.save(update_fields=["stock_qty"])
        IngredientMovement.objects.create(
            business=business,
            ingredient=ingredient,
            movement_type=IngredientMovement.MOVEMENT_OUT,
            quantity=needed,
            unit=ingredient.unit,
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
            purchased_quantity = item.get("purchased_quantity")
            conversion_factor = item.get("conversion_factor") or Decimal("1")
            quantity = item.get("quantity")
            if quantity is None and purchased_quantity is not None:
                quantity = purchased_quantity * conversion_factor
            if not ingredient or not quantity or quantity <= 0:
                continue
            total_cost = item.get("total_cost")
            unit_cost = item.get("unit_cost")
            if total_cost is not None and quantity > 0:
                unit_cost = total_cost / quantity
            IngredientStockEntryItem.objects.create(
                entry=entry,
                ingredient=ingredient,
                purchased_quantity=purchased_quantity,
                purchase_unit=item.get("purchase_unit", ""),
                conversion_factor=conversion_factor,
                quantity=quantity,
                total_cost=total_cost,
                unit_cost=unit_cost,
                expiry_date=item.get("expiry_date"),
                batch_number=item.get("batch_number", ""),
            )
            if ingredient.stock_control:
                ingredient.stock_qty = ingredient.stock_qty + quantity
                if unit_cost is not None:
                    ingredient.cost_price = unit_cost
                ingredient.save(update_fields=["stock_qty", "cost_price"])
                conversion_note = ""
                if purchased_quantity and item.get("purchase_unit"):
                    conversion_note = (
                        f" - {purchased_quantity} {item.get('purchase_unit')} x "
                        f"{conversion_factor} = {quantity} {ingredient.unit}"
                    )
                IngredientMovement.objects.create(
                    business=business,
                    ingredient=ingredient,
                    movement_type=IngredientMovement.MOVEMENT_IN,
                    quantity=quantity,
                    unit=ingredient.unit,
                    reference_type="ingredient_entry",
                    reference_id=entry.id,
                    notes=f"Entrada {entry.id}{conversion_note}",
                    created_by=user,
                )
        return entry


def adjust_ingredient_stock(*, business, ingredient, user, adjustment_type, quantity, notes=""):
    if not ingredient.stock_control:
        raise ValidationError("Este insumo nao controla stock.")
    if adjustment_type not in {
        IngredientMovement.MOVEMENT_ADJUST,
        IngredientMovement.MOVEMENT_WASTE,
    }:
        raise ValidationError("Tipo de ajuste invalido.")
    if quantity == 0:
        raise ValidationError("Informe uma quantidade diferente de zero.")
    with transaction.atomic():
        ingredient = FoodIngredient.objects.select_for_update().get(
            pk=ingredient.pk,
            business=business,
        )
        if adjustment_type == IngredientMovement.MOVEMENT_WASTE:
            if quantity <= 0:
                raise ValidationError("Informe uma quantidade positiva para perda.")
            stock_delta = -quantity
            movement_quantity = quantity
        else:
            stock_delta = quantity
            movement_quantity = quantity

        ingredient.stock_qty = ingredient.stock_qty + stock_delta
        if ingredient.stock_qty < 0 and not business.allow_negative_stock:
            raise ValidationError("Stock insuficiente para este ajuste.")
        ingredient.save(update_fields=["stock_qty"])
        IngredientMovement.objects.create(
            business=business,
            ingredient=ingredient,
            movement_type=adjustment_type,
            quantity=movement_quantity,
            unit=ingredient.unit,
            reference_type="manual",
            notes=notes or "Ajuste manual",
            created_by=user,
        )
        return ingredient
