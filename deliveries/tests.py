from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from billing.services import generate_invoice, register_invoice_payment
from catalog.models import Product
from deliveries.services import register_delivery
from inventory.models import StockMovement
from sales.models import Sale
from sales.services import add_item_to_sale, confirm_sale
from tenants.models import Business, BusinessMembership


class DeliveryRulesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="owner", password="pass")
        self.business = Business.objects.create(name="Loja Entregas", slug="loja-entregas")
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.product = Product.objects.create(
            business=self.business,
            name="Produto X",
            sale_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
        )
        StockMovement.objects.create(
            business=self.business,
            product=self.product,
            movement_type=StockMovement.MOVEMENT_IN,
            quantity=10,
        )

    def _create_confirmed_sale(self):
        sale = Sale.objects.create(
            business=self.business,
            created_by=self.user,
            payment_method=Sale.METHOD_CASH,
        )
        add_item_to_sale(
            sale=sale,
            product=self.product,
            quantity=2,
            unit_price=self.product.sale_price,
            user=self.user,
        )
        confirm_sale(sale_id=sale.id, business=self.business, user=self.user)
        sale.refresh_from_db()
        return sale

    def test_delivery_requires_invoice(self):
        sale = self._create_confirmed_sale()
        item = sale.items.first()
        with self.assertRaises(ValidationError):
            register_delivery(
                sale_id=sale.id,
                business=self.business,
                user=self.user,
                items_map={str(item.id): "1"},
            )

    def test_delivery_requires_payment_for_cash_sales(self):
        sale = self._create_confirmed_sale()
        item = sale.items.first()
        invoice = generate_invoice(sale_id=sale.id, business=self.business, user=self.user)
        with self.assertRaises(ValidationError):
            register_delivery(
                sale_id=sale.id,
                business=self.business,
                user=self.user,
                items_map={str(item.id): "1"},
            )
        register_invoice_payment(
            invoice_id=invoice.id,
            business=self.business,
            amount=invoice.total,
            method=Sale.METHOD_CASH,
            user=self.user,
        )
        guide = register_delivery(
            sale_id=sale.id,
            business=self.business,
            user=self.user,
            items_map={str(item.id): "1"},
        )
        self.assertIsNotNone(guide)
