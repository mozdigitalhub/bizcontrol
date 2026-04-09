from django import forms
from django.forms import BaseFormSet, formset_factory

from customers.models import Customer
from finance.models import CashMovement, PaymentMethod
from food.models import (
    DeliveryInfo,
    FoodIngredient,
    IngredientStockEntry,
    IngredientStockEntryItem,
    MenuCategory,
    MenuItem,
    MenuItemRecipe,
    Order,
    OrderItem,
)


class OrderForm(forms.ModelForm):
    payment_method = forms.ChoiceField(required=False, label="Metodo de pagamento")

    class Meta:
        model = Order
        fields = ["customer", "channel", "notes"]
        labels = {
            "customer": "Cliente",
            "channel": "Canal",
            "notes": "Observacoes",
        }

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        self.fields["customer"].required = False
        if business:
            self.fields["customer"].queryset = Customer.objects.filter(
                business=business
            ).order_by("name")
            methods = PaymentMethod.objects.filter(
                business=business, is_active=True
            ).order_by("name")
            if methods.exists():
                self.fields["payment_method"].choices = [
                    (m.code, m.name) for m in methods
                ]
            else:
                self.fields["payment_method"].choices = CashMovement.METHOD_CHOICES
            pay_before = business.feature_enabled("pay_before_service")
            self.fields["payment_method"].required = bool(pay_before)
        else:
            self.fields["payment_method"].choices = CashMovement.METHOD_CHOICES

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"
        if "customer" in self.fields:
            self.fields["customer"].widget.attrs["data-placeholder"] = "Selecionar cliente..."
            self.fields["customer"].widget.attrs["data-dropdown-parent"] = "form"
        self.fields["payment_method"].widget.attrs["data-placeholder"] = "Selecionar metodo..."
        if "channel" in self.fields:
            self.fields["channel"].widget.attrs["data-dropdown-parent"] = "form"


class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ["menu_item", "quantity", "unit_price", "notes"]
        labels = {
            "menu_item": "Produto",
            "quantity": "Qtd",
            "unit_price": "Preco",
            "notes": "Obs",
        }

    def __init__(self, *args, **kwargs):
        products = kwargs.pop("products", None)
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if products is not None:
            self.fields["menu_item"].queryset = products
        self.fields["quantity"].widget.attrs.update(
            {"inputmode": "numeric", "step": "1", "min": "1", "data-order-qty": "true"}
        )
        self.fields["unit_price"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0", "data-order-price": "true"}
        )
        self.fields["notes"].widget.attrs.update({"data-order-notes": "true"})
        self.fields["menu_item"].required = False
        self.fields["quantity"].required = False
        self.fields["unit_price"].required = False
        self.fields["notes"].required = False
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"
        if "menu_item" in self.fields:
            self.fields["menu_item"].widget.attrs["data-placeholder"] = "Pesquisar item..."
            self.fields["menu_item"].widget.attrs["data-dropdown-parent"] = "table"


class OrderItemBaseFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        has_any = False
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            product = form.cleaned_data.get("menu_item")
            quantity = form.cleaned_data.get("quantity")
            price = form.cleaned_data.get("unit_price")
            if product or quantity or price:
                has_any = True
            if product and (not quantity or quantity <= 0):
                raise forms.ValidationError("Informe a quantidade dos itens.")
        if not has_any:
            raise forms.ValidationError("Adicione pelo menos um item.")


OrderItemFormSet = formset_factory(
    OrderItemForm, formset=OrderItemBaseFormSet, extra=1, can_delete=True
)


