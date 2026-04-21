from decimal import Decimal

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.test import TestCase

from finance.models import CashMovement
from food.models import (
    FoodIngredient,
    IngredientMovement,
    MenuItem,
    MenuItemRecipe,
    Order,
    RestaurantTable,
)
from food.services import create_order, update_order_status
from tenants.models import Business, BusinessMembership


class FoodOrderTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="cook", password="pass")
        self.business = Business.objects.create(name="Burger", slug="burger", business_type=Business.BUSINESS_BURGER)
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.menu_item = MenuItem.objects.create(
            business=self.business,
            name="Hamburguer",
            selling_price=Decimal("250.00"),
        )

    def test_create_order_creates_cash_movement(self):
        order = create_order(
            business=self.business,
            user=self.user,
            order_data={"channel": Order.CHANNEL_DINE_IN, "payment_method": CashMovement.METHOD_CASH},
            items=[{"menu_item": self.menu_item, "quantity": 2, "unit_price": self.menu_item.selling_price}],
        )
        self.assertIsNotNone(order.code)
        movement = CashMovement.objects.filter(
            business=self.business, reference_type="order", reference_id=order.id
        ).first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.amount, order.total)

    def test_restaurant_table_changes_status_with_order_flow(self):
        business = Business.objects.create(
            name="Restaurante",
            slug="restaurante",
            business_type=Business.BUSINESS_RESTAURANT,
        )
        BusinessMembership.objects.create(
            business=business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        table = RestaurantTable.objects.create(
            business=business,
            name="Mesa 1",
            status=RestaurantTable.STATUS_FREE,
        )
        item = MenuItem.objects.create(
            business=business,
            name="Prato do dia",
            selling_price=Decimal("300.00"),
        )
        order = create_order(
            business=business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_DINE_IN,
                "table": table,
                "payment_method": "",
            },
            items=[{"menu_item": item, "quantity": 1, "unit_price": item.selling_price}],
        )
        table.refresh_from_db()
        self.assertEqual(order.table_id, table.id)
        self.assertEqual(table.status, RestaurantTable.STATUS_OCCUPIED)
        update_order_status(order=order, status=Order.STATUS_DELIVERED, user=self.user)
        table.refresh_from_db()
        self.assertEqual(table.status, RestaurantTable.STATUS_FREE)

    def test_cancel_order_restores_ingredients_and_releases_table(self):
        business = Business.objects.create(
            name="Restaurante B",
            slug="restaurante-b",
            business_type=Business.BUSINESS_RESTAURANT,
        )
        BusinessMembership.objects.create(
            business=business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        table = RestaurantTable.objects.create(
            business=business,
            name="Mesa 2",
            status=RestaurantTable.STATUS_FREE,
        )
        ingredient = FoodIngredient.objects.create(
            business=business,
            name="Queijo",
            stock_qty=Decimal("10.000"),
        )
        menu_item = MenuItem.objects.create(
            business=business,
            name="Prato especial",
            item_type=MenuItem.TYPE_FOOD,
            selling_price=Decimal("450.00"),
        )
        MenuItemRecipe.objects.create(
            menu_item=menu_item,
            ingredient=ingredient,
            quantity=Decimal("2.000"),
            unit="un",
        )

        order = create_order(
            business=business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_DINE_IN,
                "table": table,
                "payment_method": "",
            },
            items=[{"menu_item": menu_item, "quantity": 1, "unit_price": menu_item.selling_price}],
        )
        ingredient.refresh_from_db()
        self.assertEqual(ingredient.stock_qty, Decimal("8.000"))

        update_order_status(order=order, status=Order.STATUS_CANCELED, user=self.user)
        ingredient.refresh_from_db()
        table.refresh_from_db()
        self.assertEqual(ingredient.stock_qty, Decimal("10.000"))
        self.assertEqual(table.status, RestaurantTable.STATUS_FREE)
        movement = IngredientMovement.objects.filter(
            business=business,
            ingredient=ingredient,
            movement_type=IngredientMovement.MOVEMENT_IN,
            reference_type="order_cancel",
            reference_id=order.id,
        ).first()
        self.assertIsNotNone(movement)

    def test_cannot_change_status_after_cancel(self):
        order = create_order(
            business=self.business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_DINE_IN,
                "payment_method": CashMovement.METHOD_CASH,
            },
            items=[{"menu_item": self.menu_item, "quantity": 1, "unit_price": self.menu_item.selling_price}],
        )
        update_order_status(order=order, status=Order.STATUS_CANCELED, user=self.user)
        with self.assertRaises(ValidationError):
            update_order_status(order=order, status=Order.STATUS_DELIVERED, user=self.user)
