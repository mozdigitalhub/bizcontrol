from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from catalog.models import Product
from tenants.models import Business


class Supplier(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="suppliers"
    )
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("business", "name")

    def __str__(self):
        return self.name


class ExpenseCategory(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="expense_categories"
    )
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("business", "name")

    def __str__(self):
        return self.name


class FinancialAccount(models.Model):
    CATEGORY_CASH = "cash"
    CATEGORY_BANK = "bank"
    CATEGORY_MOBILE = "mobile"
    CATEGORY_CHOICES = [
        (CATEGORY_CASH, "Caixa"),
        (CATEGORY_BANK, "Banco"),
        (CATEGORY_MOBILE, "Carteiras moveis"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="financial_accounts"
    )
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("business", "name")

    def __str__(self):
        return self.name


class PaymentMethod(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="payment_methods"
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=FinancialAccount.CATEGORY_CHOICES)
    account = models.ForeignKey(
        FinancialAccount, on_delete=models.PROTECT, related_name="payment_methods"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("business", "code")

    def __str__(self):
        return self.name


class CashMovement(models.Model):
    MOVEMENT_IN = "IN"
    MOVEMENT_OUT = "OUT"
    MOVEMENT_CHOICES = [
        (MOVEMENT_IN, "Entrada"),
        (MOVEMENT_OUT, "Saida"),
    ]
    METHOD_CASH = "cash"
    METHOD_CARD = "card"
    METHOD_TRANSFER = "bank_transfer"
    METHOD_CHEQUE = "cheque"
    METHOD_MPESA = "mpesa"
    METHOD_EMOLA = "emola"
    METHOD_MKESH = "mkesh"
    METHOD_OTHER = "other"
    METHOD_CHOICES = [
        (METHOD_CASH, "Numerario"),
        (METHOD_CARD, "Cartao"),
        (METHOD_TRANSFER, "Transferencia"),
        (METHOD_CHEQUE, "Cheque"),
        (METHOD_MPESA, "MPesa"),
        (METHOD_EMOLA, "Emola"),
        (METHOD_MKESH, "MKesh"),
        (METHOD_OTHER, "Outro"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="cash_movements"
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cash_movements",
    )
    category = models.CharField(
        max_length=20,
        choices=FinancialAccount.CATEGORY_CHOICES,
        blank=True,
    )
    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cash_movements",
    )
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    reference_type = models.CharField(max_length=30, blank=True)
    reference_id = models.PositiveBigIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    happened_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "happened_at"]),
            models.Index(fields=["business", "category"]),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} {self.amount}"


class Purchase(models.Model):
    TYPE_STOCK = "stock"
    TYPE_INTERNAL = "internal"
    TYPE_CHOICES = [
        (TYPE_STOCK, "Reposicao de stock"),
        (TYPE_INTERNAL, "Uso interno"),
    ]
    STATUS_DRAFT = "draft"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Rascunho"),
        (STATUS_CONFIRMED, "Confirmada"),
        (STATUS_CANCELED, "Cancelada"),
    ]
    PAYMENT_UNPAID = "unpaid"
    PAYMENT_PARTIAL = "partial"
    PAYMENT_PAID = "paid"
    PAYMENT_CHOICES = [
        (PAYMENT_UNPAID, "Em aberto"),
        (PAYMENT_PARTIAL, "Parcial"),
        (PAYMENT_PAID, "Pago"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="purchases"
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchases"
    )
    code = models.CharField(max_length=30, null=True, blank=True)
    purchase_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    purchase_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(
        max_length=20, choices=CashMovement.METHOD_CHOICES, blank=True
    )
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_UNPAID
    )
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    stock_received = models.BooleanField(default=False)
    internal_description = models.CharField(max_length=255, blank=True)
    internal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_purchases",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_purchases",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"],
                condition=Q(code__isnull=False),
                name="uniq_purchase_code_business",
            ),
        ]

    def __str__(self):
        return f"Compra {self.code or self.id}"


class PurchasePayment(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="purchase_payments"
    )
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    method = models.CharField(max_length=20, choices=CashMovement.METHOD_CHOICES)
    notes = models.TextField(blank=True)
    paid_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "paid_at"]),
        ]

    def __str__(self):
        return f"Pagamento compra {self.purchase_id} - {self.amount}"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product} {self.quantity}"


class Expense(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PAID = "paid"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Rascunho"),
        (STATUS_PAID, "Paga"),
        (STATUS_CANCELED, "Cancelada"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="expenses"
    )
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    expense_date = models.DateField()
    payment_method = models.CharField(
        max_length=20, choices=CashMovement.METHOD_CHOICES, blank=True
    )
    attachment = models.FileField(upload_to="expense_receipts/", blank=True, null=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_expenses",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_expenses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
