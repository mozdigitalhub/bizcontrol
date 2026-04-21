from decimal import Decimal

from django import forms

from catalog.models import Category, Product, ProductVariant


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "is_active"]
        labels = {
            "name": "Categoria",
            "is_active": "Ativo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            _ = self.errors
        self.fields["name"].widget.attrs.update({"placeholder": "Nome da categoria"})
        for name, field in self.fields.items():
            if field.widget.input_type == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
                if field.required:
                    field.widget.attrs["required"] = "required"
                if name in self.errors:
                    field.widget.attrs["class"] += " is-invalid"


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "sku",
            "category",
            "unit_of_measure",
            "stock_control_mode",
            "cost_price",
            "sale_price",
            "reorder_level",
            "is_active",
        ]
        labels = {
            "name": "Nome",
            "sku": "SKU",
            "category": "Categoria",
            "unit_of_measure": "Unidade de medida",
            "stock_control_mode": "Modo de controlo de stock",
            "cost_price": "Preco de custo",
            "sale_price": "Preco de venda",
            "reorder_level": "Nivel minimo de stock",
            "is_active": "Ativo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            _ = self.errors
        self.fields["cost_price"].required = False
        self.fields["name"].widget.attrs.update({"placeholder": "Nome do produto"})
        self.fields["sku"].widget.attrs.update({"placeholder": "SKU (opcional)"})
        self.fields["category"].widget.attrs.update(
            {
                "data-placeholder": "Pesquisar categoria...",
                "data-dropdown-parent": "self",
            }
        )
        self.fields["cost_price"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "data-money": "true"}
        )
        self.fields["sale_price"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "data-money": "true"}
        )
        self.fields["reorder_level"].widget.attrs.update(
            {"inputmode": "numeric", "step": "1", "min": "0"}
        )
        for name, field in self.fields.items():
            if field.widget.input_type == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
                if field.required:
                    field.widget.attrs["required"] = "required"
                if name in self.errors:
                    field.widget.attrs["class"] += " is-invalid"

    def clean_cost_price(self):
        value = self.cleaned_data.get("cost_price")
        if value in [None, ""]:
            return Decimal("0")
        return value


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = [
            "name",
            "size",
            "color",
            "sku",
            "sale_price",
            "stock_qty",
            "reorder_level",
            "is_active",
        ]
        labels = {
            "name": "Nome da variacao",
            "size": "Tamanho",
            "color": "Cor",
            "sku": "SKU",
            "sale_price": "Preco de venda",
            "stock_qty": "Stock",
            "reorder_level": "Nivel minimo",
            "is_active": "Ativa",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sale_price"].required = False
        self.fields["sale_price"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0"}
        )
        self.fields["stock_qty"].widget.attrs.update(
            {"inputmode": "numeric", "step": "1"}
        )
        self.fields["reorder_level"].widget.attrs.update(
            {"inputmode": "numeric", "step": "1", "min": "0"}
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
