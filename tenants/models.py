from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import models
from django.db.models import Q
from django.utils import timezone as dj_timezone
from django.utils.text import slugify


class Business(models.Model):
    BUSINESS_GENERAL = "general"
    BUSINESS_HARDWARE = "hardware"
    BUSINESS_WORKSHOP = "workshop"
    BUSINESS_RESTAURANT = "restaurant"
    BUSINESS_BURGER = "burger"
    BUSINESS_GROCERY = "grocery"
    BUSINESS_MINI_GROCERY = "mini_grocery"
    BUSINESS_CLOTHING = "clothing"
    BUSINESS_ELECTRIC = "electric"
    BUSINESS_ALCOHOL = "alcohol_stall"
    BUSINESS_TYPE_CHOICES = [
        (BUSINESS_GENERAL, "Negocio geral"),
        (BUSINESS_HARDWARE, "Ferragem / construcao"),
        (BUSINESS_WORKSHOP, "Oficina mecanica"),
        (BUSINESS_RESTAURANT, "Restaurante (servico a mesa)"),
        (BUSINESS_BURGER, "Hamburgueria (fast-casual)"),
        (BUSINESS_GROCERY, "Mini-mercearia / cantina"),
        (BUSINESS_MINI_GROCERY, "Mini-mercearia (novo)"),
        (BUSINESS_CLOTHING, "Loja de roupa"),
        (BUSINESS_ELECTRIC, "Material eletrico / mecanico"),
        (BUSINESS_ALCOHOL, "Barraca de bebidas"),
    ]

    MODULE_QUOTATIONS = "quotations"
    MODULE_CASHFLOW = "cashflow"
    MODULE_CATALOG = "catalog"
    MODULE_KEYS = [MODULE_QUOTATIONS, MODULE_CASHFLOW, MODULE_CATALOG]

    MODULE_DEFAULTS = {
        BUSINESS_GENERAL: {MODULE_QUOTATIONS: False, MODULE_CASHFLOW: True, MODULE_CATALOG: True},
        BUSINESS_HARDWARE: {MODULE_QUOTATIONS: True, MODULE_CASHFLOW: True, MODULE_CATALOG: True},
        BUSINESS_WORKSHOP: {MODULE_QUOTATIONS: True, MODULE_CASHFLOW: True, MODULE_CATALOG: True},
        BUSINESS_ELECTRIC: {MODULE_QUOTATIONS: True, MODULE_CASHFLOW: True, MODULE_CATALOG: True},
        BUSINESS_RESTAURANT: {MODULE_QUOTATIONS: False, MODULE_CASHFLOW: True, MODULE_CATALOG: True},
        BUSINESS_BURGER: {MODULE_QUOTATIONS: False, MODULE_CASHFLOW: True, MODULE_CATALOG: True},
        BUSINESS_GROCERY: {MODULE_QUOTATIONS: False, MODULE_CASHFLOW: True, MODULE_CATALOG: True},
        BUSINESS_MINI_GROCERY: {MODULE_QUOTATIONS: False, MODULE_CASHFLOW: True, MODULE_CATALOG: True},
        BUSINESS_CLOTHING: {MODULE_QUOTATIONS: False, MODULE_CASHFLOW: True, MODULE_CATALOG: True},
        BUSINESS_ALCOHOL: {MODULE_QUOTATIONS: False, MODULE_CASHFLOW: True, MODULE_CATALOG: True},
    }

    FEATURE_PAY_BEFORE_SERVICE = "pay_before_service"
    FEATURE_USE_TABLES = "use_tables"
    FEATURE_USE_KITCHEN_DISPLAY = "use_kitchen_display"
    FEATURE_USE_RECIPES = "use_recipes"
    FEATURE_USE_VARIANTS = "use_variants"
    FEATURE_USE_FRACTIONAL_UNITS = "use_fractional_units"
    FEATURE_ALLOW_CREDIT_SALES = "allow_credit_sales"
    FEATURE_ENABLE_DELIVERY = "enable_delivery"
    FEATURE_ENABLE_RETURNS = "enable_returns"
    FEATURE_REQUIRE_AGE_CHECK = "require_age_check"

    FEATURE_KEYS = [
        FEATURE_PAY_BEFORE_SERVICE,
        FEATURE_USE_TABLES,
        FEATURE_USE_KITCHEN_DISPLAY,
        FEATURE_USE_RECIPES,
        FEATURE_USE_VARIANTS,
        FEATURE_USE_FRACTIONAL_UNITS,
        FEATURE_ALLOW_CREDIT_SALES,
        FEATURE_ENABLE_DELIVERY,
        FEATURE_ENABLE_RETURNS,
        FEATURE_REQUIRE_AGE_CHECK,
    ]

    FEATURE_DEFAULTS = {
        BUSINESS_GENERAL: {
            FEATURE_PAY_BEFORE_SERVICE: True,
            FEATURE_USE_TABLES: False,
            FEATURE_USE_KITCHEN_DISPLAY: False,
            FEATURE_USE_RECIPES: False,
            FEATURE_USE_VARIANTS: False,
            FEATURE_USE_FRACTIONAL_UNITS: False,
            FEATURE_ALLOW_CREDIT_SALES: True,
            FEATURE_ENABLE_DELIVERY: False,
            FEATURE_ENABLE_RETURNS: True,
            FEATURE_REQUIRE_AGE_CHECK: False,
        },
        BUSINESS_HARDWARE: {
            FEATURE_PAY_BEFORE_SERVICE: True,
            FEATURE_USE_TABLES: False,
            FEATURE_USE_KITCHEN_DISPLAY: False,
            FEATURE_USE_RECIPES: False,
            FEATURE_USE_VARIANTS: False,
            FEATURE_USE_FRACTIONAL_UNITS: True,
            FEATURE_ALLOW_CREDIT_SALES: True,
            FEATURE_ENABLE_DELIVERY: True,
            FEATURE_ENABLE_RETURNS: True,
            FEATURE_REQUIRE_AGE_CHECK: False,
        },
        BUSINESS_WORKSHOP: {
            FEATURE_PAY_BEFORE_SERVICE: True,
            FEATURE_USE_TABLES: False,
            FEATURE_USE_KITCHEN_DISPLAY: False,
            FEATURE_USE_RECIPES: False,
            FEATURE_USE_VARIANTS: False,
            FEATURE_USE_FRACTIONAL_UNITS: False,
            FEATURE_ALLOW_CREDIT_SALES: True,
            FEATURE_ENABLE_DELIVERY: False,
            FEATURE_ENABLE_RETURNS: True,
            FEATURE_REQUIRE_AGE_CHECK: False,
        },
        BUSINESS_RESTAURANT: {
            FEATURE_PAY_BEFORE_SERVICE: False,
            FEATURE_USE_TABLES: True,
            FEATURE_USE_KITCHEN_DISPLAY: True,
            FEATURE_USE_RECIPES: True,
            FEATURE_USE_VARIANTS: False,
            FEATURE_USE_FRACTIONAL_UNITS: False,
            FEATURE_ALLOW_CREDIT_SALES: False,
            FEATURE_ENABLE_DELIVERY: True,
            FEATURE_ENABLE_RETURNS: False,
            FEATURE_REQUIRE_AGE_CHECK: False,
        },
        BUSINESS_BURGER: {
            FEATURE_PAY_BEFORE_SERVICE: True,
            FEATURE_USE_TABLES: False,
            FEATURE_USE_KITCHEN_DISPLAY: True,
            FEATURE_USE_RECIPES: True,
            FEATURE_USE_VARIANTS: False,
            FEATURE_USE_FRACTIONAL_UNITS: False,
            FEATURE_ALLOW_CREDIT_SALES: False,
            FEATURE_ENABLE_DELIVERY: True,
            FEATURE_ENABLE_RETURNS: False,
            FEATURE_REQUIRE_AGE_CHECK: False,
        },
        BUSINESS_GROCERY: {
            FEATURE_PAY_BEFORE_SERVICE: True,
            FEATURE_USE_TABLES: False,
            FEATURE_USE_KITCHEN_DISPLAY: False,
            FEATURE_USE_RECIPES: False,
            FEATURE_USE_VARIANTS: False,
            FEATURE_USE_FRACTIONAL_UNITS: True,
            FEATURE_ALLOW_CREDIT_SALES: True,
            FEATURE_ENABLE_DELIVERY: False,
            FEATURE_ENABLE_RETURNS: True,
            FEATURE_REQUIRE_AGE_CHECK: False,
        },
        BUSINESS_MINI_GROCERY: {
            FEATURE_PAY_BEFORE_SERVICE: True,
            FEATURE_USE_TABLES: False,
            FEATURE_USE_KITCHEN_DISPLAY: False,
            FEATURE_USE_RECIPES: False,
            FEATURE_USE_VARIANTS: False,
            FEATURE_USE_FRACTIONAL_UNITS: True,
            FEATURE_ALLOW_CREDIT_SALES: True,
            FEATURE_ENABLE_DELIVERY: False,
            FEATURE_ENABLE_RETURNS: True,
            FEATURE_REQUIRE_AGE_CHECK: False,
        },
        BUSINESS_CLOTHING: {
            FEATURE_PAY_BEFORE_SERVICE: True,
            FEATURE_USE_TABLES: False,
            FEATURE_USE_KITCHEN_DISPLAY: False,
            FEATURE_USE_RECIPES: False,
            FEATURE_USE_VARIANTS: True,
            FEATURE_USE_FRACTIONAL_UNITS: False,
            FEATURE_ALLOW_CREDIT_SALES: False,
            FEATURE_ENABLE_DELIVERY: False,
            FEATURE_ENABLE_RETURNS: True,
            FEATURE_REQUIRE_AGE_CHECK: False,
        },
        BUSINESS_ELECTRIC: {
            FEATURE_PAY_BEFORE_SERVICE: True,
            FEATURE_USE_TABLES: False,
            FEATURE_USE_KITCHEN_DISPLAY: False,
            FEATURE_USE_RECIPES: False,
            FEATURE_USE_VARIANTS: False,
            FEATURE_USE_FRACTIONAL_UNITS: True,
            FEATURE_ALLOW_CREDIT_SALES: True,
            FEATURE_ENABLE_DELIVERY: True,
            FEATURE_ENABLE_RETURNS: True,
            FEATURE_REQUIRE_AGE_CHECK: False,
        },
        BUSINESS_ALCOHOL: {
            FEATURE_PAY_BEFORE_SERVICE: True,
            FEATURE_USE_TABLES: False,
            FEATURE_USE_KITCHEN_DISPLAY: False,
            FEATURE_USE_RECIPES: False,
            FEATURE_USE_VARIANTS: False,
            FEATURE_USE_FRACTIONAL_UNITS: False,
            FEATURE_ALLOW_CREDIT_SALES: False,
            FEATURE_ENABLE_DELIVERY: False,
            FEATURE_ENABLE_RETURNS: True,
            FEATURE_REQUIRE_AGE_CHECK: True,
        },
    }

    LABEL_DEFAULTS = {
        "products": "Produtos",
        "product": "Produto",
        "new_product": "Novo produto",
        "products_empty": "Sem produtos.",
        "products_total": "Total de produtos",
        "sales": "Vendas",
        "sale": "Venda",
        "new_sale": "Nova venda",
        "sales_empty": "Sem vendas.",
        "sales_today": "Vendas hoje",
        "sales_count": "vendas",
        "sales_total": "Total de vendas",
        "sales_canceled": "Vendas canceladas",
        "sales_vs_payments": "Vendas vs pagamentos (ultimos 6 meses)",
        "top_products": "Top produtos por vendas",
    }

    LABEL_OVERRIDES = {
        BUSINESS_RESTAURANT: {
            "products": "Menu",
            "product": "Item",
            "new_product": "Novo item",
            "products_empty": "Sem itens.",
            "products_total": "Total de itens do menu",
            "sales": "Pedidos",
            "sale": "Pedido",
            "new_sale": "Novo pedido",
            "sales_empty": "Sem pedidos.",
            "sales_today": "Pedidos hoje",
            "sales_count": "pedidos",
            "sales_total": "Total de pedidos",
            "sales_canceled": "Pedidos cancelados",
            "sales_vs_payments": "Pedidos vs pagamentos (ultimos 6 meses)",
            "top_products": "Top itens por pedidos",
        },
        BUSINESS_BURGER: {
            "products": "Menu",
            "product": "Item",
            "new_product": "Novo item",
            "products_empty": "Sem itens.",
            "products_total": "Total de itens do menu",
            "sales": "Pedidos",
            "sale": "Pedido",
            "new_sale": "Novo pedido",
            "sales_empty": "Sem pedidos.",
            "sales_today": "Pedidos hoje",
            "sales_count": "pedidos",
            "sales_total": "Total de pedidos",
            "sales_canceled": "Pedidos cancelados",
            "sales_vs_payments": "Pedidos vs pagamentos (ultimos 6 meses)",
            "top_products": "Top itens por pedidos",
        },
        BUSINESS_WORKSHOP: {
            "products": "Servicos",
            "product": "Servico",
            "new_product": "Novo servico",
            "products_empty": "Sem servicos.",
            "products_total": "Total de servicos",
            "sales": "Ordens",
            "sale": "Ordem",
            "new_sale": "Nova ordem",
            "sales_empty": "Sem ordens.",
            "sales_today": "Ordens hoje",
            "sales_count": "ordens",
            "sales_total": "Total de ordens",
            "sales_canceled": "Ordens canceladas",
            "sales_vs_payments": "Ordens vs pagamentos (ultimos 6 meses)",
            "top_products": "Top servicos por ordens",
        },
    }

    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(max_length=80, unique=True)
    business_type = models.CharField(
        max_length=30, choices=BUSINESS_TYPE_CHOICES, default=BUSINESS_GENERAL
    )
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_ACTIVE, "Ativo"),
        (STATUS_INACTIVE, "Inativo"),
        (STATUS_REJECTED, "Rejeitado"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    nuit = models.CharField(max_length=30, blank=True, null=True)
    commercial_registration = models.CharField(max_length=60, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    country = models.CharField(max_length=80, blank=True)
    city = models.CharField(max_length=80, blank=True)
    currency = models.CharField(max_length=10, default="MZN")
    timezone = models.CharField(max_length=60, default="Africa/Maputo")
    logo = models.ImageField(upload_to="business_logos/", blank=True, null=True)
    modules_enabled = models.JSONField(default=dict, blank=True)
    feature_flags = models.JSONField(default=dict, blank=True)
    vat_enabled = models.BooleanField(default=True)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("0.16"))
    prices_include_vat = models.BooleanField(default=True)
    allow_negative_stock = models.BooleanField(default=False)
    allow_over_delivery_deposit = models.BooleanField(default=False)
    registered_at = models.DateTimeField(default=dj_timezone.now)
    registration_ip = models.CharField(max_length=45, blank=True)
    approval_note = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_businesses",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_businesses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["nuit"],
                name="unique_business_nuit",
                condition=Q(nuit__isnull=False) & ~Q(nuit=""),
            )
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:80]
        super().save(*args, **kwargs)

    def get_module_flags(self):
        defaults = self.MODULE_DEFAULTS.get(self.business_type, {}).copy()
        overrides = self.modules_enabled or {}
        for key in self.MODULE_KEYS:
            if key in overrides:
                defaults[key] = bool(overrides.get(key))
            else:
                defaults.setdefault(key, False)
        return defaults

    def get_feature_flags(self):
        defaults = self.FEATURE_DEFAULTS.get(self.business_type, {}).copy()
        overrides = self.feature_flags or {}
        for key in self.FEATURE_KEYS:
            if key in overrides:
                defaults[key] = bool(overrides.get(key))
            else:
                defaults.setdefault(key, False)
        return defaults

    def get_ui_labels(self):
        labels = self.LABEL_DEFAULTS.copy()
        labels.update(self.LABEL_OVERRIDES.get(self.business_type, {}))
        return labels

    @property
    def ui_labels(self):
        return self.get_ui_labels()

    @property
    def module_quotations_enabled(self):
        return self.get_module_flags().get(self.MODULE_QUOTATIONS, False)

    @property
    def module_cashflow_enabled(self):
        return self.get_module_flags().get(self.MODULE_CASHFLOW, False)

    @property
    def module_catalog_enabled(self):
        return self.get_module_flags().get(self.MODULE_CATALOG, False)

    @property
    def allow_credit_sales_enabled(self):
        return self.feature_enabled(self.FEATURE_ALLOW_CREDIT_SALES)

    @property
    def enable_returns_enabled(self):
        return self.feature_enabled(self.FEATURE_ENABLE_RETURNS)

    def feature_enabled(self, key):
        return self.get_feature_flags().get(key, False)

    def __str__(self):
        return self.name

    def get_payment_snapshot(self):
        wallets = [
            {
                "type": wallet.wallet_type,
                "label": wallet.get_wallet_type_display(),
                "holder_name": wallet.holder_name,
                "phone_number": wallet.phone_number,
            }
            for wallet in self.mobile_wallets.filter(is_active=True).order_by("id")
        ]
        banks = [
            {
                "bank_name": bank.bank_name,
                "account_number": bank.account_number,
                "nib": bank.nib,
                "holder_name": bank.holder_name,
            }
            for bank in self.bank_accounts.filter(is_active=True).order_by("id")
        ]
        return {"wallets": wallets, "banks": banks}


