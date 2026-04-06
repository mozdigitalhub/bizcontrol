from django import forms
from django.forms import BaseFormSet, formset_factory

from finance.models import PaymentMethod, Supplier, Purchase
from inventory.models import GoodsReceipt, GoodsReceiptItem, StockMovement


class DecimalCommaField(forms.DecimalField):
    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace(" ", "").replace(",", ".")
        return super().to_python(value)


class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ["product", "movement_type", "quantity", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            _ = self.errors
        self.fields["quantity"].widget.attrs.update(
            {"inputmode": "numeric", "step": "1", "min": "1"}
        )
        self.fields["notes"].widget.attrs.update({"placeholder": "Notas (opcional)"})
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


class StockImportForm(forms.Form):
    file = forms.FileField(label="Ficheiro Excel (.xlsx)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs["class"] = "form-control"
        self.fields["file"].widget.attrs["accept"] = ".xlsx"


class GoodsReceiptForm(forms.ModelForm):
    cash_movement = forms.BooleanField(
        required=False, label="Esta rececao gera movimento de caixa?"
    )
    payment_method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.none(),
        required=False,
        label="Metodo de pagamento",
    )
    purchase = forms.ModelChoiceField(
        queryset=Purchase.objects.none(),
        required=False,
        label="Compra associada",
    )

    class Meta:
        model = GoodsReceipt
        fields = [
            "purchase",
            "supplier",
            "document_number",
            "document_date",
            "notes",
        ]
        widgets = {
            "document_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "purchase": "Compra associada",
            "supplier": "Fornecedor",
            "document_number": "Numero da guia/fatura",
            "document_date": "Data da guia/fatura",
            "notes": "Observacoes",
        }

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if business:
            self.fields["purchase"].queryset = Purchase.objects.filter(
                business=business, purchase_type=Purchase.TYPE_STOCK
            ).exclude(
                status=Purchase.STATUS_CANCELED
            ).order_by("-purchase_date")
            self.fields["supplier"].queryset = Supplier.objects.filter(
                business=business, is_active=True
            ).order_by("name")
            self.fields["payment_method"].queryset = PaymentMethod.objects.filter(
                business=business, is_active=True
            ).order_by("name")
        if self.is_bound:
            _ = self.errors
        self.fields["supplier"].required = True
        self.fields["document_number"].required = True
        self.fields["document_date"].required = True
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
        for select_name in ["supplier"]:
            if select_name in self.fields:
                self.fields[select_name].widget.attrs["data-dropdown-parent"] = "self"
                self.fields[select_name].widget.attrs.setdefault(
                    "data-placeholder", "Pesquisar fornecedor..."
                )
        if "purchase" in self.fields:
            self.fields["purchase"].widget.attrs["data-dropdown-parent"] = "self"
            self.fields["purchase"].widget.attrs.setdefault(
                "data-placeholder", "Selecionar compra..."
            )
        if "payment_method" in self.fields:
            self.fields["payment_method"].widget.attrs["data-dropdown-parent"] = "self"
            self.fields["payment_method"].widget.attrs.setdefault(
                "data-placeholder", "Selecionar metodo..."
            )

    def clean(self):
        cleaned = super().clean()
        purchase = cleaned.get("purchase")
        supplier = cleaned.get("supplier")
        if cleaned.get("cash_movement") and not cleaned.get("payment_method"):
            self.add_error("payment_method", "Selecione o metodo de pagamento.")
        if purchase:
            if purchase.purchase_type != Purchase.TYPE_STOCK:
                self.add_error("purchase", "A compra selecionada nao e de reposicao.")
            if supplier and purchase.supplier_id and supplier.id != purchase.supplier_id:
                self.add_error(
                    "supplier", "Fornecedor nao corresponde a compra selecionada."
                )
            if not supplier and purchase.supplier_id:
                cleaned["supplier"] = purchase.supplier
                if "supplier" in self.errors:
                    self.errors.pop("supplier")
        return cleaned


class GoodsReceiptItemForm(forms.ModelForm):
    unit_cost = DecimalCommaField(
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(),
        label="Preco de aquisicao",
    )
    sale_price = DecimalCommaField(
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(),
        label="Preco de revenda",
    )

    class Meta:
        model = GoodsReceiptItem
        fields = ["product", "quantity", "unit_cost", "sale_price"]
        labels = {
            "product": "Produto",
            "quantity": "Quantidade",
            "unit_cost": "Preco de aquisicao",
            "sale_price": "Preco de revenda",
        }

    def __init__(self, *args, **kwargs):
        products = kwargs.pop("products", None)
        super().__init__(*args, **kwargs)
        if products is not None:
            self.fields["product"].queryset = products
        self.fields["product"].required = False
        self.fields["quantity"].required = False
        self.fields["unit_cost"].required = False
        self.fields["sale_price"].required = False
        self.fields["quantity"].widget.attrs.update(
            {"inputmode": "numeric", "step": "1", "min": "1", "data-quantity": "true"}
        )
        self.fields["unit_cost"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "data-unit-cost": "true"}
        )
        self.fields["sale_price"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "data-sale-price": "true"}
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
            self.fields["product"].widget.attrs["data-dropdown-parent"] = "table"
            self.fields["product"].widget.attrs.pop("required", None)
            self.fields["product"].widget.attrs.setdefault(
                "data-placeholder", "Pesquisar produto..."
            )
        for field_name in ["quantity", "unit_cost", "sale_price"]:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.pop("required", None)

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product")
        quantity = cleaned.get("quantity")
        sale_price = cleaned.get("sale_price")
        unit_cost = cleaned.get("unit_cost")
        has_any = any(
            [
                product,
                quantity,
                sale_price,
                unit_cost is not None,
            ]
        )
        if has_any:
            if not product:
                self.add_error("product", "Selecione o produto.")
            if not quantity or quantity <= 0:
                self.add_error("quantity", "Quantidade obrigatoria.")
            if sale_price in [None, ""]:
                if product:
                    cleaned["sale_price"] = product.sale_price
        return cleaned


class GoodsReceiptItemBaseFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        has_item = False
        for form in self.forms:
            if not getattr(form, "cleaned_data", None):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            if form.cleaned_data.get("product") and form.cleaned_data.get("quantity"):
                has_item = True
                break
        if not has_item:
            raise forms.ValidationError("Adicione pelo menos um produto.")


GoodsReceiptItemFormSet = formset_factory(
    GoodsReceiptItemForm, formset=GoodsReceiptItemBaseFormSet, extra=1, can_delete=True
)
