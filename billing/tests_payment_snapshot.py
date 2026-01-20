from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from billing.services import generate_invoice
from sales.models import Sale
from tenants.models import Business, TenantBankAccount, TenantMobileWallet
from customers.models import Customer


class InvoicePaymentSnapshotTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="owner", password="pass")
        self.business = Business.objects.create(name="Loja", slug="loja")
        self.customer = Customer.objects.create(business=self.business, name="Cliente")
        TenantMobileWallet.objects.create(
            business=self.business,
            wallet_type=TenantMobileWallet.WALLET_MPESA,
            holder_name="Loja Central",
            phone_number="841234567",
            is_active=True,
        )
        TenantMobileWallet.objects.create(
            business=self.business,
            wallet_type=TenantMobileWallet.WALLET_EMOLA,
            holder_name="Loja Central",
            phone_number="821234567",
            is_active=True,
        )
        TenantBankAccount.objects.create(
            business=self.business,
            bank_name="BCI",
            account_number="1234567890",
            nib="0000000000000000000",
            holder_name="Loja Central",
            is_active=True,
        )

    def test_invoice_stores_payment_snapshot(self):
        sale = Sale.objects.create(
            business=self.business,
            customer=self.customer,
            status=Sale.STATUS_CONFIRMED,
            subtotal=Decimal("100.00"),
            tax_total=Decimal("16.00"),
            total=Decimal("116.00"),
        )
        invoice = generate_invoice(
            sale_id=sale.id,
            business=self.business,
            user=self.user,
        )
        self.assertIn("wallets", invoice.payment_snapshot)
        self.assertIn("banks", invoice.payment_snapshot)
        self.assertEqual(len(invoice.payment_snapshot["wallets"]), 2)
        self.assertEqual(len(invoice.payment_snapshot["banks"]), 1)