class TenantMobileWallet(models.Model):
    WALLET_MPESA = "mpesa"
    WALLET_MKESH = "mkesh"
    WALLET_EMOLA = "emola"
    WALLET_CHOICES = [
        (WALLET_MPESA, "M-Pesa"),
        (WALLET_MKESH, "M-Kesh"),
        (WALLET_EMOLA, "e-Mola"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="mobile_wallets"
    )
    wallet_type = models.CharField(max_length=20, choices=WALLET_CHOICES)
    holder_name = models.CharField(max_length=120)
    phone_number = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tenant_wallets",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_tenant_wallets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "wallet_type"]),
        ]

    def __str__(self):
        return f"{self.get_wallet_type_display()} - {self.phone_number}"


class TenantBankAccount(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="bank_accounts"
    )
    bank_name = models.CharField(max_length=120)
    account_number = models.CharField(max_length=60)
    nib = models.CharField(max_length=60)
    holder_name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tenant_bank_accounts",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_tenant_bank_accounts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "bank_name"]),
        ]

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"


class TenantEmailLog(models.Model):
    TYPE_PENDING = "pending"
    TYPE_APPROVED = "approved"
    TYPE_REJECTED = "rejected"
    TYPE_CHOICES = [
        (TYPE_PENDING, "Registo pendente"),
        (TYPE_APPROVED, "Aprovacao"),
        (TYPE_REJECTED, "Rejeicao"),
    ]
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SENT, "Enviado"),
        (STATUS_FAILED, "Falhou"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="email_logs"
    )
    email_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    recipient = models.EmailField()
    subject = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error_message = models.TextField(blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_email_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "email_type"]),
        ]

    def __str__(self):
        return f"{self.get_email_type_display()} - {self.recipient}"


