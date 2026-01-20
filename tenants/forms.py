import re

from django import forms

from tenants.models import Business, TenantBankAccount, TenantMobileWallet


PHONE_RE = re.compile(r"^\+?\d{7,15}$")
ACCOUNT_RE = re.compile(r"^\d{5,30}$")
NIB_RE = re.compile(r"^\d{10,30}$")


class BusinessProfileForm(forms.ModelForm):

    class Meta:
        model = Business
        fields = [
            "name",
            "legal_name",
            "nuit",
            "commercial_registration",
            "phone",
            "email",
            "address",
            "country",
            "city",
            "logo",
        ]
        labels = {
            "name": "Nome comercial",
            "legal_name": "Razao social",
            "nuit": "NUIT",
            "commercial_registration": "Registo comercial",
            "phone": "Contacto",
            "email": "Email",
            "address": "Endereco",
            "country": "Pais",
            "city": "Cidade",
            "logo": "Logotipo",
        }

    def __init__(self, *args, **kwargs):
        can_edit_legal = kwargs.pop("can_edit_legal", True)
        super().__init__(*args, **kwargs)
        self.can_edit_legal = can_edit_legal
        if self.is_bound:
            _ = self.errors
        if "name" in self.fields:
            self.fields["name"].widget.attrs.update({"placeholder": "Nome comercial"})
        if "legal_name" in self.fields:
            self.fields["legal_name"].widget.attrs.update(
                {"placeholder": "Razao social (opcional)"}
            )
        if "phone" in self.fields:
            self.fields["phone"].widget.attrs.update({"placeholder": "Contacto"})
        if "email" in self.fields:
            self.fields["email"].widget.attrs.update({"placeholder": "Email"})
        if "address" in self.fields:
            self.fields["address"].widget.attrs.update({"placeholder": "Endereco"})
        if "nuit" in self.fields:
            self.fields["nuit"].widget.attrs.update({"placeholder": "NUIT"})
        if "commercial_registration" in self.fields:
            self.fields["commercial_registration"].widget.attrs.update(
                {"placeholder": "Numero de registo comercial"}
            )
        if "country" in self.fields:
            self.fields["country"].widget.attrs.update({"placeholder": "Pais"})
        if "city" in self.fields:
            self.fields["city"].widget.attrs.update({"placeholder": "Cidade"})
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
                if field.required:
                    field.widget.attrs["required"] = "required"
                if name in self.errors:
                    field.widget.attrs["class"] += " is-invalid"

        if can_edit_legal and "nuit" in self.fields:
            self.fields["nuit"].required = True
            self.fields["nuit"].widget.attrs["required"] = "required"

        if not can_edit_legal:
            for field_name in ["nuit", "commercial_registration", "legal_name"]:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

    def clean_nuit(self):
        nuit = (self.cleaned_data.get("nuit") or "").strip().replace(" ", "")
        if not nuit:
            return None
        if not nuit.isdigit() or len(nuit) != 9:
            raise forms.ValidationError("NUIT deve ter 9 digitos.")
        qs = Business.objects.filter(nuit=nuit)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Este NUIT ja esta registado.")
        return nuit

    def clean_commercial_registration(self):
        value = (self.cleaned_data.get("commercial_registration") or "").strip()
        return value

    def clean_legal_name(self):
        value = (self.cleaned_data.get("legal_name") or "").strip()
        return value


