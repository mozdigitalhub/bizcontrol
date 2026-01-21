import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from accounts.models import UserProfile
from tenants.models import Business, TenantBankAccount, TenantMobileWallet, TenantRole


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

    def save(self, commit=True):
        instance = super().save(commit=False)
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


class EmailSendForm(forms.Form):
    email = forms.EmailField(label="Email", required=True)
    message = forms.CharField(
        label="Mensagem",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            _ = self.errors
        self.fields["email"].widget.attrs.update(
            {"class": "form-control", "placeholder": "email@cliente.com"}
        )
        self.fields["message"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Mensagem (opcional)"}
        )
        if "email" in self.errors:
            self.fields["email"].widget.attrs["class"] += " is-invalid"

    def clean_nib(self):
        value = (self.cleaned_data.get("nib") or "").replace(" ", "")
        if not NIB_RE.match(value):
            raise forms.ValidationError("Informe um NIB valido.")
        return value


class StaffForm(forms.Form):
    first_name = forms.CharField(max_length=60, required=True, label="Nome")
    last_name = forms.CharField(max_length=80, required=False, label="Apelido")
    email = forms.EmailField(required=False, label="Email")
    phone = forms.CharField(max_length=30, required=False, label="Contacto")
    role_profile = forms.ModelChoiceField(
        queryset=TenantRole.objects.none(),
        required=True,
        label="Perfil/Role",
    )
    is_active = forms.BooleanField(required=False, label="Ativo")
    department = forms.CharField(max_length=120, required=False, label="Departamento")
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Notas",
    )
    extra_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(),
        required=False,
        label="Permissoes adicionais",
    )
    revoked_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(),
        required=False,
        label="Permissoes removidas",
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        label="Password temporaria",
    )

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        user_instance = kwargs.pop("user_instance", None)
        membership_instance = kwargs.pop("membership_instance", None)
        super().__init__(*args, **kwargs)
        self.user_instance = user_instance
        if business:
            self.fields["role_profile"].queryset = TenantRole.objects.filter(
                business=business, is_active=True
            ).order_by("name")
        perms = Permission.objects.all().order_by("content_type__app_label", "codename")
        self.fields["extra_permissions"].queryset = perms
        self.fields["revoked_permissions"].queryset = perms

        if user_instance:
            self.fields["email"].disabled = True
            self.fields["email"].required = False
            if user_instance.email:
                self.initial["email"] = user_instance.email
        if membership_instance:
            self.initial["role_profile"] = membership_instance.role_profile
            self.initial["is_active"] = membership_instance.is_active
            self.initial["department"] = membership_instance.department
            self.initial["notes"] = membership_instance.notes
            self.initial["extra_permissions"] = membership_instance.extra_permissions.all()
            self.initial["revoked_permissions"] = membership_instance.revoked_permissions.all()
        else:
            self.initial["is_active"] = True

        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.SelectMultiple):
                field.widget.attrs["class"] = "form-select tom-select"
                field.widget.attrs.setdefault("data-placeholder", "Selecione...")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"
            if name in self.errors:
                field.widget.attrs["class"] += " is-invalid"

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get("email") or "").strip().lower()
        phone = (cleaned.get("phone") or "").replace(" ", "")
        existing_email = ""
        existing_phone = ""
        if self.user_instance:
            existing_email = self.user_instance.email or ""
            if hasattr(self.user_instance, "profile"):
                existing_phone = self.user_instance.profile.phone or ""
        if not email and not phone and not existing_email and not existing_phone:
            raise forms.ValidationError("Informe um email ou contacto.")

        User = get_user_model()
        user_instance = getattr(self, "user_instance", None)
        if email:
            qs = User.objects.filter(email__iexact=email)
            if user_instance:
                qs = qs.exclude(pk=user_instance.pk)
            if qs.exists():
                self.add_error("email", "Este email ja esta em uso.")
        if phone:
            qs = UserProfile.objects.filter(phone=phone)
            if user_instance:
                qs = qs.exclude(user=user_instance)
            if qs.exists():
                self.add_error("phone", "Este contacto ja esta em uso.")
        cleaned["email"] = email
        cleaned["phone"] = phone
        return cleaned