class IngredientForm(forms.ModelForm):
    class Meta:
        model = FoodIngredient
        fields = ["name", "unit", "cost_price", "reorder_level", "is_active"]
        labels = {
            "name": "Nome",
            "unit": "Unidade",
            "cost_price": "Preco de custo",
            "reorder_level": "Stock minimo",
            "is_active": "Ativo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class IngredientStockEntryForm(forms.ModelForm):
    class Meta:
        model = IngredientStockEntry
        fields = ["supplier_name", "reference_number", "entry_date", "notes"]
        labels = {
            "supplier_name": "Fornecedor",
            "reference_number": "Referencia",
            "entry_date": "Data",
            "notes": "Observacoes",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class IngredientStockEntryItemForm(forms.ModelForm):
    class Meta:
        model = IngredientStockEntryItem
        fields = ["ingredient", "quantity", "unit_cost"]
        labels = {
            "ingredient": "Ingrediente",
            "quantity": "Qtd",
            "unit_cost": "Custo",
        }

    def __init__(self, *args, **kwargs):
        ingredients = kwargs.pop("ingredients", None)
        super().__init__(*args, **kwargs)
        if ingredients is not None:
            self.fields["ingredient"].queryset = ingredients
        self.fields["quantity"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.001", "min": "0"}
        )
        self.fields["unit_cost"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0"}
        )
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
                field.widget.attrs["data-dropdown-parent"] = "table"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class IngredientStockEntryBaseFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        has_any = False
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            ingredient = form.cleaned_data.get("ingredient")
            quantity = form.cleaned_data.get("quantity")
            if ingredient or quantity:
                has_any = True
            if ingredient and (not quantity or quantity <= 0):
                raise forms.ValidationError("Informe a quantidade recebida.")
        if not has_any:
            raise forms.ValidationError("Adicione pelo menos um ingrediente.")


IngredientStockEntryItemFormSet = formset_factory(
    IngredientStockEntryItemForm, formset=IngredientStockEntryBaseFormSet, extra=1, can_delete=True
)


class MenuCategoryForm(forms.ModelForm):
    class Meta:
        model = MenuCategory
        fields = ["name", "is_active"]
        labels = {"name": "Nome", "is_active": "Ativo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = [
            "name",
            "description",
            "category",
            "item_type",
            "selling_price",
            "ingredient",
            "image",
            "is_active",
        ]
        labels = {
            "name": "Nome",
            "description": "Descricao",
            "category": "Categoria",
            "item_type": "Tipo",
            "selling_price": "Preco de venda",
            "ingredient": "Ingrediente (bebida)",
            "image": "Imagem",
            "is_active": "Ativo",
        }

    def __init__(self, *args, **kwargs):
        ingredients = kwargs.pop("ingredients", None)
        categories = kwargs.pop("categories", None)
        super().__init__(*args, **kwargs)
        if ingredients is not None:
            self.fields["ingredient"].queryset = ingredients
        if categories is not None:
            self.fields["category"].queryset = categories
        self.fields["selling_price"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0"}
        )
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
                field.widget.attrs["data-dropdown-parent"] = "form"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class MenuItemRecipeForm(forms.ModelForm):
    class Meta:
        model = MenuItemRecipe
        fields = ["ingredient", "quantity", "unit"]
        labels = {"ingredient": "Ingrediente", "quantity": "Qtd", "unit": "Unidade"}

    def __init__(self, *args, **kwargs):
        ingredients = kwargs.pop("ingredients", None)
        super().__init__(*args, **kwargs)
        if ingredients is not None:
            self.fields["ingredient"].queryset = ingredients
        self.fields["quantity"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.001", "min": "0"}
        )
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
                field.widget.attrs["data-dropdown-parent"] = "table"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class MenuItemRecipeBaseFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        has_any = False
        seen = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            ingredient = form.cleaned_data.get("ingredient")
            quantity = form.cleaned_data.get("quantity")
            if ingredient:
                if ingredient.id in seen:
                    raise forms.ValidationError("Ingrediente repetido na receita.")
                seen.add(ingredient.id)
            if ingredient or quantity:
                has_any = True
            if ingredient and (not quantity or quantity <= 0):
                raise forms.ValidationError("Informe a quantidade da receita.")
        if not has_any:
            raise forms.ValidationError("Adicione pelo menos um ingrediente.")


MenuItemRecipeFormSet = formset_factory(
    MenuItemRecipeForm, formset=MenuItemRecipeBaseFormSet, extra=1, can_delete=True
)

class DeliveryInfoForm(forms.ModelForm):
    class Meta:
        model = DeliveryInfo
        fields = ["address", "phone", "delivery_fee", "driver_name", "notes"]
        labels = {
            "address": "Endereço",
            "phone": "Contacto",
            "delivery_fee": "Taxa de entrega",
            "driver_name": "Responsavel",
            "notes": "Observacoes",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"
