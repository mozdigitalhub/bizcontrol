from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from food.models import MenuItem
from tenants.decorators import business_required
from tenants.models import Business
from food.forms import (
    DeliveryInfoForm,
    IngredientForm,
    IngredientStockEntryForm,
    IngredientStockEntryItemFormSet,
    MenuCategoryForm,
    MenuItemForm,
    MenuItemRecipeFormSet,
    OrderForm,
    OrderItemFormSet,
)
from food.models import (
    IngredientStockEntry,
    MenuCategory,
    MenuItem,
    Order,
)
from food.services import create_ingredient_entry, create_order, update_order_status


def _food_enabled(business):
    return business.business_type == Business.BUSINESS_BURGER


@login_required
@business_required
@permission_required("food.view_order", raise_exception=True)
def order_list(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    channel = request.GET.get("channel", "").strip()
    orders = Order.objects.filter(business=request.business).select_related("customer")
    if query:
        orders = orders.filter(Q(code__icontains=query) | Q(customer__name__icontains=query))
    if status:
        orders = orders.filter(status=status)
    if channel:
        orders = orders.filter(channel=channel)
    paginator = Paginator(orders.order_by("-created_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "food/order_list.html",
        {
            "page": page,
            "query": query,
            "status": status,
            "channel": channel,
            "status_choices": Order.STATUS_CHOICES,
            "channel_choices": Order.CHANNEL_CHOICES,
        },
    )


@login_required
@business_required
@permission_required("food.add_order", raise_exception=True)
def order_create(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")
    if request.method == "POST":
        form = OrderForm(request.POST, business=request.business)
        formset = OrderItemFormSet(
            request.POST,
            prefix="items",
            form_kwargs={
                "products": MenuItem.objects.filter(business=request.business, is_active=True),
                "business": request.business,
            },
        )
        delivery_form = DeliveryInfoForm(request.POST, prefix="delivery")
        if form.is_valid() and formset.is_valid():
            items = []
            for item_form in formset:
                if item_form.cleaned_data.get("DELETE"):
                    continue
                product = item_form.cleaned_data.get("menu_item")
                quantity = item_form.cleaned_data.get("quantity")
                unit_price = item_form.cleaned_data.get("unit_price")
                notes = item_form.cleaned_data.get("notes")
                if not product or not quantity:
                    continue
                items.append(
                    {
                        "menu_item": product,
                        "quantity": quantity,
                        "unit_price": unit_price or product.selling_price,
                        "notes": notes or "",
                    }
                )
            delivery_data = None
            if form.cleaned_data.get("channel") == Order.CHANNEL_DELIVERY:
                if delivery_form.is_valid():
                    delivery_data = delivery_form.cleaned_data
                else:
                    messages.error(request, "Revise os dados de entrega.")
                    return render(
                        request,
                        "food/order_form.html",
                        {
                            "form": form,
                            "formset": formset,
                            "delivery_form": delivery_form,
                            "product_prices": _product_prices(request.business),
                            "pay_before_service": request.business.feature_enabled("pay_before_service"),
                        },
                    )
            try:
                order = create_order(
                    business=request.business,
                    user=request.user,
                    order_data=form.cleaned_data,
                    items=items,
                    delivery_data=delivery_data,
                )
            except Exception as exc:
                messages.error(request, str(exc))
                return render(
                    request,
                    "food/order_form.html",
                    {
                        "form": form,
                        "formset": formset,
                        "delivery_form": delivery_form,
                        "product_prices": _product_prices(request.business),
                        "pay_before_service": request.business.feature_enabled("pay_before_service"),
                    },
                )
            messages.success(request, "Pedido enviado para a cozinha.")
            return redirect("food:kds")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = OrderForm(business=request.business)
        formset = OrderItemFormSet(
            prefix="items",
            form_kwargs={
                "products": MenuItem.objects.filter(business=request.business, is_active=True),
                "business": request.business,
            },
        )
        delivery_form = DeliveryInfoForm(prefix="delivery")
    return render(
        request,
        "food/order_form.html",
        {
            "form": form,
            "formset": formset,
            "delivery_form": delivery_form,
            "product_prices": _product_prices(request.business),
            "pay_before_service": request.business.feature_enabled("pay_before_service"),
        },
    )


@login_required
@business_required
@permission_required("food.view_menuitem", raise_exception=True)
def menu_list(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    item_type = request.GET.get("item_type", "").strip()
    items = MenuItem.objects.filter(business=request.business)
    if query:
        items = items.filter(Q(name__icontains=query))
    if category_id:
        items = items.filter(category_id=category_id)
    if item_type:
        items = items.filter(item_type=item_type)
    paginator = Paginator(items.order_by("name"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "food/menu_list.html",
        {
            "page": page,
            "query": query,
            "category_id": category_id,
            "item_type": item_type,
            "categories": MenuCategory.objects.filter(business=request.business, is_active=True),
            "type_choices": MenuItem.TYPE_CHOICES,
        },
    )


@login_required
@business_required
@permission_required("food.add_menuitem", raise_exception=True)
def menu_create(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")
    if request.method == "POST":
        form = MenuItemForm(
            request.POST,
            request.FILES,
            ingredients=request.business.food_ingredients.filter(is_active=True),
            categories=MenuCategory.objects.filter(business=request.business, is_active=True),
        )
        formset = MenuItemRecipeFormSet(
            request.POST,
            prefix="recipe",
            form_kwargs={
                "ingredients": request.business.food_ingredients.filter(is_active=True),
            },
        )
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                item = form.save(commit=False)
                item.business = request.business
                item.save()
                for recipe_form in formset:
                    if recipe_form.cleaned_data.get("DELETE"):
                        continue
                    ingredient = recipe_form.cleaned_data.get("ingredient")
                    quantity = recipe_form.cleaned_data.get("quantity")
                    unit = recipe_form.cleaned_data.get("unit") or ""
                    if ingredient and quantity:
                        item.recipes.create(
                            ingredient=ingredient, quantity=quantity, unit=unit
                        )
            messages.success(request, "Menu criado.")
            return redirect("food:menu_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = MenuItemForm(
            ingredients=request.business.food_ingredients.filter(is_active=True),
            categories=MenuCategory.objects.filter(business=request.business, is_active=True),
        )
        formset = MenuItemRecipeFormSet(
            prefix="recipe",
            form_kwargs={
                "ingredients": request.business.food_ingredients.filter(is_active=True),
            },
        )
    return render(
        request,
        "food/menu_form.html",
        {"form": form, "formset": formset},
    )


@login_required
@business_required
@permission_required("food.change_menuitem", raise_exception=True)
def menu_edit(request, pk):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")
    item = get_object_or_404(MenuItem, pk=pk, business=request.business)
    if request.method == "POST":
        form = MenuItemForm(
            request.POST,
            request.FILES,
            instance=item,
            ingredients=request.business.food_ingredients.filter(is_active=True),
            categories=MenuCategory.objects.filter(business=request.business, is_active=True),
        )
        formset = MenuItemRecipeFormSet(
            request.POST,
            prefix="recipe",
            form_kwargs={
                "ingredients": request.business.food_ingredients.filter(is_active=True),
            },
        )
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                item = form.save()
                item.recipes.all().delete()
                for recipe_form in formset:
                    if recipe_form.cleaned_data.get("DELETE"):
                        continue
                    ingredient = recipe_form.cleaned_data.get("ingredient")
                    quantity = recipe_form.cleaned_data.get("quantity")
                    unit = recipe_form.cleaned_data.get("unit") or ""
                    if ingredient and quantity:
                        item.recipes.create(
                            ingredient=ingredient, quantity=quantity, unit=unit
                        )
            messages.success(request, "Menu atualizado.")
            return redirect("food:menu_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = MenuItemForm(
            instance=item,
            ingredients=request.business.food_ingredients.filter(is_active=True),
            categories=MenuCategory.objects.filter(business=request.business, is_active=True),
        )
        initial = []
        for recipe in item.recipes.select_related("ingredient"):
            initial.append(
                {
                    "ingredient": recipe.ingredient_id,
                    "quantity": recipe.quantity,
                    "unit": recipe.unit,
                }
            )
        formset = MenuItemRecipeFormSet(
            prefix="recipe",
            form_kwargs={
                "ingredients": request.business.food_ingredients.filter(is_active=True),
            },
            initial=initial,
        )
    return render(
        request,
        "food/menu_form.html",
        {"form": form, "formset": formset, "item": item},
    )


@login_required
@business_required
@permission_required("food.view_foodingredient", raise_exception=True)
def ingredient_list(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")
    query = request.GET.get("q", "").strip()
    ingredients = request.business.food_ingredients.all()
    if query:
        ingredients = ingredients.filter(Q(name__icontains=query))
    paginator = Paginator(ingredients.order_by("name"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "food/ingredient_list.html",
        {"page": page, "query": query},
    )


@login_required
@business_required
@permission_required("food.add_foodingredient", raise_exception=True)
def ingredient_create(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")
    if request.method == "POST":
        form = IngredientForm(request.POST)
        if form.is_valid():
            ingredient = form.save(commit=False)
            ingredient.business = request.business
            ingredient.save()
            messages.success(request, "Ingrediente criado.")
            return redirect("food:ingredient_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = IngredientForm()
    return render(request, "food/ingredient_form.html", {"form": form})


@login_required
@business_required
@permission_required("food.change_foodingredient", raise_exception=True)
def ingredient_edit(request, pk):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")
    ingredient = get_object_or_404(
        request.business.food_ingredients, pk=pk
    )
    if request.method == "POST":
        form = IngredientForm(request.POST, instance=ingredient)
        if form.is_valid():
            form.save()
            messages.success(request, "Ingrediente atualizado.")
            return redirect("food:ingredient_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = IngredientForm(instance=ingredient)
    return render(
        request, "food/ingredient_form.html", {"form": form, "ingredient": ingredient}
    )


@login_required
@business_required
@permission_required("food.view_ingredientstockentry", raise_exception=True)
def ingredient_entry_list(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")
    entries = IngredientStockEntry.objects.filter(business=request.business)
    paginator = Paginator(entries.order_by("-entry_date"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "food/ingredient_entry_list.html",
        {"page": page},
    )


@login_required
@business_required
@permission_required("food.add_ingredientstockentry", raise_exception=True)
def ingredient_entry_create(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")
    if request.method == "POST":
        form = IngredientStockEntryForm(request.POST)
        formset = IngredientStockEntryItemFormSet(
            request.POST,
            prefix="items",
            form_kwargs={
                "ingredients": request.business.food_ingredients.filter(is_active=True),
            },
        )
        if form.is_valid() and formset.is_valid():
            try:
                entry = create_ingredient_entry(
                    business=request.business,
                    user=request.user,
                    entry_data=form.cleaned_data,
                    items=formset.cleaned_data,
                )
            except Exception as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Entrada de stock registada.")
                return redirect("food:ingredient_entry_list")
        else:
            messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = IngredientStockEntryForm()
        formset = IngredientStockEntryItemFormSet(
            prefix="items",
            form_kwargs={
                "ingredients": request.business.food_ingredients.filter(is_active=True),
            },
        )
    return render(
        request,
        "food/ingredient_entry_form.html",
        {"form": form, "formset": formset},
    )


@login_required
@business_required
@permission_required("food.view_order", raise_exception=True)
def kds(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")
    orders = (
        Order.objects.filter(
            business=request.business,
            status__in=[
                Order.STATUS_CONFIRMED,
                Order.STATUS_IN_PREPARATION,
                Order.STATUS_READY,
            ],
        )
        .select_related("customer")
        .order_by("created_at")
    )
    grouped = {
        Order.STATUS_CONFIRMED: [],
        Order.STATUS_IN_PREPARATION: [],
        Order.STATUS_READY: [],
    }
    for order in orders:
        grouped.get(order.status, []).append(order)
    return render(
        request,
        "food/kds.html",
        {"orders": orders, "grouped": grouped},
    )


@login_required
@business_required
@permission_required("food.change_order", raise_exception=True)
def update_status(request, pk):
    if request.method != "POST":
        return redirect("food:kds")
    order = get_object_or_404(Order, pk=pk, business=request.business)
    status = request.POST.get("status")
    try:
        update_order_status(order=order, status=status, user=request.user)
        messages.success(request, "Estado atualizado.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("food:kds")


def _product_prices(business):
    return {
        str(prod.id): {"sale": float(prod.selling_price)}
        for prod in MenuItem.objects.filter(business=business, is_active=True)
    }