class BusinessSettingsForm(forms.ModelForm):
    module_quotations = forms.BooleanField(required=False, label="Ativar cotacoes")
    module_cashflow = forms.BooleanField(required=False, label="Ativar fluxo de caixa")
    module_catalog = forms.BooleanField(required=False, label="Ativar catalogo")
    flag_pay_before_service = forms.BooleanField(
        required=False, label="Pagamento antes do servico"
    )
    flag_use_tables = forms.BooleanField(required=False, label="Usar mesas")
    flag_use_kitchen_display = forms.BooleanField(
        required=False, label="Usar painel de cozinha (KDS)"
    )
    flag_use_recipes = forms.BooleanField(
        required=False, label="Baixar ingredientes por receita"
    )
    flag_use_variants = forms.BooleanField(
        required=False, label="Usar variantes (tamanho/cor)"
    )
    flag_use_fractional_units = forms.BooleanField(
        required=False, label="Permitir unidades fracionadas"
    )
    flag_allow_credit_sales = forms.BooleanField(
        required=False, label="Permitir vendas a credito"
    )
    flag_enable_delivery = forms.BooleanField(
        required=False, label="Ativar entregas/delivery"
    )
    flag_enable_returns = forms.BooleanField(
        required=False, label="Permitir devolucoes"
    )
    flag_require_age_check = forms.BooleanField(
        required=False, label="Exigir confirmacao de idade"
    )

    class Meta:
        model = Business
        fields = [
            "business_type",
            "currency",
            "timezone",
            "vat_enabled",
            "vat_rate",
            "prices_include_vat",
            "allow_negative_stock",
            "allow_over_delivery_deposit",
        ]
        labels = {
            "business_type": "Tipo de negocio",
            "currency": "Moeda",
            "timezone": "Timezone",
            "vat_enabled": "IVA ativo",
            "vat_rate": "Taxa de IVA",
            "prices_include_vat": "Precos com IVA",
            "allow_negative_stock": "Permitir stock negativo",
            "allow_over_delivery_deposit": "Permitir levantamento acima do pago (deposito)",
        }

    def __init__(self, *args, **kwargs):
        can_edit_settings = kwargs.pop("can_edit_settings", True)
        super().__init__(*args, **kwargs)
        self.can_edit_settings = can_edit_settings
        if self.instance and self.instance.pk:
            modules = self.instance.get_module_flags()
            self.fields["module_quotations"].initial = modules.get(
                Business.MODULE_QUOTATIONS, False
            )
            self.fields["module_cashflow"].initial = modules.get(
                Business.MODULE_CASHFLOW, False
            )
            self.fields["module_catalog"].initial = modules.get(
                Business.MODULE_CATALOG, False
            )
            flags = self.instance.get_feature_flags()
            self.fields["flag_pay_before_service"].initial = flags.get(
                Business.FEATURE_PAY_BEFORE_SERVICE, False
            )
            self.fields["flag_use_tables"].initial = flags.get(
                Business.FEATURE_USE_TABLES, False
            )
            self.fields["flag_use_kitchen_display"].initial = flags.get(
                Business.FEATURE_USE_KITCHEN_DISPLAY, False
            )
            self.fields["flag_use_recipes"].initial = flags.get(
                Business.FEATURE_USE_RECIPES, False
            )
            self.fields["flag_use_variants"].initial = flags.get(
                Business.FEATURE_USE_VARIANTS, False
            )
            self.fields["flag_use_fractional_units"].initial = flags.get(
                Business.FEATURE_USE_FRACTIONAL_UNITS, False
            )
            self.fields["flag_allow_credit_sales"].initial = flags.get(
                Business.FEATURE_ALLOW_CREDIT_SALES, False
            )
            self.fields["flag_enable_delivery"].initial = flags.get(
                Business.FEATURE_ENABLE_DELIVERY, False
            )
            self.fields["flag_enable_returns"].initial = flags.get(
                Business.FEATURE_ENABLE_RETURNS, False
            )
            self.fields["flag_require_age_check"].initial = flags.get(
                Business.FEATURE_REQUIRE_AGE_CHECK, False
            )
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
                if field.required:
                    field.widget.attrs["required"] = "required"
                if name in self.errors:
                    field.widget.attrs["class"] += " is-invalid"
        if not can_edit_settings:
            for field_name in list(self.fields.keys()):
                self.fields[field_name].disabled = True
            for field_name in [
                "module_quotations",
                "module_cashflow",
                "module_catalog",
                "flag_pay_before_service",
                "flag_use_tables",
                "flag_use_kitchen_display",
                "flag_use_recipes",
                "flag_use_variants",
                "flag_use_fractional_units",
                "flag_allow_credit_sales",
                "flag_enable_delivery",
                "flag_enable_returns",
                "flag_require_age_check",
            ]:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.can_edit_settings:
            instance.modules_enabled = {
                Business.MODULE_QUOTATIONS: bool(self.cleaned_data.get("module_quotations")),
                Business.MODULE_CASHFLOW: bool(self.cleaned_data.get("module_cashflow")),
                Business.MODULE_CATALOG: bool(self.cleaned_data.get("module_catalog")),
            }
            instance.feature_flags = {
                Business.FEATURE_PAY_BEFORE_SERVICE: bool(
                    self.cleaned_data.get("flag_pay_before_service")
                ),
                Business.FEATURE_USE_TABLES: bool(
                    self.cleaned_data.get("flag_use_tables")
                ),
                Business.FEATURE_USE_KITCHEN_DISPLAY: bool(
                    self.cleaned_data.get("flag_use_kitchen_display")
                ),
                Business.FEATURE_USE_RECIPES: bool(
                    self.cleaned_data.get("flag_use_recipes")
                ),
                Business.FEATURE_USE_VARIANTS: bool(
                    self.cleaned_data.get("flag_use_variants")
                ),
                Business.FEATURE_USE_FRACTIONAL_UNITS: bool(
                    self.cleaned_data.get("flag_use_fractional_units")
                ),
                Business.FEATURE_ALLOW_CREDIT_SALES: bool(
                    self.cleaned_data.get("flag_allow_credit_sales")
                ),
                Business.FEATURE_ENABLE_DELIVERY: bool(
                    self.cleaned_data.get("flag_enable_delivery")
                ),
                Business.FEATURE_ENABLE_RETURNS: bool(
                    self.cleaned_data.get("flag_enable_returns")
                ),
                Business.FEATURE_REQUIRE_AGE_CHECK: bool(
                    self.cleaned_data.get("flag_require_age_check")
                ),
            }
        if commit:
            instance.save()
        return instance


