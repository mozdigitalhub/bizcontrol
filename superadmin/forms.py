from django import forms
from django.contrib.auth import get_user_model

from superadmin.models import (
    PlatformAlert,
    PlatformSetting,
    SubscriptionPlan,
    SupportTicket,
    TenantAdminNote,
    TenantSubscription,
)
from tenants.models import Business


class TenantAdminNoteForm(forms.ModelForm):
    class Meta:
        model = TenantAdminNote
        fields = ["note_type", "note"]
        labels = {"note_type": "Tipo", "note": "Nota interna"}
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"


class SubscriptionPlanForm(forms.ModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = [
            "code",
            "name",
            "description",
            "price_monthly",
            "billing_cycle_months",
            "trial_days",
            "max_users",
            "max_branches",
            "is_active",
            "is_default",
            "feature_flags",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "feature_flags": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", "") == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"


class PlatformSettingForm(forms.ModelForm):
    class Meta:
        model = PlatformSetting
        fields = ["key", "value", "description", "is_public"]
        widgets = {
            "value": forms.Textarea(attrs={"rows": 3}),
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if getattr(field.widget, "input_type", "") == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"


class PlatformAlertForm(forms.ModelForm):
    class Meta:
        model = PlatformAlert
        fields = [
            "business",
            "level",
            "title",
            "message",
            "is_active",
            "starts_at",
            "ends_at",
        ]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 3}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["business"].queryset = Business.objects.order_by("name")
        self.fields["business"].required = False
        for field in self.fields.values():
            if getattr(field.widget, "input_type", "") == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ["business", "subject", "message", "status", "assigned_to"]
        widgets = {"message": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["business"].required = False
        self.fields["business"].queryset = Business.objects.order_by("name")
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"


class TenantSubscriptionForm(forms.ModelForm):
    class Meta:
        model = TenantSubscription
        fields = [
            "plan",
            "status",
            "trial_ends_at",
            "ends_at",
            "next_renewal_at",
            "auto_renew",
            "payment_proof_status",
            "payment_reference",
            "notes",
        ]
        widgets = {
            "trial_ends_at": forms.DateInput(attrs={"type": "date"}),
            "ends_at": forms.DateInput(attrs={"type": "date"}),
            "next_renewal_at": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if getattr(field.widget, "input_type", "") == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"


class SuperAdminTenantCreateForm(forms.Form):
    name = forms.CharField(max_length=200, label="Nome comercial")
    legal_name = forms.CharField(max_length=200, required=False, label="Razao social")
    business_type = forms.ChoiceField(
        choices=Business.BUSINESS_TYPE_CHOICES,
        label="Tipo de negocio",
    )
    nuit = forms.CharField(max_length=30, required=False, label="NUIT")
    commercial_registration = forms.CharField(
        max_length=60,
        required=False,
        label="Registo comercial",
    )
    email = forms.EmailField(required=False, label="Email do negocio")
    phone = forms.CharField(max_length=30, required=False, label="Telefone do negocio")
    country = forms.CharField(max_length=80, required=False, label="Pais", initial="Mozambique")
    city = forms.CharField(max_length=80, required=False, label="Cidade")
    address = forms.CharField(
        required=False,
        label="Endereço",
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    owner_full_name = forms.CharField(max_length=150, label="Nome do owner")
    owner_email = forms.EmailField(label="Email do owner")
    owner_phone = forms.CharField(max_length=30, required=False, label="Telefone do owner")
    send_pending_email = forms.BooleanField(
        required=False,
        initial=True,
        label="Enviar email de registo pendente ao owner",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if getattr(field.widget, "input_type", "") == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean_owner_email(self):
        email = (self.cleaned_data.get("owner_email") or "").strip().lower()
        user_model = get_user_model()
        if user_model.objects.filter(username__iexact=email).exists() or user_model.objects.filter(
            email__iexact=email
        ).exists():
            raise forms.ValidationError("Ja existe um utilizador com este email.")
        return email

    def clean_nuit(self):
        nuit = (self.cleaned_data.get("nuit") or "").strip().replace(" ", "")
        if not nuit:
            return ""
        if not nuit.isdigit() or len(nuit) != 9:
            raise forms.ValidationError("NUIT deve ter 9 digitos.")
        if Business.objects.filter(nuit=nuit).exists():
            raise forms.ValidationError("Este NUIT ja esta registado.")
        return nuit
