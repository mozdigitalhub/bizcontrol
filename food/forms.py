from django import forms
from django.forms import BaseFormSet, formset_factory
from django.utils import timezone

from customers.models import Customer
from finance.models import CashMovement, PaymentMethod
from food.models import (
    DeliveryInfo,
    FoodExtra,
    FoodIngredient,
    FoodIngredientCategory,
    FoodIngredientUnit,
    IngredientMovement,
    IngredientStockEntry,
    IngredientStockEntryItem,
    MenuCategory,
    MenuItem,
    MenuItemType,
    MenuItemRecipe,
    Order,
    OrderItem,
    OrderPayment,
    RestaurantTable,
)
from food.services import (
    DEFAULT_INGREDIENT_CATEGORIES,
    DEFAULT_INGREDIENT_UNITS,
    ensure_default_ingredient_options,
    ensure_default_menu_options,
)


class OrderForm(forms.ModelForm):
    payment_method = forms.ChoiceField(required=False, label="Metodo de pagamento")

    class Meta:
        model = Order
        fields = ["customer", "channel", "table", "notes"]
        labels = {
            "customer": "Cliente",
            "channel": "Canal",
            "table": "Mesa",
            "notes": "Observacoes",
        }

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        self.fields["customer"].required = False
        self.fields["table"].required = False
        if business:
            self.fields["customer"].queryset = Customer.objects.filter(
                business=business
            ).order_by("name")
            self.fields["customer"].label_from_instance = (
                lambda obj: f"{obj.name} - {obj.phone}" if obj.phone else obj.name
            )
            use_tables = business.feature_enabled("use_tables")
            if use_tables:
                self.fields["table"].queryset = business.restaurant_tables.filter(
                    is_active=True
                ).order_by("name")
            else:
                self.fields["table"].widget = forms.HiddenInput()
            methods = PaymentMethod.objects.filter(
                business=business, is_active=True
            ).order_by("name")
            method_choices = (
                [(m.code, m.name) for m in methods]
                if methods.exists()
                else list(CashMovement.METHOD_CHOICES)
            )
            self.fields["payment_method"].choices = [("", "Selecionar...")] + method_choices
            pay_before = business.feature_enabled("pay_before_service")
            if business.business_type == business.BUSINESS_BURGER:
                pay_before = False
            self.fields["payment_method"].required = bool(pay_before)
            self.initial.setdefault("payment_method", "")
        else:
            self.fields["payment_method"].choices = [
                ("", "Selecionar...")
            ] + list(CashMovement.METHOD_CHOICES)

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.HiddenInput):
                continue
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"
        if "customer" in self.fields:
            self.fields["customer"].widget.attrs["data-placeholder"] = "Pesquisar por nome ou nr..."
            self.fields["customer"].widget.attrs["data-dropdown-parent"] = "self"
        if "table" in self.fields and not isinstance(
            self.fields["table"].widget, forms.HiddenInput
        ):
            self.fields["table"].widget.attrs["data-placeholder"] = "Selecionar mesa..."
            self.fields["table"].widget.attrs["data-dropdown-parent"] = "form"
        self.fields["payment_method"].widget.attrs["data-placeholder"] = "Selecionar metodo..."
        if "channel" in self.fields:
            self.fields["channel"].widget.attrs["data-dropdown-parent"] = "form"


