from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from finance.models import CashMovement, FinancialAccount, PaymentMethod
from finance.services import _create_cash_in, _create_cash_out, ensure_default_payment_methods
from tenants.models import Business


class FinanceServicesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="finance-user", password="pass")
        self.business = Business.objects.create(
            name="Finance Burger",
            slug="finance-burger",
            business_type=Business.BUSINESS_BURGER,
        )

    def test_ensure_default_payment_methods_creates_accounts_and_methods(self):
        ensure_default_payment_methods(self.business)

        accounts = FinancialAccount.objects.filter(business=self.business)
        methods = PaymentMethod.objects.filter(business=self.business, is_active=True)

        self.assertGreaterEqual(accounts.count(), 3)
        self.assertTrue(methods.filter(code=CashMovement.METHOD_CASH).exists())
        self.assertTrue(methods.filter(code=CashMovement.METHOD_MPESA).exists())

    def test_create_cash_in_resolves_category_and_account(self):
        movement = _create_cash_in(
            business=self.business,
            amount=Decimal("300.00"),
            method=CashMovement.METHOD_MPESA,
            reference_type="order_payment",
            reference_id=123,
            user=self.user,
            notes="Pagamento teste",
        )

        self.assertIsNotNone(movement)
        self.assertEqual(movement.category, FinancialAccount.CATEGORY_MOBILE)
        self.assertIsNotNone(movement.account_id)
        self.assertEqual(movement.movement_type, CashMovement.MOVEMENT_IN)

    def test_create_cash_out_requires_method(self):
        with self.assertRaises(ValidationError):
            _create_cash_out(
                business=self.business,
                amount=Decimal("100.00"),
                method="",
                reference_type="burger_manual",
                reference_id=1,
                user=self.user,
                notes="Saida sem metodo",
            )
