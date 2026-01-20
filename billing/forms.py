from django import forms

from billing.models import InvoicePayment


class InvoicePaymentForm(forms.ModelForm):
    class Meta:
        model = InvoicePayment
        fields = ["amount", "method", "notes"]
        labels = {
            "amount": "Valor do pagamento",
            "method": "Metodo de pagamento",
            "notes": "Observacoes",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0.01", "data-money": "true"}
        )
        self.fields["method"].widget.attrs.update(
            {"data-placeholder": "Selecione o metodo...", "data-dropdown-parent": "self"}
        )
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"