class OrderItemForm(forms.ModelForm):
    complements = forms.ModelMultipleChoiceField(
        queryset=MenuItem.objects.none(),
        required=False,
        label="Complementos",
    )
    beverages = forms.ModelMultipleChoiceField(
        queryset=MenuItem.objects.none(),
        required=False,
        label="Bebidas",
    )

    class Meta:
        model = OrderItem
        fields = ["menu_item", "quantity", "unit_price", "notes"]
        labels = {
            "menu_item": "Prato",
            "quantity": "Qtd",
            "unit_price": "Preco base",
            "notes": "Observacoes",
        }

    def __init__(self, *args, **kwargs):
        products = kwargs.pop("products", None)
        complement_items = kwargs.pop("complement_items", None)
        beverage_items = kwargs.pop("beverage_items", None)
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if products is not None:
            self.fields["menu_item"].queryset = products
        if complement_items is not None:
            self.fields["complements"].queryset = complement_items
        elif business is not None and business.business_type == business.BUSINESS_BURGER:
            self.fields["complements"].queryset = (
                MenuItem.objects.filter(
                    business=business,
                    is_active=True,
                    item_type=MenuItem.TYPE_COMPLEMENT,
                )
                .order_by("name")
            )
        if beverage_items is not None:
            self.fields["beverages"].queryset = beverage_items
        elif business is not None and business.business_type == business.BUSINESS_BURGER:
            self.fields["beverages"].queryset = (
                MenuItem.objects.filter(
                    business=business,
                    is_active=True,
                    item_type=MenuItem.TYPE_BEVERAGE,
                    ingredient__usage_type__in=[
                        FoodIngredient.USAGE_SELLABLE,
                        FoodIngredient.USAGE_BOTH,
                    ],
                )
                .select_related("ingredient")
                .order_by("name")
                .distinct()
            )
        self.fields["quantity"].widget.attrs.update(
            {"inputmode": "numeric", "step": "1", "min": "1", "data-order-qty": "true"}
        )
        self.fields["unit_price"].widget.attrs.update(
            {
                "inputmode": "decimal",
                "step": "0.01",
                "min": "0",
                "data-order-price": "true",
                "readonly": "readonly",
            }
        )
        self.fields["complements"].widget.attrs.update({"data-order-complements": "true"})
        self.fields["beverages"].widget.attrs.update({"data-order-beverages": "true"})
        self.fields["notes"].widget.attrs.update(
            {
                "data-order-notes": "true",
                "placeholder": "Ex: sem cebola, sem tomate, molho a parte",
            }
        )
        self.fields["menu_item"].required = False
        self.fields["quantity"].required = False
        self.fields["unit_price"].required = False
        self.fields["notes"].required = False
        self.fields["complements"].required = False
        self.fields["beverages"].required = False
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.SelectMultiple):
                field.widget.attrs["class"] = "form-select tom-select"
                field.widget.attrs["data-dropdown-parent"] = "self"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
                field.widget.attrs["data-dropdown-parent"] = "self"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"
        self.fields["menu_item"].widget.attrs["data-placeholder"] = "Pesquisar prato..."
        self.fields["menu_item"].widget.attrs["data-dropdown-parent"] = "self"
        self.fields["complements"].widget.attrs["data-placeholder"] = "Batata, molho, queijo extra..."
        self.fields["beverages"].widget.attrs["data-placeholder"] = "Refresco, agua, sumo..."


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
        fields = [
            "name",
            "category",
            "usage_type",
            "unit",
            "reorder_level",
            "stock_control",
            "is_active",
        ]
        labels = {
            "name": "Nome",
            "category": "Categoria",
            "usage_type": "Uso do insumo",
            "unit": "Unidade base de controlo",
            "reorder_level": "Stock minimo",
            "stock_control": "Controla stock",
            "is_active": "Ativo",
        }

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        category_choices = list(DEFAULT_INGREDIENT_CATEGORIES)
        unit_choices = list(DEFAULT_INGREDIENT_UNITS)
        if business is not None:
            ensure_default_ingredient_options(business)
            category_choices = list(
                FoodIngredientCategory.objects.filter(
                    business=business, is_active=True
                )
                .order_by("name")
                .values_list("code", "name")
            )
            unit_choices = list(
                FoodIngredientUnit.objects.filter(
                    business=business, is_active=True
                )
                .order_by("name")
                .values_list("code", "name")
            )
        if self.instance and self.instance.pk:
            if self.instance.category and self.instance.category not in {
                value for value, label in category_choices
            }:
                category_choices.append((self.instance.category, self.instance.category))
            if self.instance.unit and self.instance.unit not in {
                value for value, label in unit_choices
            }:
                unit_choices.append((self.instance.unit, self.instance.unit))

        self.fields["category"].widget = forms.Select(choices=category_choices)
        self.fields["unit"].widget = forms.Select(choices=unit_choices)
        self.fields["category"].widget.attrs["data-placeholder"] = "Categoria..."
        self.fields["category"].widget.attrs["data-dropdown-parent"] = "self"
        self.fields["usage_type"].widget.attrs["data-placeholder"] = "Uso..."
        self.fields["usage_type"].widget.attrs["data-dropdown-parent"] = "self"
        self.fields["unit"].widget.attrs["data-placeholder"] = "Unidade base..."
        self.fields["unit"].widget.attrs["data-dropdown-parent"] = "self"
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class IngredientStockEntryForm(forms.ModelForm):
    class Meta:
        model = IngredientStockEntry
        fields = ["supplier_name", "reference_number", "entry_date"]
        widgets = {
            "entry_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "supplier_name": "Fornecedor",
            "reference_number": "Referencia da fatura",
            "entry_date": "Data da compra/fatura",
        }

    def __init__(self, *args, **kwargs):
        kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if not self.instance.pk and not self.initial.get("entry_date"):
            self.initial["entry_date"] = timezone.localdate()
        self.fields["supplier_name"].widget.attrs["placeholder"] = "Nome do fornecedor"
        self.fields["reference_number"].widget.attrs["placeholder"] = "Numero da fatura/recibo"
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class IngredientStockEntryItemForm(forms.ModelForm):
    PURCHASE_UNIT_CHOICES = [
        ("", "Selecionar..."),
        ("caixa", "Caixa"),
        ("duzia", "Duzia"),
        ("embalagem", "Embalagem"),
        ("kg", "Kg"),
        ("litro", "Litro"),
        ("saco", "Saco"),
        ("unidade", "Unidade"),
        ("outro", "Outro"),
    ]

    class Meta:
        model = IngredientStockEntryItem
        fields = [
            "ingredient",
            "purchased_quantity",
            "purchase_unit",
            "conversion_factor",
            "total_cost",
            "expiry_date",
        ]
        widgets = {
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "ingredient": "Insumo",
            "purchased_quantity": "Qtd comprada",
            "purchase_unit": "Unidade de compra",
            "conversion_factor": "Fator de conversao",
            "total_cost": "Preco total",
            "expiry_date": "Validade",
        }

    def __init__(self, *args, **kwargs):
        ingredients = kwargs.pop("ingredients", None)
        super().__init__(*args, **kwargs)
        if ingredients is not None:
            self.fields["ingredient"].queryset = ingredients
        self.fields["purchase_unit"].widget = forms.Select(choices=self.PURCHASE_UNIT_CHOICES)
        self.fields["purchased_quantity"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.001", "min": "0"}
        )
        self.fields["conversion_factor"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.001", "min": "0.001"}
        )
        self.fields["total_cost"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0"}
        )
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
                field.widget.attrs["data-dropdown-parent"] = "self"
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
            purchased_quantity = form.cleaned_data.get("purchased_quantity")
            conversion_factor = form.cleaned_data.get("conversion_factor")
            if ingredient or purchased_quantity:
                has_any = True
            if ingredient and (not purchased_quantity or purchased_quantity <= 0):
                raise forms.ValidationError("Informe a quantidade comprada.")
            if ingredient and (not conversion_factor or conversion_factor <= 0):
                raise forms.ValidationError("Informe um fator de conversao maior que zero.")
        if not has_any:
            raise forms.ValidationError("Adicione pelo menos um ingrediente.")


