from io import BytesIO
from decimal import Decimal

import openpyxl
from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Category, Product
from inventory.excel_import import ExcelImportService
from inventory.models import StockMovement
from tenants.models import Business, BusinessMembership


class StockExcelImportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="importer", password="pass")
        self.business = Business.objects.create(name="Ferragem", slug="ferragem", business_type=Business.BUSINESS_HARDWARE)
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )

    def _build_workbook(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Cimento"
        ws.append([
            "Descrição do Item",
            "Un.",
            "PREÇO DE COMPRA",
            "PREÇO DE VENDA",
            "ENTRADA",
        ])
        ws.append(["Cimento 32", "saco", "250,00", "450,00", "10"])
        ws.append(["Cimento 42", "saco", "", "500", "5"])
        return wb

    def test_import_creates_categories_and_products(self):
        wb = self._build_workbook()
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        service = ExcelImportService(business=self.business, user=self.user)
        result = service.import_workbook(buffer)
        self.assertEqual(Category.objects.filter(business=self.business).count(), 1)
        self.assertEqual(Product.objects.filter(business=self.business).count(), 2)
        self.assertEqual(result.products_created, 2)
        self.assertEqual(StockMovement.objects.filter(business=self.business).count(), 2)

    def test_import_updates_existing_product(self):
        category = Category.objects.create(business=self.business, name="Cimento")
        product = Product.objects.create(
            business=self.business,
            category=category,
            name="Cimento 32",
            sale_price=Decimal("400.00"),
            cost_price=Decimal("200.00"),
        )
        wb = self._build_workbook()
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        service = ExcelImportService(business=self.business, user=self.user)
        result = service.import_workbook(buffer)
        product.refresh_from_db()
        self.assertEqual(product.sale_price, Decimal("450.00"))
        self.assertEqual(result.products_updated, 1)

    def test_missing_required_fields_reported(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Ferramentas"
        ws.append([
            "Descrição do Item",
            "Un.",
            "PREÇO DE COMPRA",
            "PREÇO DE VENDA",
            "ENTRADA",
        ])
        ws.append(["", "un", "", "", ""])
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        service = ExcelImportService(business=self.business, user=self.user)
        result = service.import_workbook(buffer)
        self.assertEqual(result.rows_failed, 1)
        self.assertTrue(result.errors)
