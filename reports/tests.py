from django.test import TestCase

from catalog.models import Product
from reports.services import get_product_sales_history
from sales.models import Sale, SaleItem
from tenants.models import Business


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
