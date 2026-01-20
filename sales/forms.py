from decimal import Decimal

from django import forms

from sales.models import Sale, SaleItem


class SaleUpdateForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = [
            "customer",
            "sale_type",
            "delivery_mode",
            "is_credit",
            "discount_type",
            "discount_value",
            "payment_method",
            "payment_due_date",
        ]
        labels = {
            "customer": "Cliente",
            "sale_type": "Tipo de venda",
            "delivery_mode": "Levantamento",
            "is_credit": "Fiado",
            "discount_type": "Tipo de desconto",
            "discount_value": "Desconto",
            "payment_method": "Metodo de pagamento",
            "payment_due_date": "Data prevista de pagamento",
        }

    def __init__(self, *args, **kwargs):
        self.allow_credit = kwargs.pop("allow_credit", True)
        self.read_only = kwargs.pop("read_only", False)
        self.relaxed = kwargs.pop("relaxed", False)
        super().__init__(*args, **kwargs)
        self.fields["discount_value"].required = False
        self.fields["payment_method"].required = False
        self.fields["payment_due_date"].required = False
        self.fields["customer"].empty_label = "Selecione um cliente"
        self.fields["customer"].widget.attrs.update(
            {"data-placeholder": "Pesquisar cliente...", "data-dropdown-parent": "self"}
        )
        self.fields["discount_value"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "data-money": "true"}
        )
        self.fields["payment_method"].widget.attrs.update(
            {
                "data-placeholder": "Selecione o metodo...",
                "data-dropdown-parent": "self",
            }
        )
        if "payment_method" in self.fields:
            base_choices = [
                choice
                for choice in Sale.METHOD_CHOICES
                if choice[0] != Sale.METHOD_OTHER
            ]
            if self.instance and self.instance.payment_method == Sale.METHOD_OTHER:
                base_choices = Sale.METHOD_CHOICES
            self.fields["payment_method"].choices = base_choices
        self.fields["sale_type"].widget.attrs.update(
            {"data-placeholder": "Tipo de venda...", "data-dropdown-parent": "self"}
        )
        self.fields["delivery_mode"].widget.attrs.update(
            {"data-placeholder": "Levantamento...", "data-dropdown-parent": "self"}
        )
        self.fields["payment_due_date"].widget = forms.DateInput(attrs={"type": "date"})
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
                field.widget.attrs.setdefault("data-dropdown-parent", "self")
            else:
                field.widget.attrs["class"] = "form-control"
        self.fields["payment_method"].widget.attrs["required"] = False
        if "delivery_mode" in self.fields:
            self.fields["delivery_mode"].required = False
        if not self.allow_credit:
            self.fields["is_credit"].disabled = True
            self.fields["payment_due_date"].disabled = True
        if "sale_type" in self.fields:
            self.fields["sale_type"].required = True
        if self.read_only:
            for field in self.fields.values():
                field.disabled = True
                field.required = False

    def clean(self):
        cleaned = super().clean()
        discount_type = cleaned.get("discount_type")
        discount_value = cleaned.get("discount_value") or Decimal("0")
        sale_type = cleaned.get("sale_type")
        delivery_mode = cleaned.get("delivery_mode")
        is_credit = cleaned.get("is_credit")
        payment_method = cleaned.get("payment_method")
        payment_due_date = cleaned.get("payment_due_date")
        raw_discount_value = str(self.data.get("discount_value", "")).strip()
        if sale_type == Sale.SALE_TYPE_DEPOSIT:
            cleaned["is_credit"] = False
            cleaned["payment_due_date"] = None
            cleaned["delivery_mode"] = Sale.DELIVERY_SCHEDULED
            is_credit = False
            payment_due_date = None
            delivery_mode = Sale.DELIVERY_SCHEDULED
        if not self.allow_credit:
            cleaned["is_credit"] = False
            cleaned["payment_due_date"] = None
            is_credit = False
            payment_due_date = None
        if is_credit:
            cleaned["sale_type"] = Sale.SALE_TYPE_NORMAL
            cleaned["delivery_mode"] = Sale.DELIVERY_IMMEDIATE
            cleaned["payment_method"] = ""
            cleaned["discount_type"] = Sale.DISCOUNT_NONE
            cleaned["discount_value"] = Decimal("0")
            sale_type = Sale.SALE_TYPE_NORMAL
            delivery_mode = Sale.DELIVERY_IMMEDIATE
            payment_method = ""
            discount_type = Sale.DISCOUNT_NONE
            discount_value = Decimal("0")
        if sale_type == Sale.SALE_TYPE_DEPOSIT and is_credit:
            self.add_error("sale_type", "Deposito nao pode ser fiado.")
        if discount_value < 0:
            self.add_error("discount_value", "O desconto nao pode ser negativo.")
        if discount_type == Sale.DISCOUNT_NONE:
            cleaned["discount_value"] = Decimal("0")
        elif not raw_discount_value or discount_value <= 0:
            cleaned["discount_type"] = Sale.DISCOUNT_NONE
            cleaned["discount_value"] = Decimal("0")
            discount_type = Sale.DISCOUNT_NONE
            discount_value = Decimal("0")
        if discount_type == Sale.DISCOUNT_PERCENT and discount_value > Decimal("100"):
            self.add_error("discount_value", "A percentagem maxima e 100.")
        if not self.relaxed:
            if sale_type != Sale.SALE_TYPE_DEPOSIT and not is_credit and not payment_method:
                self.add_error("payment_method", "Selecione o metodo de pagamento.")
            if is_credit and not payment_due_date:
                self.add_error("payment_due_date", "Indique a data prevista de pagamento.")
        if not is_credit:
            cleaned["payment_due_date"] = None
        if sale_type == Sale.SALE_TYPE_DEPOSIT:
            cleaned["payment_method"] = payment_method or ""
        if not delivery_mode:
            cleaned["delivery_mode"] = Sale.DELIVERY_IMMEDIATE
        return cleaned


class SaleItemForm(forms.ModelForm):
    class Meta:
        model = SaleItem
        fields = ["product", "quantity"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].empty_label = "Selecione um produto"
        self.fields["product"].widget.attrs.update(
            {"data-placeholder": "Pesquisar produto...", "data-dropdown-parent": "self"}
        )
        self.fields["quantity"].widget.attrs.update(
            {"inputmode": "numeric", "step": "1", "min": "1"}
        )
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
                field.widget.attrs.setdefault("data-dropdown-parent", "self")
            else:
                field.widget.attrs["class"] = "form-control"
