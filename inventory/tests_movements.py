from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product
from deliveries.models import DeliveryGuide
from inventory.models import StockMovement
from sales.models import Sale
from tenants.models import Business, BusinessMembership


class ProductMovementsReferenceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="StrongPass123!",
        )
        self.business = Business.objects.create(
            name="Ferragem Teste",
            slug="ferragem-teste",
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.user,
            role=BusinessMembership.ROLE_OWNER,
        )
        self.product = Product.objects.create(
            business=self.business,
            name="Cimento 32",
            sale_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
        )
        self.sale = Sale.objects.create(
            business=self.business,
            status=Sale.STATUS_CONFIRMED,
        )
        self.guide = DeliveryGuide.objects.create(
            business=self.business,
            sale=self.sale,
            customer=self.sale.customer,
            code="G-260114-1-001",
            guide_number=1,
            origin_type=DeliveryGuide.ORIGIN_SALE,
        )
        StockMovement.objects.create(
            business=self.business,
            product=self.product,
            movement_type=StockMovement.MOVEMENT_OUT,
            quantity=1,
            reference_type="delivery_guide",
            reference_id=self.guide.id,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["business_id"] = self.business.id
        session.save()

    def test_product_movements_reference_uses_guide_code(self):
        response = self.client.get(
            reverse("inventory:product_movements", args=[self.product.id])
        )
        self.assertEqual(response.status_code, 200)
        movements = response.context["movements"]
        self.assertTrue(movements)
        self.assertEqual(movements[0].reference_label, self.guide.code)
