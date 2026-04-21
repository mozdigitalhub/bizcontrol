from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, ProductVariant
from tenants.models import Business, BusinessMembership


class ProductVariantTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="owner", password="pass1234")
        self.business = Business.objects.create(
            name="Loja de roupa",
            slug="loja-roupa",
            business_type=Business.BUSINESS_CLOTHING,
        )
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.product = Product.objects.create(
            business=self.business,
            name="Camiseta",
            sale_price=Decimal("120.00"),
            cost_price=Decimal("50.00"),
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="catalog",
                codename="view_productvariant",
            )
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["business_id"] = self.business.id
        session.save()

    def test_variant_list_is_scoped_to_current_business_product(self):
        other_business = Business.objects.create(
            name="Outra loja",
            slug="outra-loja",
            business_type=Business.BUSINESS_CLOTHING,
        )
        other_product = Product.objects.create(
            business=other_business,
            name="Calca",
            sale_price=Decimal("200.00"),
            cost_price=Decimal("80.00"),
        )
        ProductVariant.objects.create(
            product=self.product,
            name="Slim",
            size="M",
            color="Azul",
            sale_price=Decimal("130.00"),
        )
        ProductVariant.objects.create(
            product=other_product,
            name="Wide",
            size="L",
            color="Preto",
            sale_price=Decimal("210.00"),
        )

        response = self.client.get(reverse("catalog:variant_list", args=[self.product.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Slim")
        self.assertNotContains(response, "Wide")
