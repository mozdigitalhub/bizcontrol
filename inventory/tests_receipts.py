from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product
from finance.models import CashMovement, PaymentMethod, Supplier
from finance.services import ensure_default_payment_methods
from inventory.models import GoodsReceipt, ProductCostHistory, ProductSalePriceHistory, StockMovement
from tenants.models import Business


class GoodsReceiptTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="StrongPass123!",
        )
        self.business = Business.objects.create(
            name="Ferragem Central",
            slug="ferragem-central",
            business_type=Business.BUSINESS_HARDWARE,
            nuit="123456789",
        )
        ensure_default_payment_methods(self.business)
        self.payment_method = PaymentMethod.objects.filter(business=self.business).first()
        self.supplier = Supplier.objects.create(
            business=self.business,
            name="Fornecedor A",
            is_active=True,
        )
        self.product1 = Product.objects.create(
            business=self.business,
            name="Cimento Nacional 32",
            sale_price=Decimal("60"),
            cost_price=Decimal("40"),
        )
        self.product2 = Product.objects.create(
            business=self.business,
            name="Ferro 8mm",
            sale_price=Decimal("40"),
            cost_price=Decimal("30"),
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["business_id"] = self.business.id
        session.save()

    def test_receipt_create_with_multiple_items(self):
        payload = {
            "supplier": str(self.supplier.id),
            "document_number": "G-2026-01",
            "document_date": "2026-01-12",
            "notes": "Rececao normal",
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": str(self.product1.id),
            "items-0-quantity": "10",
            "items-0-unit_cost": "50",
            "items-0-sale_price": "70",
            "items-1-product": str(self.product2.id),
            "items-1-quantity": "5",
            "items-1-unit_cost": "",
            "items-1-sale_price": "40",
        }
        response = self.client.post(reverse("inventory:receipt_create"), payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GoodsReceipt.objects.count(), 1)
        self.assertEqual(StockMovement.objects.count(), 2)
        self.assertEqual(
            StockMovement.objects.filter(reference_type="goods_receipt").count(), 2
        )
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.cost_price, Decimal("50"))
        self.assertEqual(self.product1.sale_price, Decimal("70"))
        self.assertEqual(self.product2.sale_price, Decimal("40"))
        self.assertEqual(ProductCostHistory.objects.count(), 1)
        self.assertEqual(ProductSalePriceHistory.objects.count(), 1)

    def test_receipt_allows_optional_cost(self):
        payload = {
            "supplier": str(self.supplier.id),
            "document_number": "G-2026-02",
            "document_date": "2026-01-12",
            "notes": "",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": str(self.product2.id),
            "items-0-quantity": "2",
            "items-0-unit_cost": "",
            "items-0-sale_price": "42",
        }
        response = self.client.post(reverse("inventory:receipt_create"), payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GoodsReceipt.objects.count(), 1)
        self.assertEqual(ProductCostHistory.objects.count(), 0)

    def test_receipt_create_with_cash_movement(self):
        payload = {
            "supplier": str(self.supplier.id),
            "document_number": "G-2026-03",
            "document_date": "2026-01-12",
            "notes": "Rececao com caixa",
            "cash_movement": "on",
            "payment_method": str(self.payment_method.id),
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": str(self.product1.id),
            "items-0-quantity": "10",
            "items-0-unit_cost": "50",
            "items-0-sale_price": "70",
            "items-1-product": str(self.product2.id),
            "items-1-quantity": "5",
            "items-1-unit_cost": "20",
            "items-1-sale_price": "40",
        }
        response = self.client.post(reverse("inventory:receipt_create"), payload)
        self.assertEqual(response.status_code, 302)
        receipt = GoodsReceipt.objects.first()
        self.assertIsNotNone(receipt.cash_movement)
        self.assertEqual(CashMovement.objects.count(), 1)
        movement = CashMovement.objects.first()
        expected_total = (Decimal("10") * Decimal("50")) + (Decimal("5") * Decimal("20"))
        self.assertEqual(movement.amount, expected_total)
        self.assertEqual(movement.movement_type, CashMovement.MOVEMENT_OUT)

    def test_receipt_cash_movement_requires_payment_method(self):
        payload = {
            "supplier": str(self.supplier.id),
            "document_number": "G-2026-04",
            "document_date": "2026-01-12",
            "cash_movement": "on",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": str(self.product1.id),
            "items-0-quantity": "4",
            "items-0-unit_cost": "45",
            "items-0-sale_price": "70",
        }
        response = self.client.post(reverse("inventory:receipt_create"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(GoodsReceipt.objects.count(), 0)
        self.assertContains(response, "Selecione o metodo de pagamento")

    def test_receipt_cash_movement_requires_unit_cost(self):
        payload = {
            "supplier": str(self.supplier.id),
            "document_number": "G-2026-05",
            "document_date": "2026-01-12",
            "cash_movement": "on",
            "payment_method": str(self.payment_method.id),
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": str(self.product1.id),
            "items-0-quantity": "4",
            "items-0-unit_cost": "",
            "items-0-sale_price": "70",
        }
        response = self.client.post(reverse("inventory:receipt_create"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(GoodsReceipt.objects.count(), 0)
        self.assertContains(response, "Informe o custo de aquisicao")
