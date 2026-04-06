from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Product
from finance.models import CashMovement
from food.models import Order
from food.services import create_order
from tenants.models import Business, BusinessMembership


class FoodOrderTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="cook", password="pass")
        self.business = Business.objects.create(name="Burger", slug="burger", business_type=Business.BUSINESS_BURGER)
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.product = Product.objects.create(
            business=self.business,
            name="Hamburguer",
            sale_price=Decimal("250.00"),
            cost_price=Decimal("100.00"),
        )

    def test_create_order_creates_cash_movement(self):
        order = create_order(
            business=self.business,
            user=self.user,
            order_data={"channel": Order.CHANNEL_DINE_IN, "payment_method": CashMovement.METHOD_CASH},
            items=[{"product": self.product, "quantity": 2, "unit_price": self.product.sale_price}],
        )
        self.assertIsNotNone(order.code)
        movement = CashMovement.objects.filter(
            business=self.business, reference_type="order", reference_id=order.id
        ).first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.amount, order.total)
