from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from catalog.models import Product
from customers.models import Customer
from inventory.models import StockMovement
from inventory.services import get_product_stock
from receivables.models import Receivable
from receivables.services import register_payment
from sales.models import Sale
from sales.services import (
    add_item_to_sale,
    calculate_line_totals,
    cancel_sale,
    confirm_sale,
)
from deliveries.services import create_delivery_for_sale
from deliveries.models import DeliveryGuide, DeliveryGuideItem
from tenants.models import Business, BusinessMembership


class SaleStockTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="seller", password="pass")
        self.business = Business.objects.create(name="Loja", slug="loja")
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.product = Product.objects.create(
            business=self.business,
            name="Produto A",
            sale_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
        )
        StockMovement.objects.create(
            business=self.business,
            product=self.product,
            movement_type=StockMovement.MOVEMENT_IN,
            quantity=10,
        )

    def _create_sale_with_item(self, quantity):
        sale = Sale.objects.create(
            business=self.business,
            created_by=self.user,
            payment_method=Sale.METHOD_CASH,
        )
        add_item_to_sale(
            sale=sale,
            product=self.product,
            quantity=int(quantity),
            unit_price=self.product.sale_price,
            user=self.user,
        )
        return sale

    def test_confirm_sale_creates_reserve_movement(self):
        sale = self._create_sale_with_item("2")
        confirm_sale(sale_id=sale.id, business=self.business, user=self.user)
        current = get_product_stock(self.business, self.product)
        self.assertEqual(current, 10)
        reserve_movements = StockMovement.objects.filter(
            business=self.business,
            product=self.product,
            movement_type=StockMovement.MOVEMENT_RESERVE,
            reference_type="sale_reserve",
            reference_id=sale.id,
        )
        self.assertEqual(reserve_movements.count(), 1)
        self.assertEqual(reserve_movements.first().quantity, 2)

    def test_cancel_sale_restores_stock(self):
        sale = self._create_sale_with_item("2")
        confirm_sale(sale_id=sale.id, business=self.business, user=self.user)
        create_delivery_for_sale(sale=sale, user=self.user)
        cancel_sale(
            sale_id=sale.id,
            business=self.business,
            user=self.user,
            return_type=Sale.RETURN_TOTAL,
        )
        current = get_product_stock(self.business, self.product)
        self.assertEqual(current, 10)
        sale.refresh_from_db()
        item = sale.items.first()
        self.assertEqual(sale.total, Decimal("0"))
        self.assertEqual(item.returned_quantity, item.quantity)

    def test_manual_stock_mode_does_not_create_movements(self):
        manual_product = Product.objects.create(
            business=self.business,
            name="Servico",
            sale_price=Decimal("50.00"),
            cost_price=Decimal("0.00"),
            stock_control_mode=Product.STOCK_MANUAL,
        )
        sale = Sale.objects.create(business=self.business, created_by=self.user)
        add_item_to_sale(
            sale=sale,
            product=manual_product,
            quantity=1,
            unit_price=manual_product.sale_price,
            user=self.user,
        )
        sale.payment_method = Sale.METHOD_CASH
        sale.save(update_fields=["payment_method"])
        confirm_sale(sale_id=sale.id, business=self.business, user=self.user)
        manual_stock = get_product_stock(self.business, manual_product)
        self.assertEqual(manual_stock, 0)

    def test_cancel_sale_no_return_keeps_stock_reduced(self):
        sale = self._create_sale_with_item("2")
        confirm_sale(sale_id=sale.id, business=self.business, user=self.user)
        guide = DeliveryGuide.objects.create(
            business=self.business,
            sale=sale,
            customer=sale.customer,
            guide_number=1,
            origin_type=DeliveryGuide.ORIGIN_SALE,
            status=DeliveryGuide.STATUS_PARTIAL,
        )
        DeliveryGuideItem.objects.create(
            guide=guide,
            sale_item=sale.items.first(),
            product=self.product,
            quantity=1,
        )
        StockMovement.objects.create(
            business=self.business,
            product=self.product,
            movement_type=StockMovement.MOVEMENT_OUT,
            quantity=1,
            reference_type="delivery_guide",
            reference_id=guide.id,
        )
        previous_total = sale.total
        cancel_sale(
            sale_id=sale.id,
            business=self.business,
            user=self.user,
            return_type=Sale.RETURN_NONE,
        )
        current = get_product_stock(self.business, self.product)
        self.assertEqual(current, 9)
        sale.refresh_from_db()
        self.assertEqual(sale.total, previous_total)

    def test_cancel_sale_partial_return(self):
        sale = self._create_sale_with_item("2")
        confirm_sale(sale_id=sale.id, business=self.business, user=self.user)
        create_delivery_for_sale(sale=sale, user=self.user)
        item = sale.items.first()
        previous_total = sale.total
        cancel_sale(
            sale_id=sale.id,
            business=self.business,
            user=self.user,
            return_type=Sale.RETURN_PARTIAL,
            return_items={item.id: 1},
        )
        current = get_product_stock(self.business, self.product)
        self.assertEqual(current, 9)
        sale.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(item.returned_quantity, 1)
        self.assertLess(sale.total, previous_total)
        self.assertEqual(sale.refunds.count(), 1)

    def test_cancel_sale_blocked_when_delivery_completed(self):
        sale = self._create_sale_with_item("2")
        confirm_sale(sale_id=sale.id, business=self.business, user=self.user)
        item = sale.items.first()
        guide = DeliveryGuide.objects.create(
            business=self.business,
            sale=sale,
            customer=sale.customer,
            guide_number=1,
            origin_type=DeliveryGuide.ORIGIN_SALE,
            status=DeliveryGuide.STATUS_DELIVERED,
        )
        DeliveryGuideItem.objects.create(
            guide=guide,
            sale_item=item,
            product=item.product,
            quantity=item.quantity,
        )
        with self.assertRaises(ValidationError):
            cancel_sale(
                sale_id=sale.id,
                business=self.business,
                user=self.user,
                return_type=Sale.RETURN_TOTAL,
            )


class SaleCreditTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="cashier", password="pass")
        self.business = Business.objects.create(name="Loja", slug="loja-2")
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.customer = Customer.objects.create(
            business=self.business, name="Cliente A"
        )
        self.product = Product.objects.create(
            business=self.business,
            name="Produto B",
            sale_price=Decimal("116.00"),
            cost_price=Decimal("60.00"),
        )
        StockMovement.objects.create(
            business=self.business,
            product=self.product,
            movement_type=StockMovement.MOVEMENT_IN,
            quantity=10,
        )

    def test_credit_sale_creates_receivable_and_payment(self):
        sale = Sale.objects.create(
            business=self.business,
            customer=self.customer,
            is_credit=True,
            payment_due_date=timezone.now().date(),
            created_by=self.user,
        )
        add_item_to_sale(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=self.product.sale_price,
            user=self.user,
        )
        confirm_sale(sale_id=sale.id, business=self.business, user=self.user)
        receivable = Receivable.objects.get(sale=sale)
        self.assertEqual(receivable.original_amount, sale.total)

        register_payment(
            receivable_id=receivable.id,
            business=self.business,
            amount=Decimal("50.00"),
            method="cash",
            user=self.user,
        )
        receivable.refresh_from_db()
        self.assertEqual(receivable.total_paid, Decimal("50.00"))
        self.assertEqual(receivable.status, Receivable.STATUS_OPEN)
        self.assertEqual(receivable.balance, sale.total - Decimal("50.00"))

    def test_credit_sale_warns_when_open_receivable(self):
        Receivable.objects.create(
            business=self.business,
            customer=self.customer,
            original_amount=Decimal("200.00"),
            total_paid=Decimal("0"),
            status=Receivable.STATUS_OPEN,
        )
        sale = Sale.objects.create(
            business=self.business,
            customer=self.customer,
            is_credit=True,
            payment_due_date=timezone.now().date(),
            created_by=self.user,
        )
        add_item_to_sale(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=self.product.sale_price,
            user=self.user,
        )
        with self.assertRaises(ValidationError):
            confirm_sale(sale_id=sale.id, business=self.business, user=self.user)
        confirm_sale(
            sale_id=sale.id,
            business=self.business,
            user=self.user,
            confirm_open_debt=True,
        )


class SaleValidationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="validator", password="pass")
        self.business = Business.objects.create(name="Loja V", slug="loja-v")
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.product = Product.objects.create(
            business=self.business,
            name="Produto V",
            sale_price=Decimal("100.00"),
            cost_price=Decimal("50.00"),
        )
        StockMovement.objects.create(
            business=self.business,
            product=self.product,
            movement_type=StockMovement.MOVEMENT_IN,
            quantity=10,
        )

    def test_confirm_requires_payment_method(self):
        sale = Sale.objects.create(business=self.business, created_by=self.user)
        add_item_to_sale(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=self.product.sale_price,
            user=self.user,
        )
        with self.assertRaises(ValidationError):
            confirm_sale(sale_id=sale.id, business=self.business, user=self.user)

    def test_confirm_requires_due_date_for_credit(self):
        sale = Sale.objects.create(
            business=self.business,
            customer=Customer.objects.create(
                business=self.business, name="Cliente V"
            ),
            is_credit=True,
            created_by=self.user,
        )
        sale.payment_method = Sale.METHOD_CASH
        sale.save(update_fields=["payment_method"])
        add_item_to_sale(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=self.product.sale_price,
            user=self.user,
        )
        with self.assertRaises(ValidationError):
            confirm_sale(sale_id=sale.id, business=self.business, user=self.user)


class VatCalculationTests(TestCase):
    def test_prices_include_vat(self):
        business = Business.objects.create(
            name="Loja IVA", slug="loja-iva", vat_enabled=True, vat_rate=Decimal("0.16")
        )
        business.prices_include_vat = True
        subtotal, tax, total = calculate_line_totals(
            business=business, unit_price=Decimal("116.00"), quantity=Decimal("1")
        )
        self.assertAlmostEqual(subtotal, Decimal("100.00"), places=2)
        self.assertAlmostEqual(tax, Decimal("16.00"), places=2)
        self.assertAlmostEqual(total, Decimal("116.00"), places=2)

    def test_prices_exclude_vat(self):
        business = Business.objects.create(
            name="Loja IVA 2", slug="loja-iva-2", vat_enabled=True, vat_rate=Decimal("0.16")
        )
        business.prices_include_vat = False
        subtotal, tax, total = calculate_line_totals(
            business=business, unit_price=Decimal("100.00"), quantity=Decimal("1")
        )
        self.assertAlmostEqual(subtotal, Decimal("100.00"), places=2)
        self.assertAlmostEqual(tax, Decimal("16.00"), places=2)
        self.assertAlmostEqual(total, Decimal("116.00"), places=2)