IngredientStockEntryItemFormSet = formset_factory(
    IngredientStockEntryItemForm,
    formset=IngredientStockEntryBaseFormSet,
    extra=1,
    can_delete=True,
)


class IngredientAdjustmentForm(forms.Form):
    adjustment_type = forms.ChoiceField(
        label="Tipo",
        choices=[
            (IngredientMovement.MOVEMENT_ADJUST, "Ajuste manual"),
            (IngredientMovement.MOVEMENT_WASTE, "Perda/desperdicio"),
        ],
    )
    quantity = forms.DecimalField(
        label="Quantidade",
        max_digits=12,
        decimal_places=3,
        help_text="Use valor positivo. Em ajuste manual pode usar negativo para reduzir stock.",
    )
    notes = forms.CharField(
        label="Observacao",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quantity"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.001"}
        )
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"

    def clean(self):
        cleaned = super().clean()
        adjustment_type = cleaned.get("adjustment_type")
        quantity = cleaned.get("quantity")
        if quantity is None:
            return cleaned
        if adjustment_type == IngredientMovement.MOVEMENT_WASTE and quantity <= 0:
            self.add_error("quantity", "Informe uma quantidade positiva para perda.")
        if adjustment_type == IngredientMovement.MOVEMENT_ADJUST and quantity == 0:
            self.add_error("quantity", "Informe uma quantidade diferente de zero.")
        return cleaned


