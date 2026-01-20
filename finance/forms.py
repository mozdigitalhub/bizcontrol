from django import forms
from django.forms import formset_factory

from catalog.models import Product
from finance.models import Expense, ExpenseCategory, Purchase, PurchaseItem, Supplier


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "phone", "email", "address", "notes", "is_active"]
        widgets = {
            "address": forms.TextInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "name": "Fornecedor",
            "phone": "Telefone",
            "email": "Email",
            "address": "Endereco",
            "notes": "Notas",
            "is_active": "Ativo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            _ = self.errors
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
                if field.required:
                    field.widget.attrs["required"] = "required"
                if name in self.errors:
                    field.widget.attrs["class"] += " is-invalid"


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["name", "is_active"]
        labels = {"name": "Categoria", "is_active": "Ativo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            _ = self.errors
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
                if field.required:
                    field.widget.attrs["required"] = "required"
                if name in self.errors:
                    field.widget.attrs["class"] += " is-invalid"


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = [
            "supplier",
            "purchase_type",
            "purchase_date",
            "payment_method",
            "internal_description",
            "internal_amount",
            "notes",
        ]
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "supplier": "Fornecedor",
            "purchase_type": "Tipo de registo",
            "purchase_date": "Data da compra",
            "payment_method": "Metodo de pagamento",
            "internal_description": "Descricao",
            "internal_amount": "Valor",
            "notes": "Observacoes",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["internal_description"].required = False
        self.fields["internal_amount"].required = False
        self.fields["internal_amount"].widget.attrs.update(
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
        for select_name in ["category", "payment_method"]:
            if select_name in self.fields:
                self.fields[select_name].widget.attrs["data-dropdown-parent"] = "modal"
        if "purchase_type" in self.fields:
            self.fields["purchase_type"].widget.attrs["class"] = "form-select"
            if self.fields["purchase_type"].required:
                self.fields["purchase_type"].widget.attrs["required"] = "required"
        for select_name in ["supplier", "payment_method"]:
            if select_name in self.fields:
                self.fields[select_name].widget.attrs["data-dropdown-parent"] = "modal"
        for field_name in ["internal_description", "internal_amount"]:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.pop("required", None)


class PurchaseItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = ["product", "quantity", "unit_cost"]
        labels = {
            "product": "Produto",
            "quantity": "Quantidade",
            "unit_cost": "Preco unitario",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].required = False
        self.fields["quantity"].required = False
        self.fields["unit_cost"].required = False
        self.fields["quantity"].widget.attrs.update(
            {"inputmode": "numeric", "step": "1", "min": "1", "data-quantity": "true"}
        )
        self.fields["unit_cost"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "data-unit-cost": "true"}
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
            self.fields["product"].widget.attrs["data-dropdown-parent"] = "modal"
            self.fields["product"].widget.attrs.pop("required", None)
        if "quantity" in self.fields:
            self.fields["quantity"].widget.attrs.pop("required", None)
        if "unit_cost" in self.fields:
            self.fields["unit_cost"].widget.attrs.pop("required", None)


PurchaseItemFormSet = formset_factory(PurchaseItemForm, extra=1, can_delete=True)


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            "category",
            "title",
            "amount",
            "expense_date",
            "payment_method",
            "attachment",
            "notes",
        ]
        widgets = {
            "expense_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "category": "Categoria",
            "title": "Nome da despesa",
            "amount": "Valor",
            "expense_date": "Data",
            "payment_method": "Metodo de pagamento",
            "attachment": "Comprovativo",
            "notes": "Observacoes",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            _ = self.errors
        self.fields["amount"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0"}
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
