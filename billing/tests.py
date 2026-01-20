from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from billing.models import Receipt
from billing.services import generate_invoice, register_invoice_payment
from customers.models import Customer
from receivables.models import Receivable
from receivables.services import register_payment
from sales.models import Sale
from tenants.models import Business, BusinessMembership


class SequenceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="owner", password="pass")
        self.business = Business.objects.create(name="Loja", slug="loja-seq")
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.customer = Customer.objects.create(business=self.business, name="Cliente")

    def test_invoice_sequence_per_business(self):
        sale1 = Sale.objects.create(
            business=self.business,
            customer=self.customer,
            status=Sale.STATUS_CONFIRMED,
            subtotal=Decimal("100.00"),
            tax_total=Decimal("16.00"),
            total=Decimal("116.00"),
        )
        sale2 = Sale.objects.create(
            business=self.business,
            customer=self.customer,
            status=Sale.STATUS_CONFIRMED,
            subtotal=Decimal("200.00"),
            tax_total=Decimal("32.00"),
            total=Decimal("232.00"),
        )
        invoice1 = generate_invoice(
            sale_id=sale1.id, business=self.business, user=self.user
        )
        invoice2 = generate_invoice(
            sale_id=sale2.id, business=self.business, user=self.user
        )
        self.assertEqual(invoice1.invoice_number, 1)
        self.assertEqual(invoice2.invoice_number, 2)

        other_business = Business.objects.create(name="Outra", slug="outra")
        other_sale = Sale.objects.create(
            business=other_business,
            customer=Customer.objects.create(business=other_business, name="Outro"),
            status=Sale.STATUS_CONFIRMED,
            subtotal=Decimal("50.00"),
            tax_total=Decimal("8.00"),
            total=Decimal("58.00"),
        )
        invoice_other = generate_invoice(
            sale_id=other_sale.id, business=other_business, user=self.user
        )
        self.assertEqual(invoice_other.invoice_number, 1)

    def test_receipt_sequence_per_business(self):
        receivable = Receivable.objects.create(
            business=self.business,
            customer=self.customer,
            original_amount=Decimal("100.00"),
            total_paid=Decimal("0.00"),
            status=Receivable.STATUS_OPEN,
        )
        register_payment(
            receivable_id=receivable.id,
            business=self.business,
            amount=Decimal("40.00"),
            method="cash",
            user=self.user,
        )
        register_payment(
            receivable_id=receivable.id,
            business=self.business,
            amount=Decimal("60.00"),
            method="cash",
            user=self.user,
        )
        receipt_numbers = list(
            Receipt.objects.filter(business=self.business)
            .order_by("receipt_number")
            .values_list("receipt_number", flat=True)
        )
        self.assertEqual(receipt_numbers, [1, 2])


class InvoicePaymentRulesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="owner2", password="pass")
        self.business = Business.objects.create(name="Loja Pagamentos", slug="loja-pagamentos")
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.customer = Customer.objects.create(business=self.business, name="Cliente P")

    def _create_invoice(self):
        sale = Sale.objects.create(
            business=self.business,
            customer=self.customer,
            status=Sale.STATUS_CONFIRMED,
            subtotal=Decimal("100.00"),
            tax_total=Decimal("16.00"),
            total=Decimal("116.00"),
        )
        return generate_invoice(sale_id=sale.id, business=self.business, user=self.user)

    def test_invoice_payment_cannot_exceed_balance(self):
        invoice = self._create_invoice()
        with self.assertRaisesMessage(ValidationError, "excede o saldo"):
            register_invoice_payment(
                invoice_id=invoice.id,
                business=self.business,
                amount=Decimal("200.00"),
                method="cash",
                user=self.user,
            )

    def test_invoice_payment_updates_sale_status(self):
        invoice = self._create_invoice()
        register_invoice_payment(
            invoice_id=invoice.id,
            business=self.business,
            amount=invoice.total,
            method="cash",
            user=self.user,
        )
        invoice.refresh_from_db()
        invoice.sale.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(invoice.sale.payment_status, Sale.PAYMENT_PAID)
