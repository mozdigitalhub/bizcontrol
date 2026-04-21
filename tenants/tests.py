from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from billing.models import Invoice
from sales.models import Sale
from tenants.models import Business, BusinessMembership


class MultiTenantIsolationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user_a = User.objects.create_user(username="usera", password="pass")
        self.user_b = User.objects.create_user(username="userb", password="pass")
        self.business_a = Business.objects.create(name="Negocio A", slug="negocio-a")
        self.business_b = Business.objects.create(name="Negocio B", slug="negocio-b")
        BusinessMembership.objects.create(
            business=self.business_a, user=self.user_a, role=BusinessMembership.ROLE_OWNER
        )
        BusinessMembership.objects.create(
            business=self.business_b, user=self.user_b, role=BusinessMembership.ROLE_OWNER
        )
        owner_group, _ = Group.objects.get_or_create(name="group_owner")
        owner_group.permissions.set(Permission.objects.all())
        self.user_a.groups.add(owner_group)
        self.user_b.groups.add(owner_group)

        self.sale_b = Sale.objects.create(
            business=self.business_b,
            status=Sale.STATUS_CONFIRMED,
            subtotal=100,
            tax_total=16,
            total=116,
        )
        self.invoice_b = Invoice.objects.create(
            business=self.business_b,
            invoice_number=1,
            status=Invoice.STATUS_ISSUED,
            subtotal=100,
            tax_total=16,
            total=116,
        )

    def _login_with_business(self, user, business):
        self.client.force_login(user)
        session = self.client.session
        session["business_id"] = business.id
        session.save()

    def test_user_cannot_access_other_business_sale(self):
        self._login_with_business(self.user_a, self.business_a)
        response = self.client.get(reverse("sales:detail", args=[self.sale_b.id]))
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_access_other_business_invoice(self):
        self._login_with_business(self.user_a, self.business_a)
        response = self.client.get(reverse("billing:invoice_detail", args=[self.invoice_b.id]))
        self.assertEqual(response.status_code, 404)


class FoodOperationRoutingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="chef", password="pass")
        self.business = Business.objects.create(
            name="Restaurante",
            slug="restaurante-route",
            business_type=Business.BUSINESS_RESTAURANT,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.user,
            role=BusinessMembership.ROLE_OWNER,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["business_id"] = self.business.id
        session.save()

    def test_food_business_redirects_from_non_food_paths(self):
        response = self.client.get(reverse("sales:list"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse("food:order_list")))