class TenantRole(models.Model):
    ROLE_OWNER_ADMIN = "owner_admin"
    ROLE_MANAGER = "manager"
    ROLE_CASHIER = "cashier_sales"
    ROLE_FINANCE = "finance"
    ROLE_STOCK = "stock_warehouse"
    ROLE_OPERATIONS = "operations_production"
    ROLE_SUPPORT = "support_viewer"
    ROLE_CHOICES = [
        (ROLE_OWNER_ADMIN, "Admin da empresa"),
        (ROLE_MANAGER, "Gerente"),
        (ROLE_CASHIER, "Caixa/Vendas"),
        (ROLE_FINANCE, "Financeiro"),
        (ROLE_STOCK, "Stock/Armazem"),
        (ROLE_OPERATIONS, "Operacional/Producao"),
        (ROLE_SUPPORT, "Leitura/Suporte"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="roles"
    )
    code = models.CharField(max_length=40, choices=ROLE_CHOICES)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    permissions = models.ManyToManyField(
        Permission, blank=True, related_name="tenant_roles"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tenant_roles",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_tenant_roles",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"], name="uniq_tenant_role_code"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.business})"


class RoleAuditLog(models.Model):
    TARGET_ROLE = "role"
    TARGET_USER = "user"
    TARGET_CHOICES = [
        (TARGET_ROLE, "Role"),
        (TARGET_USER, "Utilizador"),
    ]
    ACTION_UPDATE = "update"
    ACTION_RESET = "reset"
    ACTION_ASSIGN = "assign"
    ACTION_CHOICES = [
        (ACTION_UPDATE, "Atualizar"),
        (ACTION_RESET, "Reset"),
        (ACTION_ASSIGN, "Atribuir"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="role_audits"
    )
    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES)
    role = models.ForeignKey(
        TenantRole, on_delete=models.SET_NULL, null=True, blank=True
    )
    membership = models.ForeignKey(
        "BusinessMembership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    payload = models.JSONField(default=dict, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="role_audit_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} {self.target_type}"

class BusinessMembership(models.Model):
    ROLE_OWNER = "owner"
    ROLE_STAFF = "staff"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_STAFF, "Staff"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STAFF)
    role_profile = models.ForeignKey(
        TenantRole,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memberships",
    )
    extra_permissions = models.ManyToManyField(
        Permission, blank=True, related_name="membership_extra_permissions"
    )
    revoked_permissions = models.ManyToManyField(
        Permission, blank=True, related_name="membership_revoked_permissions"
    )
    department = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_memberships",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_memberships",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("business", "user")

    def get_effective_permission_ids(self):
        role_perm_ids = set()
        if self.role_profile_id and self.role_profile_id is not None:
            role_perm_ids = set(self.role_profile.permissions.values_list("id", flat=True))
        extra_ids = set(self.extra_permissions.values_list("id", flat=True))
        revoked_ids = set(self.revoked_permissions.values_list("id", flat=True))
        return (role_perm_ids | extra_ids) - revoked_ids

    def get_effective_permission_keys(self):
        perms = Permission.objects.filter(id__in=self.get_effective_permission_ids()).select_related(
            "content_type"
        )
        return {f"{perm.content_type.app_label}.{perm.codename}" for perm in perms}

    def has_permission(self, perm_key):
        if not perm_key or "." not in perm_key:
            return False
        app_label, codename = perm_key.split(".", 1)
        return (
            Permission.objects.filter(
                id__in=self.get_effective_permission_ids(),
                content_type__app_label=app_label,
                codename=codename,
            ).exists()
        )

    def __str__(self):
        return f"{self.user} - {self.business} ({self.role})"


class DocumentSequence(models.Model):
    DOC_SALE = "sale"
    DOC_ORDER = "order"
    DOC_INVOICE = "invoice"
    DOC_RECEIPT = "receipt"
    DOC_DELIVERY = "delivery"
    DOC_PURCHASE = "purchase"
    DOC_QUOTATION = "quotation"
    DOC_EXPENSE = "expense"
    DOC_CHOICES = [
        (DOC_SALE, "Venda"),
        (DOC_ORDER, "Pedido"),
        (DOC_INVOICE, "Fatura"),
        (DOC_RECEIPT, "Recibo"),
        (DOC_DELIVERY, "Guia de entrega"),
        (DOC_PURCHASE, "Compra"),
        (DOC_QUOTATION, "Cotacao"),
        (DOC_EXPENSE, "Despesa"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="document_sequences"
    )
    doc_type = models.CharField(max_length=20, choices=DOC_CHOICES)
    seq_date = models.DateField()
    current_value = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "doc_type", "seq_date"],
                name="uniq_document_sequence",
            )
        ]

    def __str__(self):
        return f"{self.business} {self.doc_type} {self.seq_date}"
