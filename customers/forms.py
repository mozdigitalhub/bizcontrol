from django import forms

from customers.models import Customer


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "customer_type",
            "name",
            "phone",
            "nuit",
            "credit_limit",
            "email",
            "address",
            "notes",
        ]
        labels = {
            "customer_type": "Tipo de cliente",
            "nuit": "NUIT",
            "credit_limit": "Limite de credito",
        }

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if self.is_bound:
            _ = self.errors
        self.fields["customer_type"].widget.attrs.update(
            {"data-placeholder": "Selecione o tipo..."}
        )
        self.fields["name"].widget.attrs.update({"placeholder": "Nome completo"})
        self.fields["phone"].widget.attrs.update({"placeholder": "Telefone"})
        self.fields["nuit"].widget.attrs.update({"placeholder": "NUIT (empresa)"})
        self.fields["credit_limit"].widget.attrs.update(
            {"placeholder": "Limite de credito (opcional)", "inputmode": "decimal", "step": "0.01", "min": "0"}
        )
        self.fields["email"].widget.attrs.update({"placeholder": "Email (opcional)"})
        self.fields["address"].widget.attrs.update({"placeholder": "Endereço (opcional)"})
        self.fields["notes"].widget.attrs.update({"placeholder": "Notas (opcional)"})
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
                field.widget.attrs.setdefault("data-dropdown-parent", "self")
            else:
                field.widget.attrs["class"] = "form-control"
                if field.required:
                    field.widget.attrs["required"] = "required"
                if name in self.errors:
                    field.widget.attrs["class"] += " is-invalid"

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip().replace(" ", "")
        if not phone:
            raise forms.ValidationError("Informe o telefone do cliente.")
        if not self.business:
            return phone
        qs = Customer.objects.filter(business=self.business, phone__iexact=phone)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ja existe um cliente com este telefone.")
        return phone

    def clean(self):
        cleaned = super().clean()
        customer_type = cleaned.get("customer_type")
        nuit = (cleaned.get("nuit") or "").strip().replace(" ", "")
        if nuit:
            cleaned["nuit"] = nuit
        if customer_type == Customer.TYPE_COMPANY and not nuit:
            self.add_error("nuit", "NUIT e obrigatorio para clientes empresa.")
        return cleaned


class QuickCustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["customer_type", "name", "phone", "nuit"]
        labels = {
            "customer_type": "Tipo de cliente",
            "name": "Nome do cliente",
            "phone": "Telefone",
            "nuit": "NUIT",
        }

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if self.is_bound:
            _ = self.errors
        self.fields["customer_type"].widget.attrs.update(
            {"data-placeholder": "Tipo de cliente..."}
        )
        self.fields["name"].widget.attrs.update({"placeholder": "Nome do cliente"})
        self.fields["phone"].widget.attrs.update({"placeholder": "Telefone"})
        self.fields["nuit"].widget.attrs.update({"placeholder": "NUIT (empresa)"})
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
                field.widget.attrs.setdefault("data-dropdown-parent", "self")
            else:
                field.widget.attrs["class"] = "form-control"
                if field.required:
                    field.widget.attrs["required"] = "required"
                if name in self.errors:
                    field.widget.attrs["class"] += " is-invalid"

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip().replace(" ", "")
        if not phone:
            raise forms.ValidationError("Informe o telefone do cliente.")
        if not self.business:
            return phone
        qs = Customer.objects.filter(business=self.business, phone__iexact=phone)
        if qs.exists():
            raise forms.ValidationError("Ja existe um cliente com este telefone.")
        return phone

    def clean(self):
        cleaned = super().clean()
        customer_type = cleaned.get("customer_type")
        nuit = (cleaned.get("nuit") or "").strip().replace(" ", "")
        if nuit:
            cleaned["nuit"] = nuit
        if customer_type == Customer.TYPE_COMPANY and not nuit:
            self.add_error("nuit", "NUIT e obrigatorio para clientes empresa.")
        return cleaned
