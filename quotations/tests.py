from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product
from customers.models import Customer
from inventory.models import StockMovement
from quotations.models import Quotation
from quotations.services import approve_quotation, update_quotation_items
from tenants.models import Business, BusinessMembership


class QuotationFlowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="owner", password="pass")
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=["is_superuser", "is_staff"])

        self.business = Business.objects.create(name="Loja A", slug="loja-a")
        self.business.vat_enabled = False
        self.business.save(update_fields=["vat_enabled"])

        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.customer = Customer.objects.create(business=self.business, name="Cliente A")
        self.product = Product.objects.create(
            business=self.business,
            name="Produto A",
            sale_price=Decimal("100.00"),
            cost_price=Decimal("50.00"),
        )
        StockMovement.objects.create(
            business=self.business,
            product=self.product,
            movement_type=StockMovement.MOVEMENT_IN,
            quantity=20,
            reference_type="test",
            reference_id=0,
        )

    def _login_with_business(self, business):
        self.client.force_login(self.user)
        session = self.client.session
        session["business_id"] = business.id
        session.save()

    def _create_quotation(self):
        quotation = Quotation.objects.create(
            business=self.business,
            customer=self.customer,
            status=Quotation.STATUS_DRAFT,
            created_by=self.user,
        )
        update_quotation_items(
            quotation=quotation,
            items_data=[
                {
                    "product": self.product,
                    "description": "",
                    "quantity": 2,
                    "unit_price": Decimal("100.00"),
                }
            ],
        )
        return quotation

    def test_create_quotation_calculates_totals(self):
        quotation = self._create_quotation()
        quotation.refresh_from_db()
        self.assertEqual(quotation.subtotal, Decimal("200.00"))
        self.assertEqual(quotation.tax_total, Decimal("0.00"))
        self.assertEqual(quotation.total, Decimal("200.00"))
        self.assertEqual(quotation.items.count(), 1)

    def test_unit_price_defaults_to_product_price(self):
        quotation = Quotation.objects.create(
            business=self.business,
            customer=self.customer,
            status=Quotation.STATUS_DRAFT,
            created_by=self.user,
        )
        update_quotation_items(
            quotation=quotation,
            items_data=[
                {
                    "product": self.product,
                    "description": "",
                    "quantity": 1,
                    "unit_price": None,
                }
            ],
        )
        quotation.refresh_from_db()
        item = quotation.items.first()
        self.assertEqual(item.unit_price, self.product.sale_price)

    def test_approve_quotation_creates_sale_and_reserve(self):
        quotation = self._create_quotation()
        approved = approve_quotation(
            quotation_id=quotation.id, business=self.business, user=self.user
        )
        approved.refresh_from_db()
        self.assertEqual(approved.status, Quotation.STATUS_APPROVED)
        self.assertIsNotNone(approved.sale_id)
        self.assertEqual(approved.sale.items.count(), 1)
        self.assertTrue(approved.sale.code)

        reserve = StockMovement.objects.filter(
            business=self.business,
            product=self.product,
            movement_type=StockMovement.MOVEMENT_RESERVE,
            reference_type="sale_reserve",
            reference_id=approved.sale_id,
        )
        self.assertEqual(reserve.count(), 1)
        self.assertEqual(reserve.first().quantity, 2)

    def test_edit_redirects_after_approval(self):
        quotation = self._create_quotation()
        quotation.status = Quotation.STATUS_APPROVED
        quotation.save(update_fields=["status"])
        self._login_with_business(self.business)
        response = self.client.get(reverse("quotations:edit", args=[quotation.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], reverse("quotations:detail", args=[quotation.id])
        )

    def test_pdf_view_returns_response(self):
        quotation = self._create_quotation()
        self._login_with_business(self.business)
        response = self.client.get(reverse("quotations:pdf_view", args=[quotation.id]))
        from quotations import views as quotation_views

        if quotation_views.HTML is None:
            self.assertEqual(response.status_code, 500)
        else:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "application/pdf")

    def test_tenant_isolation_on_detail(self):
        other_business = Business.objects.create(name="Loja B", slug="loja-b")
        other_quote = Quotation.objects.create(
            business=other_business, customer=None, created_by=self.user
        )
        self._login_with_business(self.business)
        response = self.client.get(
            reverse("quotations:detail", args=[other_quote.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_expired_quotation_cannot_be_approved(self):
        quotation = self._create_quotation()
        quotation.valid_until = quotation.issue_date - timedelta(days=1)
        quotation.save(update_fields=["valid_until"])
        with self.assertRaisesMessage(Exception, "expirou"):
            approve_quotation(
                quotation_id=quotation.id, business=self.business, user=self.user
            )
        quotation.refresh_from_db()
        self.assertEqual(quotation.status, Quotation.STATUS_EXPIRED)

    def test_create_form_lists_business_customers_and_quick_create_link(self):
        other_business = Business.objects.create(name="Loja B", slug="loja-b")
        Customer.objects.create(business=other_business, name="Cliente Externo")
        self._login_with_business(self.business)

        response = self.client.get(reverse("quotations:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente A")
        self.assertNotContains(response, "Cliente Externo")
        self.assertContains(response, reverse("customers:quick_create"))
        self.assertContains(response, "Criar cliente rápido")
