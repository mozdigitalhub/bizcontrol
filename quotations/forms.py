from django import forms
from django.forms import formset_factory

from quotations.models import Quotation, QuotationItem


class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = [
            "customer",
            "valid_until",
            "notes",
            "discount_type",
            "discount_value",
        ]
        widgets = {
            "valid_until": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "customer": "Cliente",
            "valid_until": "Validade",
            "notes": "Observacoes",
            "discount_type": "Tipo de desconto",
            "discount_value": "Desconto",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].required = True
        self.fields["discount_value"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0"}
        )
        if self.is_bound:
            _ = self.errors
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
        for select_name in ["customer", "discount_type"]:
            if select_name in self.fields:
                self.fields[select_name].widget.attrs["data-dropdown-parent"] = "form"


class QuotationItemForm(forms.ModelForm):
    class Meta:
        model = QuotationItem
        fields = ["product", "quantity", "unit_price"]
        labels = {
            "product": "Produto/Servico",
            "quantity": "Quantidade",
            "unit_price": "Preco unitario",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].required = False
        self.fields["quantity"].required = False
        self.fields["unit_price"].required = False
        self.fields["quantity"].widget.attrs.update(
            {"inputmode": "numeric", "step": "1", "min": "1", "data-quantity": "true"}
        )
        self.fields["unit_price"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "data-unit-price": "true"}
        )
        if self.is_bound:
            _ = self.errors
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
        if "product" in self.fields:
            self.fields["product"].widget.attrs["data-dropdown-parent"] = "form"
            self.fields["product"].widget.attrs.pop("required", None)
        if "quantity" in self.fields:
            self.fields["quantity"].widget.attrs.pop("required", None)
        if "unit_price" in self.fields:
            self.fields["unit_price"].widget.attrs.pop("required", None)


QuotationItemFormSet = formset_factory(QuotationItemForm, extra=1, can_delete=True)