class FoodIngredientCategoryForm(forms.ModelForm):
    class Meta:
        model = FoodIngredientCategory
        fields = ["name", "is_active"]
        labels = {"name": "Categoria", "is_active": "Ativa"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class FoodIngredientUnitForm(forms.ModelForm):
    class Meta:
        model = FoodIngredientUnit
        fields = ["name", "is_active"]
        labels = {"name": "Unidade base", "is_active": "Ativa"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class MenuCategoryForm(forms.ModelForm):
    class Meta:
        model = MenuCategory
        fields = ["name", "is_active"]
        labels = {"name": "Nome", "is_active": "Ativo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class RestaurantTableForm(forms.ModelForm):
    class Meta:
        model = RestaurantTable
        fields = [
            "name",
            "seats",
            "status",
            "reserved_for",
            "reserved_until",
            "notes",
            "is_active",
        ]
        labels = {
            "name": "Nome",
            "seats": "Lugares",
            "status": "Estado",
            "reserved_for": "Reserva para",
            "reserved_until": "Reservada ate",
            "notes": "Observacoes",
            "is_active": "Ativa",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["seats"].widget.attrs.update(
            {"inputmode": "numeric", "step": "1", "min": "1"}
        )
        self.fields["reserved_until"].widget = forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        )
        self.fields["reserved_until"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
        ]
        if self.instance and self.instance.reserved_until:
            local_reserved_until = timezone.localtime(self.instance.reserved_until)
            self.initial["reserved_until"] = local_reserved_until.strftime("%Y-%m-%dT%H:%M")
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        reserved_for = (cleaned.get("reserved_for") or "").strip()
        reserved_until = cleaned.get("reserved_until")

        if status == RestaurantTable.STATUS_RESERVED:
            if not reserved_for:
                self.add_error("reserved_for", "Informe para quem a mesa esta reservada.")
            if not reserved_until:
                self.add_error("reserved_until", "Informe ate quando a mesa esta reservada.")
            elif timezone.is_naive(reserved_until):
                reserved_until = timezone.make_aware(
                    reserved_until, timezone.get_current_timezone()
                )
                cleaned["reserved_until"] = reserved_until
            if reserved_until and reserved_until <= timezone.now():
                self.add_error(
                    "reserved_until",
                    "A data/hora da reserva deve ser futura.",
                )
        else:
            cleaned["reserved_for"] = ""
            cleaned["reserved_until"] = None

        return cleaned


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
            "item_type": "Tipo do item",
            "selling_price": "Preco de venda",
            "ingredient": "Insumo de stock vinculado",
            "image": "Imagem",
            "is_active": "Ativo",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        ingredients = kwargs.pop("ingredients", None)
        categories = kwargs.pop("categories", None)
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if business is not None and business.business_type == business.BUSINESS_BURGER:
            ensure_default_menu_options(business)
            type_choices = list(
                MenuItemType.objects.filter(business=business, is_active=True)
                .order_by("name")
                .values_list("code", "name")
            )
            if type_choices:
                self.fields["item_type"].choices = type_choices
        if ingredients is not None:
            self.fields["ingredient"].queryset = ingredients
        if categories is not None:
            self.fields["category"].queryset = categories
        self.fields["selling_price"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0"}
        )
        self.fields["image"].widget.attrs.update({"accept": "image/*"})
        self.fields["ingredient"].required = False
        self.fields["ingredient"].widget.attrs["data-placeholder"] = "Selecionar insumo vendavel..."
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
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


class FoodExtraForm(forms.ModelForm):
    class Meta:
        model = FoodExtra
        fields = ["name", "extra_type", "extra_price", "ingredient", "is_active"]
        labels = {
            "name": "Nome",
            "extra_type": "Tipo de adicional",
            "extra_price": "Preco adicional",
            "ingredient": "Insumo de stock vinculado",
            "is_active": "Ativo",
        }

    def __init__(self, *args, **kwargs):
        ingredients = kwargs.pop("ingredients", None)
        super().__init__(*args, **kwargs)
        if ingredients is not None:
            self.fields["ingredient"].queryset = ingredients
        self.fields["extra_price"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0"}
        )
        self.fields["ingredient"].required = False
        self.fields["ingredient"].widget.attrs["data-placeholder"] = "Opcional: baixa stock deste insumo..."
        for name, field in self.fields.items():
            if getattr(field.widget, "input_type", None) == "checkbox":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class OrderPaymentForm(forms.ModelForm):
    method = forms.ChoiceField(label="Metodo")

    class Meta:
        model = OrderPayment
        fields = ["method", "amount"]
        labels = {"amount": "Valor"}

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if business:
            methods = PaymentMethod.objects.filter(
                business=business, is_active=True
            ).order_by("name")
            if methods.exists():
                self.fields["method"].choices = [(m.code, m.name) for m in methods]
            else:
                self.fields["method"].choices = CashMovement.METHOD_CHOICES
        else:
            self.fields["method"].choices = CashMovement.METHOD_CHOICES
        self.fields["amount"].widget.attrs.update(
            {"inputmode": "decimal", "step": "0.01", "min": "0.01"}
        )
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select tom-select"
            else:
                field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"


class DeliveryInfoForm(forms.ModelForm):
    class Meta:
        model = DeliveryInfo
        fields = ["address", "phone", "delivery_fee", "driver_name", "notes"]
        labels = {
            "address": "Endereco",
            "phone": "Contacto",
            "delivery_fee": "Taxa de entrega",
            "driver_name": "Responsavel de entrega",
            "notes": "Observacoes",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            if field.required:
                field.widget.attrs["required"] = "required"
