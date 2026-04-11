from django import forms
from django.utils import timezone

from receivables.models import Payment


class PaymentForm(forms.ModelForm):
    paid_at = forms.DateTimeField(
        required=False,
        label="Data do pagamento",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )

    class Meta:
        model = Payment
        fields = ["amount", "method", "notes"]

    def __init__(self, *args, **kwargs):
        self.allow_backdated_payment = kwargs.pop("allow_backdated_payment", False)
        self.initial_paid_at = kwargs.pop("initial_paid_at", None)
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0.01", "data-money": "true"}
        )
        self.fields["method"].widget.attrs.update(
            {"data-placeholder": "Selecione o metodo...", "data-dropdown-parent": "self"}
        )
        if self.allow_backdated_payment:
            if self.initial_paid_at:
                self.initial["paid_at"] = timezone.localtime(
                    self.initial_paid_at
                ).strftime("%Y-%m-%dT%H:%M")
        else:
            self.fields.pop("paid_at", None)
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"
