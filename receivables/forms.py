from django import forms

from receivables.models import Payment


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0.01", "data-money": "true"}
        )
        self.fields["method"].widget.attrs.update(
            {"data-placeholder": "Selecione o metodo...", "data-dropdown-parent": "self"}
        )
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
