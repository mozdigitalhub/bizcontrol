from django.contrib.auth import get_user_model
from django.test import TestCase

from tenants.models import Business, TenantBankAccount, TenantMobileWallet


class TenantPaymentDataTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="owner", password="pass")
        self.business = Business.objects.create(name="Loja", slug="loja")

    def test_business_can_have_multiple_wallets_and_banks(self):
        TenantMobileWallet.objects.create(
            business=self.business,
            wallet_type=TenantMobileWallet.WALLET_MPESA,
            holder_name="Loja",
            phone_number="841234567",
        )
        TenantMobileWallet.objects.create(
            business=self.business,
            wallet_type=TenantMobileWallet.WALLET_EMOLA,
            holder_name="Loja",
            phone_number="821234567",
        )
        TenantBankAccount.objects.create(
            business=self.business,
            bank_name="BCI",
            account_number="1234567890",
            nib="0000000000000000000",
        )
        TenantBankAccount.objects.create(
            business=self.business,
            bank_name="BIM",
            account_number="9876543210",
            nib="1111111111111111111",
        )
        snapshot = self.business.get_payment_snapshot()
        self.assertEqual(len(snapshot["wallets"]), 2)
        self.assertEqual(len(snapshot["banks"]), 2)
