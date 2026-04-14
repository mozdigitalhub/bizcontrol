from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from reports.services import get_product_sales_history, get_sales_series
from sales.models import Sale, SaleItem
from tenants.models import Business, BusinessMembership


class ProductSalesHistoryTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Loja", slug="loja")
        self.other_business = Business.objects.create(name="Outra", slug="outra")
        self.product_a = Product.objects.create(
            business=self.business, name="Produto A", sale_price=10
        )
        self.product_b = Product.objects.create(
            business=self.business, name="Produto B", sale_price=20
        )
        self.product_c = Product.objects.create(
            business=self.other_business, name="Produto C", sale_price=30
        )

    def test_product_sales_history_is_per_business(self):
        sale = Sale.objects.create(
            business=self.business, status=Sale.STATUS_CONFIRMED
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=5,
            returned_quantity=1,
            unit_price=10,
            line_total=50,
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product_b,
            quantity=2,
            returned_quantity=0,
            unit_price=20,
            line_total=40,
        )
        other_sale = Sale.objects.create(
            business=self.other_business, status=Sale.STATUS_CONFIRMED
        )
        SaleItem.objects.create(
            sale=other_sale,
            product=self.product_c,
            quantity=7,
            returned_quantity=0,
            unit_price=30,
            line_total=210,
        )

        results = get_product_sales_history(business=self.business)
        self.assertEqual(len(results), 2)
        totals = {row["product__name"]: row["total_qty"] for row in results}
        self.assertEqual(totals["Produto A"], 4)
        self.assertEqual(totals["Produto B"], 2)


class ReportsPermissionsTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Loja", slug="loja")
        self.user = get_user_model().objects.create_user(
            username="staff", email="staff@example.com", password="pass1234"
        )
        self.membership = BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_STAFF
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["business_id"] = self.business.id
        session.save()

    def test_reports_requires_permission(self):
        response = self.client.get(reverse("reports:overview"))
        self.assertEqual(response.status_code, 302)
        perm = Permission.objects.get(
            content_type__app_label="reports", codename="view_basic"
        )
        self.membership.extra_permissions.add(perm)
        response = self.client.get(reverse("reports:overview"))
        self.assertEqual(response.status_code, 200)

    def test_user_guide_is_available_without_report_permission(self):
        response = self.client.get(reverse("reports:user_guide"))
        self.assertEqual(response.status_code, 200)


class SalesSeriesIsolationTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Loja", slug="loja")
        self.other_business = Business.objects.create(name="Outra", slug="outra")
        self.product = Product.objects.create(
            business=self.business, name="Produto A", sale_price=10
        )
        self.other_product = Product.objects.create(
            business=self.other_business, name="Produto B", sale_price=20
        )

    def test_sales_series_is_scoped(self):
        today = timezone.localdate()
        sale = Sale.objects.create(
            business=self.business,
            status=Sale.STATUS_CONFIRMED,
            sale_date=timezone.now(),
            total=20,
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=2,
            unit_price=10,
            line_total=20,
        )
        other_sale = Sale.objects.create(
            business=self.other_business,
            status=Sale.STATUS_CONFIRMED,
            sale_date=timezone.now(),
            total=100,
        )
        SaleItem.objects.create(
            sale=other_sale,
            product=self.other_product,
            quantity=5,
            unit_price=20,
            line_total=100,
        )
        date_from = today - timedelta(days=1)
        labels, values = get_sales_series(
            business=self.business,
            date_from=date_from,
            date_to=today,
            granularity="daily",
        )
        self.assertTrue(labels)
        self.assertEqual(sum(values), 20.0)
