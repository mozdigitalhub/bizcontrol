from django.test import TestCase

from catalog.models import Product
from inventory.models import StockMovement
from inventory.services import get_stock_snapshot_by_product_ids
from tenants.models import Business


class InventoryStockSnapshotTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Loja", slug="loja-stock")
        self.product_a = Product.objects.create(
            business=self.business, name="Produto A", sale_price=10
        )
        self.product_b = Product.objects.create(
            business=self.business, name="Produto B", sale_price=20
        )

    def test_snapshot_returns_balances_per_product(self):
        StockMovement.objects.create(
            business=self.business,
            product=self.product_a,
            movement_type=StockMovement.MOVEMENT_IN,
            quantity=10,
        )
        StockMovement.objects.create(
            business=self.business,
            product=self.product_a,
            movement_type=StockMovement.MOVEMENT_OUT,
            quantity=3,
        )
        StockMovement.objects.create(
            business=self.business,
            product=self.product_b,
            movement_type=StockMovement.MOVEMENT_ADJUST,
            quantity=2,
        )

        snapshot = get_stock_snapshot_by_product_ids(
            self.business, [self.product_a.id, self.product_b.id]
        )

        self.assertEqual(snapshot[self.product_a.id], 7)
        self.assertEqual(snapshot[self.product_b.id], 2)