class TenantMobileWalletForm(forms.ModelForm):
    class Meta:
        model = TenantMobileWallet
        fields = ["wallet_type", "holder_name", "phone_number", "is_active"]
        labels = {
            "wallet_type": "Carteira movel",
            "holder_name": "Nome do titular",
            "phone_number": "Numero/Contacto",
            "is_active": "Ativa",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            _ = self.errors
        self.fields["wallet_type"].required = True
        self.fields["holder_name"].required = True
        self.fields["phone_number"].required = True
        self.fields["wallet_type"].widget.attrs.update(
            {"data-placeholder": "Selecione a carteira...", "data-dropdown-parent": "modal"}
        )
        self.fields["holder_name"].widget.attrs.update({"placeholder": "Nome do titular"})
        self.fields["phone_number"].widget.attrs.update({"placeholder": "Ex: 84xxxxxxx"})
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
                if field.required:
                    field.widget.attrs["required"] = "required"
                if name in self.errors:
                    field.widget.attrs["class"] += " is-invalid"

    def clean_phone_number(self):
        value = (self.cleaned_data.get("phone_number") or "").replace(" ", "")
        if not PHONE_RE.match(value):
            raise forms.ValidationError("Informe um contacto valido (7-15 digitos).")
        return value


class TenantBankAccountForm(forms.ModelForm):
    class Meta:
        model = TenantBankAccount
        fields = ["bank_name", "account_number", "nib", "holder_name", "is_active"]
        labels = {
            "bank_name": "Banco",
            "account_number": "Numero da conta",
            "nib": "NIB",
            "holder_name": "Nome do titular",
            "is_active": "Ativo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            _ = self.errors
        self.fields["bank_name"].required = True
        self.fields["account_number"].required = True
        self.fields["nib"].required = True
        self.fields["bank_name"].widget.attrs.update({"placeholder": "Nome do banco"})
        self.fields["account_number"].widget.attrs.update({"placeholder": "Numero da conta"})
        self.fields["nib"].widget.attrs.update({"placeholder": "NIB"})
        self.fields["holder_name"].widget.attrs.update({"placeholder": "Nome do titular (opcional)"})
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
                if field.required:
                    field.widget.attrs["required"] = "required"
                if name in self.errors:
                    field.widget.attrs["class"] += " is-invalid"

    def clean_account_number(self):
        value = (self.cleaned_data.get("account_number") or "").replace(" ", "")
        if not ACCOUNT_RE.match(value):
            raise forms.ValidationError("Informe um numero de conta valido.")
        return value

    def clean_nib(self):
        value = (self.cleaned_data.get("nib") or "").replace(" ", "")
        if not NIB_RE.match(value):
            raise forms.ValidationError("Informe um NIB valido.")
        return value
