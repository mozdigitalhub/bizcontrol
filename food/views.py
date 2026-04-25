from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce, ExtractHour
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from customers.models import Customer
from finance.models import CashMovement, Expense, FinancialAccount, PaymentMethod, Purchase
from finance.services import ensure_default_payment_methods
from food.forms import (
    DeliveryInfoForm,
    FoodExtraForm,
    FoodIngredientCategoryForm,
    FoodIngredientUnitForm,
    IngredientAdjustmentForm,
    IngredientForm,
    IngredientStockEntryForm,
    IngredientStockEntryItemFormSet,
    MenuCategoryForm,
    MenuItemForm,
    MenuItemRecipeFormSet,
    OrderForm,
    OrderItemFormSet,
    OrderPaymentForm,
    RestaurantTableForm,
)
from food.models import (
    FoodExtra,
    FoodIngredient,
    FoodIngredientCategory,
    FoodIngredientUnit,
    IngredientMovement,
    IngredientStockEntry,
    MenuCategory,
    MenuItem,
    Order,
    OrderItem,
    RestaurantTable,
)
from food.services import (
    adjust_ingredient_stock,
    create_ingredient_entry,
    create_order,
    ensure_default_ingredient_options,
    ensure_default_menu_options,
    register_order_payment,
    update_order_status,
)
from tenants.decorators import business_required
from tenants.models import Business


def _food_enabled(business):
    return bool(
        business.feature_enabled(Business.FEATURE_USE_KITCHEN_DISPLAY)
        and business.feature_enabled(Business.FEATURE_USE_RECIPES)
    )


def _tables_enabled(business):
    return _food_enabled(business) and business.feature_enabled(Business.FEATURE_USE_TABLES)


def _ensure_financial_write_permission(user):
    if user.has_perm("food.change_order"):
        return
    raise PermissionDenied("Sem permissao para registar movimentos financeiros.")


def _recipe_ingredients(business):
    ingredients = business.food_ingredients.filter(is_active=True)
    if business.business_type == Business.BUSINESS_BURGER:
        ingredients = ingredients.filter(
            usage_type__in=[FoodIngredient.USAGE_RECIPE, FoodIngredient.USAGE_BOTH]
        )
    return ingredients.order_by("name")


def _sellable_ingredients(business):
    ingredients = business.food_ingredients.filter(is_active=True)
    if business.business_type == Business.BUSINESS_BURGER:
        ingredients = ingredients.filter(
            usage_type__in=[FoodIngredient.USAGE_SELLABLE, FoodIngredient.USAGE_BOTH]
        )
    return ingredients.order_by("name")


@login_required
@business_required
@permission_required("food.view_order", raise_exception=True)
def order_list(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    channel = request.GET.get("channel", "").strip()
    table_id = request.GET.get("table", "").strip()
    payment_status = request.GET.get("payment_status", "").strip()

    orders = Order.objects.filter(business=request.business).select_related("customer", "table")
    if query:
        orders = orders.filter(Q(code__icontains=query) | Q(customer__name__icontains=query))
    if status:
        orders = orders.filter(status=status)
    if channel:
        orders = orders.filter(channel=channel)
    if table_id:
        orders = orders.filter(table_id=table_id)
    if payment_status:
        orders = orders.filter(payment_status=payment_status)

    paginator = Paginator(orders.order_by("-created_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    for order in page.object_list:
        _attach_order_timing(order)
        order.outstanding = max(order.total - order.amount_paid, Decimal("0"))

    today = timezone.localdate()
    today_orders = Order.objects.filter(business=request.business, created_at__date=today)
    today_non_canceled = today_orders.exclude(status=Order.STATUS_CANCELED)
    status_summary = {
        "new": today_orders.filter(status=Order.STATUS_CONFIRMED).count(),
        "preparing": today_orders.filter(status=Order.STATUS_IN_PREPARATION).count(),
        "ready": today_orders.filter(status=Order.STATUS_READY).count(),
        "delivered": today_orders.filter(status=Order.STATUS_DELIVERED).count(),
        "canceled": today_orders.filter(status=Order.STATUS_CANCELED).count(),
    }
    channel_summary = {
        row["channel"]: row["total"]
        for row in today_non_canceled.values("channel").annotate(total=Count("id"))
    }
    open_balance_today = today_non_canceled.aggregate(
        total=Coalesce(Sum(F("total") - F("amount_paid")), Decimal("0"))
    ).get("total")

    return render(
        request,
        "food/order_list.html",
        {
            "page": page,
            "query": query,
            "status": status,
            "channel": channel,
            "table_id": table_id,
            "payment_status": payment_status,
            "tables": RestaurantTable.objects.filter(
                business=request.business, is_active=True
            ).order_by("name")
            if _tables_enabled(request.business)
            else [],
            "status_choices": Order.STATUS_CHOICES,
            "channel_choices": Order.CHANNEL_CHOICES,
            "payment_status_choices": Order.PAYMENT_CHOICES,
            "tables_enabled": _tables_enabled(request.business),
            "status_summary": status_summary,
            "today_orders_count": today_non_canceled.count(),
            "today_sales": today_non_canceled.aggregate(
                total=Coalesce(Sum("total"), Decimal("0"))
            ).get("total"),
            "channel_summary": channel_summary,
            "open_balance_today": open_balance_today,
        },
    )


@login_required
@business_required
@permission_required("food.add_order", raise_exception=True)
def order_create(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    form_kwargs = {
        "form_kwargs": {
            "products": MenuItem.objects.filter(business=request.business, is_active=True),
            "business": request.business,
        },
    }

    if request.method == "POST":
        form = OrderForm(request.POST, business=request.business)
        formset = OrderItemFormSet(request.POST, prefix="items", **form_kwargs)
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
                variant = item_form.cleaned_data.get("variant")
                extras = list(item_form.cleaned_data.get("extras") or [])
                if not product or not quantity:
                    continue
                items.append(
                    {
                        "menu_item": product,
                        "quantity": quantity,
                        "unit_price": unit_price or product.selling_price,
                        "notes": notes or "",
                        "variant": variant,
                        "extras": extras,
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
                            "extra_prices": _extra_prices(request.business),
                            "ingredient_preview": _ingredient_preview_data(request.business),
                            "pay_before_service": request.business.feature_enabled("pay_before_service"),
                            "tables_enabled": _tables_enabled(request.business),
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
                        "extra_prices": _extra_prices(request.business),
                        "ingredient_preview": _ingredient_preview_data(request.business),
                        "pay_before_service": request.business.feature_enabled("pay_before_service"),
                        "tables_enabled": _tables_enabled(request.business),
                    },
                )

            messages.success(request, "Pedido criado e enviado para operacao.")
            return redirect("food:order_checkout", pk=order.id)
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = OrderForm(business=request.business)
        formset = OrderItemFormSet(prefix="items", **form_kwargs)
        delivery_form = DeliveryInfoForm(prefix="delivery")

    return render(
        request,
        "food/order_form.html",
        {
            "form": form,
            "formset": formset,
            "delivery_form": delivery_form,
            "product_prices": _product_prices(request.business),
            "extra_prices": _extra_prices(request.business),
            "ingredient_preview": _ingredient_preview_data(request.business),
            "pay_before_service": request.business.feature_enabled("pay_before_service"),
            "tables_enabled": _tables_enabled(request.business),
        },
    )


@login_required
@business_required
@permission_required("food.add_order", raise_exception=True)
def customer_quick_create(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Metodo invalido."}, status=405)
    if not _food_enabled(request.business):
        return JsonResponse({"ok": False, "message": "Modulo indisponivel."}, status=400)

    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    if not name or not phone:
        return JsonResponse(
            {"ok": False, "message": "Informe nome e contacto."},
            status=400,
        )

    customer, created = Customer.objects.get_or_create(
        business=request.business,
        phone=phone,
        defaults={
            "name": name,
            "created_by": request.user,
            "updated_by": request.user,
        },
    )
    if not created and customer.name != name:
        customer.name = name
        customer.updated_by = request.user
        customer.save(update_fields=["name", "updated_by", "updated_at"])

    return JsonResponse(
        {
            "ok": True,
            "created": created,
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "label": f"{customer.name} - {customer.phone}",
        }
    )


@login_required
@business_required
@permission_required("food.view_order", raise_exception=True)
def order_checkout(request, pk):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    order = get_object_or_404(
        Order.objects.select_related("customer", "table").prefetch_related(
            "items__menu_item",
            "items__extras__extra",
            "payments",
        ),
        pk=pk,
        business=request.business,
    )

    if request.method == "POST":
        _ensure_financial_write_permission(request.user)
        form = OrderPaymentForm(request.POST, business=request.business)
        if form.is_valid():
            try:
                register_order_payment(
                    order=order,
                    business=request.business,
                    user=request.user,
                    method=form.cleaned_data["method"],
                    amount=form.cleaned_data["amount"],
                )
            except Exception as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Pagamento registado com sucesso.")
                return redirect("food:order_checkout", pk=order.id)
        else:
            messages.error(request, "Revise os dados do pagamento.")
    else:
        form = OrderPaymentForm(
            business=request.business,
            initial={
                "amount": max(order.total - order.amount_paid, Decimal("0")),
            },
        )

    order.refresh_from_db()
    outstanding = max(order.total - order.amount_paid, Decimal("0"))
    return render(
        request,
        "food/order_checkout.html",
        {
            "order": order,
            "form": form,
            "outstanding": outstanding,
            "payments": order.payments.order_by("-paid_at", "-id"),
        },
    )


@login_required
@business_required
@permission_required("food.view_order", raise_exception=True)
def order_payment_modal(request, pk):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")
    _ensure_financial_write_permission(request.user)

    order = get_object_or_404(
        Order.objects.select_related("customer", "table").prefetch_related("payments__created_by"),
        pk=pk,
        business=request.business,
    )
    next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or request.META.get("HTTP_REFERER")
        or reverse("food:order_list")
    )
    outstanding = max(order.total - order.amount_paid, Decimal("0"))
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.method == "POST":
        form = OrderPaymentForm(request.POST, business=request.business)
        if outstanding <= 0:
            form.add_error(None, "Pedido ja esta totalmente pago.")
        elif form.is_valid():
            try:
                register_order_payment(
                    order=order,
                    business=request.business,
                    user=request.user,
                    method=form.cleaned_data["method"],
                    amount=form.cleaned_data["amount"],
                )
            except Exception as exc:
                form.add_error(None, str(exc))
            else:
                if is_ajax:
                    return JsonResponse({"ok": True, "redirect_url": next_url})
                messages.success(request, "Pagamento registado com sucesso.")
                return redirect(next_url)
        if not is_ajax:
            messages.error(request, "Nao foi possivel registar o pagamento.")
    else:
        form = OrderPaymentForm(
            business=request.business,
            initial={"amount": outstanding},
        )

    order.refresh_from_db()
    outstanding = max(order.total - order.amount_paid, Decimal("0"))
    response = render(
        request,
        "food/partials/order_payment_modal_body.html",
        {
            "order": order,
            "form": form,
            "outstanding": outstanding,
            "payments": order.payments.order_by("-paid_at", "-id")[:8],
            "next_url": next_url,
        },
    )
    if request.method == "POST" and is_ajax and form.errors:
        response.status_code = 400
    return response


@login_required
@business_required
@permission_required("food.view_order", raise_exception=True)
def order_detail_modal(request, pk):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    order = get_object_or_404(
        Order.objects.select_related("customer", "table").prefetch_related(
            "items__menu_item",
            "items__product",
            "items__extras__extra",
            "payments__created_by",
        ),
        pk=pk,
        business=request.business,
    )
    _attach_order_timing(order)
    return render(
        request,
        "food/partials/order_detail_modal_body.html",
        {
            "order": order,
            "payments": order.payments.order_by("-paid_at", "-id"),
            "outstanding": max(order.total - order.amount_paid, Decimal("0")),
        },
    )


@login_required
@business_required
@permission_required("food.view_menuitem", raise_exception=True)
def menu_list(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    ensure_default_menu_options(request.business)
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
    type_choices = list(
        request.business.menu_item_types.filter(is_active=True)
        .order_by("name")
        .values_list("code", "name")
    )
    type_labels = dict(type_choices)
    for item in page.object_list:
        item.type_label = type_labels.get(item.item_type, item.get_item_type_display())
    return render(
        request,
        "food/menu_list.html",
        {
            "page": page,
            "query": query,
            "category_id": category_id,
            "item_type": item_type,
            "categories": MenuCategory.objects.filter(business=request.business, is_active=True),
            "type_choices": type_choices,
        },
    )


@login_required
@business_required
@permission_required("food.add_menuitem", raise_exception=True)
def menu_create(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    ensure_default_menu_options(request.business)
    sellable_ingredients = _sellable_ingredients(request.business)
    recipe_ingredients = _recipe_ingredients(request.business)
    active_categories = MenuCategory.objects.filter(business=request.business, is_active=True)
    if request.method == "POST":
        form = MenuItemForm(
            request.POST,
            request.FILES,
            ingredients=sellable_ingredients,
            categories=active_categories,
            business=request.business,
        )
        formset = MenuItemRecipeFormSet(
            request.POST,
            prefix="recipe",
            form_kwargs={
                "ingredients": recipe_ingredients,
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
                    unit = ingredient.unit if ingredient else (recipe_form.cleaned_data.get("unit") or "")
                    if ingredient and quantity:
                        item.recipes.create(
                            ingredient=ingredient,
                            quantity=quantity,
                            unit=unit,
                        )
            messages.success(request, "Item do menu criado.")
            return redirect("food:menu_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = MenuItemForm(
            ingredients=sellable_ingredients,
            categories=active_categories,
            business=request.business,
        )
        formset = MenuItemRecipeFormSet(
            prefix="recipe",
            form_kwargs={
                "ingredients": recipe_ingredients,
            },
        )

    return render(
        request,
        "food/menu_form.html",
        {
            "form": form,
            "formset": formset,
            "ingredient_preview": _ingredient_preview_data(request.business),
            "is_edit": False,
        },
    )


@login_required
@business_required
@permission_required("food.change_menuitem", raise_exception=True)
def menu_edit(request, pk):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    ensure_default_menu_options(request.business)
    sellable_ingredients = _sellable_ingredients(request.business)
    recipe_ingredients = _recipe_ingredients(request.business)
    active_categories = MenuCategory.objects.filter(business=request.business, is_active=True)
    item = get_object_or_404(MenuItem, pk=pk, business=request.business)
    if request.method == "POST":
        form = MenuItemForm(
            request.POST,
            request.FILES,
            instance=item,
            ingredients=sellable_ingredients,
            categories=active_categories,
            business=request.business,
        )
        formset = MenuItemRecipeFormSet(
            request.POST,
            prefix="recipe",
            form_kwargs={
                "ingredients": recipe_ingredients,
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
                    unit = ingredient.unit if ingredient else (recipe_form.cleaned_data.get("unit") or "")
                    if ingredient and quantity:
                        item.recipes.create(
                            ingredient=ingredient,
                            quantity=quantity,
                            unit=unit,
                        )
            messages.success(request, "Item do menu atualizado.")
            return redirect("food:menu_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = MenuItemForm(
            instance=item,
            ingredients=sellable_ingredients,
            categories=active_categories,
            business=request.business,
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
                "ingredients": recipe_ingredients,
            },
            initial=initial,
        )

    return render(
        request,
        "food/menu_form.html",
        {
            "form": form,
            "formset": formset,
            "item": item,
            "ingredient_preview": _ingredient_preview_data(request.business),
            "is_edit": True,
        },
    )


@login_required
@business_required
@permission_required("food.view_menuitem", raise_exception=True)
def menu_detail(request, pk):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    item = get_object_or_404(
        MenuItem.objects.select_related("category", "ingredient")
        .prefetch_related("recipes__ingredient"),
        pk=pk,
        business=request.business,
    )
    return render(
        request,
        "food/menu_detail.html",
        {
            "item": item,
        },
    )


@login_required
@business_required
@permission_required("food.delete_menuitem", raise_exception=True)
def menu_delete(request, pk):
    if request.method != "POST":
        return redirect("food:menu_list")
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    item = get_object_or_404(MenuItem, pk=pk, business=request.business)
    item_name = item.name
    try:
        item.delete()
    except ProtectedError:
        item.is_active = False
        item.save(update_fields=["is_active", "updated_at"])
        messages.warning(
            request,
            "Item com historico de pedidos nao pode ser removido. Foi inativado.",
        )
    else:
        messages.success(request, f"Item '{item_name}' removido.")
    return redirect("food:menu_list")


@login_required
@business_required
@permission_required("food.view_menucategory", raise_exception=True)
def menu_category_list(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    ensure_default_menu_options(request.business)
    query = request.GET.get("q", "").strip()
    categories = MenuCategory.objects.filter(business=request.business)
    if query:
        categories = categories.filter(name__icontains=query)
    paginator = Paginator(categories.order_by("name"), 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "food/menu_category_list.html",
        {
            "page": page,
            "query": query,
        },
    )


@login_required
@business_required
@permission_required("food.add_menucategory", raise_exception=True)
def menu_category_create(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    if request.method == "POST":
        form = MenuCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.business = request.business
            category.save()
            messages.success(request, "Categoria criada.")
            return redirect("food:menu_category_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = MenuCategoryForm()
    return render(request, "food/menu_category_form.html", {"form": form})


@login_required
@business_required
@permission_required("food.change_menucategory", raise_exception=True)
def menu_category_edit(request, pk):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    category = get_object_or_404(MenuCategory, pk=pk, business=request.business)
    if request.method == "POST":
        form = MenuCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoria atualizada.")
            return redirect("food:menu_category_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = MenuCategoryForm(instance=category)
    return render(
        request,
        "food/menu_category_form.html",
        {
            "form": form,
            "category": category,
        },
    )


@login_required
@business_required
@permission_required("food.view_foodextra", raise_exception=True)
def extra_list(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    query = request.GET.get("q", "").strip()
    extra_type = request.GET.get("extra_type", "").strip()
    extras = FoodExtra.objects.filter(business=request.business).select_related("ingredient")
    if query:
        extras = extras.filter(name__icontains=query)
    if extra_type:
        extras = extras.filter(extra_type=extra_type)
    paginator = Paginator(extras.order_by("extra_type", "name"), 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "food/extra_list.html",
        {
            "page": page,
            "query": query,
            "extra_type": extra_type,
            "type_choices": FoodExtra.TYPE_CHOICES,
        },
    )


@login_required
@business_required
@permission_required("food.add_foodextra", raise_exception=True)
def extra_create(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    if request.method == "POST":
        form = FoodExtraForm(request.POST, ingredients=_sellable_ingredients(request.business))
        if form.is_valid():
            extra = form.save(commit=False)
            extra.business = request.business
            extra.save()
            messages.success(request, "Complemento criado.")
            return redirect("food:extra_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = FoodExtraForm(ingredients=_sellable_ingredients(request.business))
    return render(request, "food/extra_form.html", {"form": form})


@login_required
@business_required
@permission_required("food.change_foodextra", raise_exception=True)
def extra_edit(request, pk):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    extra = get_object_or_404(FoodExtra, pk=pk, business=request.business)
    if request.method == "POST":
        form = FoodExtraForm(
            request.POST,
            instance=extra,
            ingredients=_sellable_ingredients(request.business),
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Complemento atualizado.")
            return redirect("food:extra_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = FoodExtraForm(
            instance=extra,
            ingredients=_sellable_ingredients(request.business),
        )
    return render(request, "food/extra_form.html", {"form": form, "extra": extra})


@login_required
@business_required
@permission_required("food.view_foodingredient", raise_exception=True)
def ingredient_list(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    ensure_default_ingredient_options(request.business)
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    ingredients = request.business.food_ingredients.all()
    if query:
        ingredients = ingredients.filter(Q(name__icontains=query))
    if category:
        ingredients = ingredients.filter(category=category)
    paginator = Paginator(ingredients.order_by("name"), 20)
    page = paginator.get_page(request.GET.get("page"))

    stock_summary = {"critical": 0, "near": 0, "healthy": 0}
    all_ingredients = request.business.food_ingredients.filter(is_active=True)
    for ingredient in all_ingredients:
        status = _ingredient_stock_status(ingredient)
        if status in stock_summary:
            stock_summary[status] += 1

    for ingredient in page.object_list:
        ingredient.stock_status = _ingredient_stock_status(ingredient)
    category_labels = dict(
        FoodIngredientCategory.objects.filter(business=request.business).values_list(
            "code", "name"
        )
    )
    for ingredient in page.object_list:
        ingredient.category_label = category_labels.get(
            ingredient.category, ingredient.get_category_display()
        )

    return render(
        request,
        "food/ingredient_list.html",
        {
            "page": page,
            "query": query,
            "category": category,
            "category_choices": FoodIngredientCategory.objects.filter(
                business=request.business, is_active=True
            ).order_by("name"),
            "stock_summary": stock_summary,
        },
    )


@login_required
@business_required
@permission_required("food.add_foodingredient", raise_exception=True)
def ingredient_create(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    ensure_default_ingredient_options(request.business)
    if request.method == "POST":
        form = IngredientForm(request.POST, business=request.business)
        if form.is_valid():
            ingredient = form.save(commit=False)
            ingredient.business = request.business
            ingredient.save()
            messages.success(request, "Ingrediente criado.")
            return redirect("food:ingredient_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = IngredientForm(business=request.business)
    return render(request, "food/ingredient_form.html", {"form": form})


@login_required
@business_required
@permission_required("food.change_foodingredient", raise_exception=True)
def ingredient_edit(request, pk):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    ingredient = get_object_or_404(request.business.food_ingredients, pk=pk)
    if request.method == "POST":
        form = IngredientForm(
            request.POST,
            instance=ingredient,
            business=request.business,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Ingrediente atualizado.")
            return redirect("food:ingredient_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = IngredientForm(instance=ingredient, business=request.business)
    return render(
        request,
        "food/ingredient_form.html",
        {
            "form": form,
            "ingredient": ingredient,
        },
    )


@login_required
@business_required
@permission_required("food.view_foodingredient", raise_exception=True)
def ingredient_detail(request, pk):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    ingredient = get_object_or_404(request.business.food_ingredients, pk=pk)
    category_labels = dict(
        FoodIngredientCategory.objects.filter(business=request.business).values_list(
            "code", "name"
        )
    )
    ingredient.category_label = category_labels.get(
        ingredient.category, ingredient.get_category_display()
    )
    ingredient.stock_status = _ingredient_stock_status(ingredient)
    recent_movements = IngredientMovement.objects.filter(
        business=request.business,
        ingredient=ingredient,
    ).select_related("created_by").order_by("-created_at", "-id")[:10]
    return render(
        request,
        "food/ingredient_detail.html",
        {
            "ingredient": ingredient,
            "recent_movements": recent_movements,
            "recipe_items": ingredient.recipes.select_related("menu_item").order_by(
                "menu_item__name"
            ),
            "linked_menu_items": ingredient.beverage_items.order_by("name"),
            "linked_complements": ingredient.food_complements.order_by("name"),
        },
    )


@login_required
@business_required
@permission_required("food.view_foodingredient", raise_exception=True)
def ingredient_option_list(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    ensure_default_ingredient_options(request.business)
    category_form = FoodIngredientCategoryForm(prefix="category")
    unit_form = FoodIngredientUnitForm(prefix="unit")

    if request.method == "POST":
        option_type = request.POST.get("option_type")
        if option_type == "category":
            category_form = FoodIngredientCategoryForm(request.POST, prefix="category")
            if category_form.is_valid():
                option = category_form.save(commit=False)
                option.business = request.business
                try:
                    option.save()
                except Exception:
                    messages.error(request, "Ja existe uma categoria com este codigo.")
                else:
                    messages.success(request, "Categoria adicionada.")
                    return redirect("food:ingredient_option_list")
            else:
                messages.error(request, "Revise os dados da categoria.")
        elif option_type == "unit":
            unit_form = FoodIngredientUnitForm(request.POST, prefix="unit")
            if unit_form.is_valid():
                option = unit_form.save(commit=False)
                option.business = request.business
                try:
                    option.save()
                except Exception:
                    messages.error(request, "Ja existe uma unidade com este codigo.")
                else:
                    messages.success(request, "Unidade adicionada.")
                    return redirect("food:ingredient_option_list")
            else:
                messages.error(request, "Revise os dados da unidade.")

    return render(
        request,
        "food/ingredient_option_list.html",
        {
            "category_form": category_form,
            "unit_form": unit_form,
            "categories": FoodIngredientCategory.objects.filter(
                business=request.business
            ).order_by("name"),
            "units": FoodIngredientUnit.objects.filter(
                business=request.business
            ).order_by("name"),
        },
    )


@login_required
@business_required
@permission_required("food.change_foodingredient", raise_exception=True)
def ingredient_adjust(request, pk):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    ingredient = get_object_or_404(request.business.food_ingredients, pk=pk)
    if request.method == "POST":
        form = IngredientAdjustmentForm(request.POST)
        if form.is_valid():
            try:
                adjust_ingredient_stock(
                    business=request.business,
                    ingredient=ingredient,
                    user=request.user,
                    adjustment_type=form.cleaned_data["adjustment_type"],
                    quantity=form.cleaned_data["quantity"],
                    notes=form.cleaned_data.get("notes", ""),
                )
            except Exception as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Stock ajustado.")
                return redirect("food:ingredient_list")
        else:
            messages.error(request, "Revise os dados do ajuste.")
    else:
        form = IngredientAdjustmentForm()

    return render(
        request,
        "food/ingredient_adjust_form.html",
        {
            "form": form,
            "ingredient": ingredient,
        },
    )


@login_required
@business_required
@permission_required("food.view_ingredientstockentry", raise_exception=True)
def ingredient_entry_list(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    entries = IngredientStockEntry.objects.filter(business=request.business).prefetch_related(
        "items__ingredient"
    )
    paginator = Paginator(entries.order_by("-entry_date", "-id"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "food/ingredient_entry_list.html", {"page": page})


@login_required
@business_required
@permission_required("food.add_ingredientstockentry", raise_exception=True)
def ingredient_entry_create(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    if request.method == "POST":
        form = IngredientStockEntryForm(request.POST, business=request.business)
        formset = IngredientStockEntryItemFormSet(
            request.POST,
            prefix="items",
            form_kwargs={
                "ingredients": request.business.food_ingredients.filter(is_active=True),
            },
        )
        if form.is_valid() and formset.is_valid():
            try:
                create_ingredient_entry(
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
        form = IngredientStockEntryForm(business=request.business)
        formset = IngredientStockEntryItemFormSet(
            prefix="items",
            form_kwargs={
                "ingredients": request.business.food_ingredients.filter(is_active=True),
            },
        )

    return render(
        request,
        "food/ingredient_entry_form.html",
        {
            "form": form,
            "formset": formset,
            "ingredient_preview": _ingredient_preview_data(request.business),
            "is_burger": request.business.business_type == Business.BUSINESS_BURGER,
        },
    )


@login_required
@business_required
@permission_required("food.view_ingredientmovement", raise_exception=True)
def ingredient_movement_list(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    ingredient_id = request.GET.get("ingredient", "").strip()
    movement_type = request.GET.get("movement_type", "").strip()
    movements = IngredientMovement.objects.filter(
        business=request.business
    ).select_related("ingredient", "created_by")
    if ingredient_id:
        movements = movements.filter(ingredient_id=ingredient_id)
    if movement_type:
        movements = movements.filter(movement_type=movement_type)

    paginator = Paginator(movements.order_by("-created_at", "-id"), 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "food/ingredient_movement_list.html",
        {
            "page": page,
            "ingredient_id": ingredient_id,
            "movement_type": movement_type,
            "ingredients": request.business.food_ingredients.order_by("name"),
            "movement_choices": IngredientMovement.MOVEMENT_CHOICES,
        },
    )


@login_required
@business_required
@permission_required("food.view_restauranttable", raise_exception=True)
def table_list(request):
    if not _tables_enabled(request.business):
        return redirect("reports:dashboard")

    RestaurantTable.objects.filter(
        business=request.business,
        is_active=True,
        status=RestaurantTable.STATUS_RESERVED,
        reserved_until__isnull=False,
        reserved_until__lte=timezone.now(),
    ).update(
        status=RestaurantTable.STATUS_FREE,
        reserved_for="",
        reserved_until=None,
    )

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    tables = RestaurantTable.objects.filter(
        business=request.business,
        is_active=True,
    ).order_by("name")
    if query:
        tables = tables.filter(name__icontains=query)
    if status:
        tables = tables.filter(status=status)

    open_orders = (
        Order.objects.filter(
            business=request.business,
            table__isnull=False,
            status__in=[
                Order.STATUS_CONFIRMED,
                Order.STATUS_IN_PREPARATION,
                Order.STATUS_READY,
            ],
        )
        .values("table_id")
        .annotate(total=Count("id"))
    )
    open_orders_map = {row["table_id"]: row["total"] for row in open_orders}
    paginator = Paginator(tables, 20)
    page = paginator.get_page(request.GET.get("page"))
    for table in page.object_list:
        table.open_orders = open_orders_map.get(table.id, 0)

    return render(
        request,
        "food/table_list.html",
        {
            "page": page,
            "query": query,
            "status": status,
            "status_choices": RestaurantTable.STATUS_CHOICES,
        },
    )


@login_required
@business_required
@permission_required("food.add_restauranttable", raise_exception=True)
def table_create(request):
    if not _tables_enabled(request.business):
        return redirect("reports:dashboard")

    if request.method == "POST":
        form = RestaurantTableForm(request.POST)
        if form.is_valid():
            table = form.save(commit=False)
            table.business = request.business
            table.save()
            messages.success(request, "Mesa criada.")
            return redirect("food:table_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = RestaurantTableForm()
    return render(request, "food/table_form.html", {"form": form})


@login_required
@business_required
@permission_required("food.change_restauranttable", raise_exception=True)
def table_edit(request, pk):
    if not _tables_enabled(request.business):
        return redirect("reports:dashboard")

    table = get_object_or_404(RestaurantTable, pk=pk, business=request.business)
    if request.method == "POST":
        form = RestaurantTableForm(request.POST, instance=table)
        if form.is_valid():
            form.save()
            messages.success(request, "Mesa atualizada.")
            return redirect("food:table_list")
        messages.error(request, "Revise os campos obrigatorios.")
    else:
        form = RestaurantTableForm(instance=table)
    return render(request, "food/table_form.html", {"form": form, "table": table})


@login_required
@business_required
@permission_required("food.change_restauranttable", raise_exception=True)
def table_set_status(request, pk):
    if request.method != "POST":
        return redirect("food:table_list")
    if not _tables_enabled(request.business):
        return redirect("reports:dashboard")

    table = get_object_or_404(RestaurantTable, pk=pk, business=request.business)
    status = request.POST.get("status")
    reserved_for = (request.POST.get("reserved_for") or "").strip()
    reserved_until_raw = (request.POST.get("reserved_until") or "").strip()
    allowed = {
        RestaurantTable.STATUS_FREE,
        RestaurantTable.STATUS_OCCUPIED,
        RestaurantTable.STATUS_RESERVED,
    }
    if status not in allowed:
        messages.error(request, "Estado invalido.")
        return redirect("food:table_list")

    if status == RestaurantTable.STATUS_FREE:
        has_open_orders = Order.objects.filter(
            business=request.business,
            table=table,
            status__in=[
                Order.STATUS_CONFIRMED,
                Order.STATUS_IN_PREPARATION,
                Order.STATUS_READY,
            ],
        ).exists()
        if has_open_orders:
            messages.error(request, "Nao pode libertar mesa com pedidos ativos.")
            return redirect("food:table_list")

    reservation_until = None
    if status == RestaurantTable.STATUS_RESERVED:
        reservation_until = parse_datetime(reserved_until_raw) if reserved_until_raw else None
        if reservation_until is None:
            reservation_until = table.reserved_until or (timezone.now() + timedelta(hours=2))
        elif timezone.is_naive(reservation_until):
            reservation_until = timezone.make_aware(
                reservation_until, timezone.get_current_timezone()
            )
        if reservation_until <= timezone.now():
            messages.error(request, "Reserva invalida: a data/hora deve ser futura.")
            return redirect("food:table_list")
        if not reserved_for:
            reserved_for = table.reserved_for or "Reserva"

    table.status = status
    if status == RestaurantTable.STATUS_RESERVED:
        table.reserved_for = reserved_for
        table.reserved_until = reservation_until
    else:
        table.reserved_for = ""
        table.reserved_until = None
    table.save(update_fields=["status", "reserved_for", "reserved_until", "updated_at"])
    messages.success(request, "Estado da mesa atualizado.")
    return redirect("food:table_list")


@login_required
@business_required
@permission_required("food.view_order", raise_exception=True)
def kds(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    now = timezone.localtime()
    orders = (
        Order.objects.filter(
            business=request.business,
            status__in=[
                Order.STATUS_CONFIRMED,
                Order.STATUS_IN_PREPARATION,
                Order.STATUS_READY,
            ],
        )
        .select_related("customer", "table")
        .prefetch_related("items__menu_item", "items__extras__extra")
        .order_by("created_at")
    )
    grouped = {
        Order.STATUS_CONFIRMED: [],
        Order.STATUS_IN_PREPARATION: [],
        Order.STATUS_READY: [],
    }
    for order in orders:
        elapsed = now - timezone.localtime(order.created_at)
        wait_minutes = max(int(elapsed.total_seconds() // 60), 0)
        order.wait_minutes = wait_minutes
        order.priority = "critical" if wait_minutes >= 25 else "warning" if wait_minutes >= 12 else "normal"
        order.outstanding = max(order.total - order.amount_paid, Decimal("0"))
        order.can_deliver = order.outstanding <= 0
        grouped.get(order.status, []).append(order)

    return render(
        request,
        "food/kds.html",
        {
            "orders": orders,
            "grouped": grouped,
            "kpi": {
                "new": len(grouped[Order.STATUS_CONFIRMED]),
                "preparing": len(grouped[Order.STATUS_IN_PREPARATION]),
                "ready": len(grouped[Order.STATUS_READY]),
                "total": len(orders),
            },
        },
    )


@login_required
@business_required
@permission_required("food.change_order", raise_exception=True)
def update_status(request, pk):
    if request.method != "POST":
        return redirect("food:kds")
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    order = get_object_or_404(Order, pk=pk, business=request.business)
    status = request.POST.get("status")
    next_url = request.POST.get("next") or request.GET.get("next")
    try:
        update_order_status(order=order, status=status, user=request.user)
        messages.success(request, "Estado atualizado.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect(next_url or "food:kds")


@login_required
@business_required
@permission_required("food.view_order", raise_exception=True)
def cashflow_dashboard(request):
    if not _food_enabled(request.business) or request.business.business_type != Business.BUSINESS_BURGER:
        return redirect("reports:dashboard")
    _ensure_financial_write_permission(request.user)
    if not request.business.module_cashflow_enabled:
        messages.error(request, "Modulo financeiro desativado para esta hamburgueria.")
        return redirect("food:order_list")

    ensure_default_payment_methods(request.business)
    account_choices = list(
        FinancialAccount.objects.filter(business=request.business).order_by("category", "name")
    )
    method_choices = list(
        PaymentMethod.objects.filter(business=request.business, is_active=True)
        .select_related("account")
        .order_by("name")
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "add_account":
            name = (request.POST.get("account_name") or "").strip()
            category = (request.POST.get("account_category") or "").strip()
            is_active = request.POST.get("account_is_active") == "on"
            valid_categories = {key for key, _ in FinancialAccount.CATEGORY_CHOICES}
            if not name:
                messages.error(request, "Informe o nome da conta.")
            elif category not in valid_categories:
                messages.error(request, "Categoria de conta invalida.")
            else:
                try:
                    FinancialAccount.objects.create(
                        business=request.business,
                        name=name,
                        category=category,
                        is_active=is_active,
                    )
                    messages.success(request, "Conta financeira criada.")
                except IntegrityError:
                    messages.error(request, "Ja existe uma conta com este nome.")
        elif action == "toggle_account":
            account_id = request.POST.get("account_id")
            account = FinancialAccount.objects.filter(
                business=request.business,
                id=account_id,
            ).first()
            if not account:
                messages.error(request, "Conta nao encontrada.")
            else:
                account.is_active = not account.is_active
                account.save(update_fields=["is_active", "updated_at"])
                state = "ativada" if account.is_active else "desativada"
                messages.success(request, f"Conta {state}.")
        elif action == "add_movement":
            movement_type = (request.POST.get("movement_type") or "").strip()
            method_code = (request.POST.get("method") or CashMovement.METHOD_CASH).strip()
            account_id = (request.POST.get("account") or "").strip()
            reference_type = (request.POST.get("reference_type") or "burger_manual").strip()
            happened_on = parse_date((request.POST.get("happened_on") or "").strip())
            notes = (request.POST.get("notes") or "").strip()
            valid_movements = {CashMovement.MOVEMENT_IN, CashMovement.MOVEMENT_OUT}
            valid_methods = {key for key, _ in CashMovement.METHOD_CHOICES}
            try:
                amount = _parse_money_input(request.POST.get("amount"))
            except Exception:
                amount = None
            if movement_type not in valid_movements:
                messages.error(request, "Tipo de movimento invalido.")
            elif method_code not in valid_methods:
                messages.error(request, "Metodo de pagamento invalido.")
            elif amount is None or amount <= 0:
                messages.error(request, "Informe um valor valido.")
            else:
                selected_account = None
                if account_id:
                    selected_account = FinancialAccount.objects.filter(
                        business=request.business,
                        id=account_id,
                    ).first()
                payment_method = PaymentMethod.objects.filter(
                    business=request.business,
                    code=method_code,
                    is_active=True,
                ).select_related("account").first()
                if not selected_account and payment_method and payment_method.account_id:
                    selected_account = payment_method.account
                if not selected_account:
                    category_map = dict(PaymentMethod.objects.filter(
                        business=request.business,
                        is_active=True,
                    ).values_list("code", "category"))
                    fallback_category = category_map.get(
                        method_code,
                        FinancialAccount.CATEGORY_CASH,
                    )
                    selected_account = FinancialAccount.objects.filter(
                        business=request.business,
                        category=fallback_category,
                        is_active=True,
                    ).order_by("id").first()
                if not selected_account:
                    messages.error(request, "Crie uma conta financeira antes de lançar movimentos.")
                else:
                    movement = CashMovement.objects.create(
                        business=request.business,
                        payment_method=payment_method,
                        category=selected_account.category,
                        account=selected_account,
                        movement_type=movement_type,
                        amount=amount,
                        method=method_code,
                        reference_type=reference_type or "burger_manual",
                        notes=notes,
                        happened_at=_compose_happened_at(happened_on or timezone.localdate()),
                        created_by=request.user,
                    )
                    direction = "Entrada" if movement.movement_type == CashMovement.MOVEMENT_IN else "Saida"
                    messages.success(request, f"{direction} registada em {movement.account.name}.")
        return redirect("food:cashflow_dashboard")

    today = timezone.localdate()
    date_from = parse_date((request.GET.get("date_from") or "").strip()) or today
    date_to = parse_date((request.GET.get("date_to") or "").strip()) or today
    if date_to < date_from:
        date_from, date_to = date_to, date_from
    movement_type = (request.GET.get("movement_type") or "").strip()
    account_id = (request.GET.get("account") or "").strip()
    method = (request.GET.get("method") or "").strip()

    base_movements = CashMovement.objects.filter(
        business=request.business,
        happened_at__date__gte=date_from,
        happened_at__date__lte=date_to,
    ).select_related("account", "payment_method", "created_by")

    movements = base_movements
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    if account_id:
        movements = movements.filter(account_id=account_id)
    if method:
        movements = movements.filter(method=method)

    totals = movements.aggregate(
        total_in=Coalesce(
            Sum("amount", filter=Q(movement_type=CashMovement.MOVEMENT_IN)),
            Decimal("0"),
        ),
        total_out=Coalesce(
            Sum("amount", filter=Q(movement_type=CashMovement.MOVEMENT_OUT)),
            Decimal("0"),
        ),
    )
    total_in = totals["total_in"]
    total_out = totals["total_out"]
    net_total = total_in - total_out

    source_totals = []
    source_rows = (
        movements.values("reference_type")
        .annotate(
            total_in=Coalesce(
                Sum("amount", filter=Q(movement_type=CashMovement.MOVEMENT_IN)),
                Decimal("0"),
            ),
            total_out=Coalesce(
                Sum("amount", filter=Q(movement_type=CashMovement.MOVEMENT_OUT)),
                Decimal("0"),
            ),
            movement_count=Count("id"),
        )
        .order_by("-movement_count", "-total_in", "-total_out")
    )
    for row in source_rows:
        source_totals.append(
            {
                "label": _cashflow_reference_label(row["reference_type"]),
                "reference_type": row["reference_type"] or "",
                "movement_count": row["movement_count"],
                "total_in": row["total_in"],
                "total_out": row["total_out"],
                "net_total": row["total_in"] - row["total_out"],
            }
        )

    account_totals_map = {
        row["account_id"]: row
        for row in movements.values("account_id")
        .annotate(
            total_in=Coalesce(
                Sum("amount", filter=Q(movement_type=CashMovement.MOVEMENT_IN)),
                Decimal("0"),
            ),
            total_out=Coalesce(
                Sum("amount", filter=Q(movement_type=CashMovement.MOVEMENT_OUT)),
                Decimal("0"),
            ),
            movement_count=Count("id"),
        )
    }
    payment_method_map = {}
    for method_row in method_choices:
        payment_method_map.setdefault(method_row.account_id, []).append(method_row.name)
    account_summary = []
    for account in account_choices:
        totals_row = account_totals_map.get(account.id, {})
        acc_total_in = totals_row.get("total_in", Decimal("0"))
        acc_total_out = totals_row.get("total_out", Decimal("0"))
        account_summary.append(
            {
                "account": account,
                "methods": payment_method_map.get(account.id, []),
                "total_in": acc_total_in,
                "total_out": acc_total_out,
                "net_total": acc_total_in - acc_total_out,
                "movement_count": totals_row.get("movement_count", 0),
            }
        )
    account_summary.sort(
        key=lambda item: (
            item["account"].category,
            -item["net_total"],
            item["account"].name.lower(),
        )
    )

    series_rows = (
        movements.values("happened_at__date")
        .annotate(
            total_in=Coalesce(
                Sum("amount", filter=Q(movement_type=CashMovement.MOVEMENT_IN)),
                Decimal("0"),
            ),
            total_out=Coalesce(
                Sum("amount", filter=Q(movement_type=CashMovement.MOVEMENT_OUT)),
                Decimal("0"),
            ),
        )
        .order_by("happened_at__date")
    )
    series_map = {row["happened_at__date"]: row for row in series_rows}
    series_labels = []
    series_in = []
    series_out = []
    cursor = date_from
    max_days = 120
    while cursor <= date_to and len(series_labels) < max_days:
        row = series_map.get(cursor)
        series_labels.append(cursor.strftime("%d/%m"))
        series_in.append(float((row or {}).get("total_in", Decimal("0"))))
        series_out.append(float((row or {}).get("total_out", Decimal("0"))))
        cursor += timedelta(days=1)

    pending_orders = Order.objects.filter(
        business=request.business,
        payment_status__in=[Order.PAYMENT_UNPAID, Order.PAYMENT_PARTIAL],
    ).exclude(status=Order.STATUS_CANCELED)
    pending_order_total = pending_orders.aggregate(
        total=Coalesce(Sum(F("total") - F("amount_paid")), Decimal("0"))
    ).get("total")
    pending_order_count = pending_orders.count()
    pending_purchase_total = Purchase.objects.filter(
        business=request.business,
        status=Purchase.STATUS_DRAFT,
    ).aggregate(total=Coalesce(Sum("total"), Decimal("0"))).get("total")
    pending_purchase_count = Purchase.objects.filter(
        business=request.business,
        status=Purchase.STATUS_DRAFT,
    ).count()
    pending_expense_total = Expense.objects.filter(
        business=request.business,
        status=Expense.STATUS_DRAFT,
    ).aggregate(total=Coalesce(Sum("amount"), Decimal("0"))).get("total")
    pending_expense_count = Expense.objects.filter(
        business=request.business,
        status=Expense.STATUS_DRAFT,
    ).count()

    paginator = Paginator(movements.order_by("-happened_at", "-id"), 25)
    page = paginator.get_page(request.GET.get("page"))
    for movement in page.object_list:
        movement.reference_label = _cashflow_reference_label(movement.reference_type)

    return render(
        request,
        "food/cashflow_dashboard.html",
        {
            "date_from": date_from,
            "date_to": date_to,
            "movement_type": movement_type,
            "account_id": account_id,
            "method": method,
            "page": page,
            "movement_choices": CashMovement.MOVEMENT_CHOICES,
            "method_choices": CashMovement.METHOD_CHOICES,
            "account_choices": account_choices,
            "method_options": method_choices,
            "total_in": total_in,
            "total_out": total_out,
            "net_total": net_total,
            "source_totals": source_totals,
            "account_summary": account_summary,
            "series_labels": series_labels,
            "series_in": series_in,
            "series_out": series_out,
            "pending_order_total": pending_order_total,
            "pending_order_count": pending_order_count,
            "pending_purchase_total": pending_purchase_total,
            "pending_purchase_count": pending_purchase_count,
            "pending_expense_total": pending_expense_total,
            "pending_expense_count": pending_expense_count,
            "category_choices": FinancialAccount.CATEGORY_CHOICES,
        },
    )


@login_required
@business_required
@permission_required("food.view_order", raise_exception=True)
def operations_report(request):
    if not _food_enabled(request.business):
        return redirect("reports:dashboard")

    today = timezone.localdate()
    date_from = parse_date((request.GET.get("date_from") or "").strip()) or today
    date_to = parse_date((request.GET.get("date_to") or "").strip()) or today
    if date_to < date_from:
        date_from, date_to = date_to, date_from

    orders = Order.objects.filter(
        business=request.business,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )
    valid_orders = orders.exclude(status=Order.STATUS_CANCELED)

    sales_total = valid_orders.aggregate(total=Coalesce(Sum("total"), Decimal("0"))).get("total")
    orders_count = valid_orders.count()
    canceled_count = orders.filter(status=Order.STATUS_CANCELED).count()
    ticket_avg = (sales_total / orders_count) if orders_count else Decimal("0")

    channel_breakdown = list(
        valid_orders.values("channel")
        .annotate(count=Count("id"), total=Coalesce(Sum("total"), Decimal("0")))
        .order_by("-count")
    )

    top_products = list(
        OrderItem.objects.filter(
            order__business=request.business,
            order__created_at__date__gte=date_from,
            order__created_at__date__lte=date_to,
            order__status__in=[
                Order.STATUS_CONFIRMED,
                Order.STATUS_IN_PREPARATION,
                Order.STATUS_READY,
                Order.STATUS_DELIVERED,
            ],
        )
        .values("menu_item__name")
        .annotate(qty=Coalesce(Sum("quantity"), 0), total=Coalesce(Sum("line_total"), Decimal("0")))
        .order_by("-qty", "-total")[:12]
    )

    category_performance = list(
        OrderItem.objects.filter(
            order__business=request.business,
            order__created_at__date__gte=date_from,
            order__created_at__date__lte=date_to,
            order__status__in=[
                Order.STATUS_CONFIRMED,
                Order.STATUS_IN_PREPARATION,
                Order.STATUS_READY,
                Order.STATUS_DELIVERED,
            ],
        )
        .values("menu_item__category__name")
        .annotate(qty=Coalesce(Sum("quantity"), 0), total=Coalesce(Sum("line_total"), Decimal("0")))
        .order_by("-total")
    )

    peak_hours = list(
        valid_orders.annotate(hour=ExtractHour("created_at"))
        .values("hour")
        .annotate(total=Count("id"))
        .order_by("-total", "hour")[:6]
    )

    ingredient_usage = list(
        IngredientMovement.objects.filter(
            business=request.business,
            movement_type=IngredientMovement.MOVEMENT_OUT,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )
        .values("ingredient__name")
        .annotate(total=Coalesce(Sum("quantity"), Decimal("0")))
        .order_by("-total")[:12]
    )

    return render(
        request,
        "food/operations_report.html",
        {
            "date_from": date_from,
            "date_to": date_to,
            "sales_total": sales_total,
            "orders_count": orders_count,
            "canceled_count": canceled_count,
            "ticket_avg": ticket_avg,
            "channel_breakdown": channel_breakdown,
            "top_products": top_products,
            "category_performance": category_performance,
            "peak_hours": peak_hours,
            "ingredient_usage": ingredient_usage,
        },
    )


def _product_prices(business):
    return {
        str(prod.id): {"sale": float(prod.selling_price)}
        for prod in MenuItem.objects.filter(business=business, is_active=True)
    }


def _extra_prices(business):
    return {
        str(extra.id): float(extra.extra_price)
        for extra in FoodExtra.objects.filter(business=business, is_active=True)
    }


def _ingredient_stock_status(ingredient):
    if not ingredient.stock_control:
        return "inactive"
    if ingredient.reorder_level is None:
        return "healthy"
    if ingredient.stock_qty <= ingredient.reorder_level:
        return "critical"
    near_limit = ingredient.reorder_level * Decimal("1.25")
    if ingredient.stock_qty <= near_limit:
        return "near"
    return "healthy"


def _ingredient_preview_data(business):
    return {
        str(ingredient.id): {
            "name": ingredient.name,
            "unit": ingredient.unit or "unidade base",
            "stock": float(ingredient.stock_qty),
            "cost": float(ingredient.cost_price or 0),
        }
        for ingredient in business.food_ingredients.filter(is_active=True).order_by("name")
    }


def _format_minutes_label(total_minutes):
    safe = max(int(total_minutes), 0)
    hours, minutes = divmod(safe, 60)
    if hours:
        return f"{hours}h {minutes}min"
    return f"{minutes}min"


def _format_datetime_label(value):
    if not value:
        return ""
    return timezone.localtime(value).strftime("%d/%m %H:%M")


def _attach_order_timing(order):
    order.duration_label = ""
    order.dispatch_label = ""
    order.received_label = ""
    delivered_at = getattr(order, "delivered_at", None)
    ready_at = getattr(order, "ready_at", None)
    if delivered_at:
        elapsed = delivered_at - order.created_at
        total_minutes = int(elapsed.total_seconds() // 60)
        order.duration_label = _format_minutes_label(total_minutes)
    if order.channel == Order.CHANNEL_DELIVERY:
        order.dispatch_label = _format_datetime_label(ready_at)
    order.received_label = _format_datetime_label(delivered_at)


def _cashflow_reference_label(reference_type):
    normalized = (reference_type or "").strip().lower()
    labels = {
        "order": "Pagamento de pedido",
        "invoice_payment": "Pagamento de fatura",
        "purchase": "Compra",
        "purchase_cancel": "Estorno de compra",
        "expense": "Despesa",
        "expense_cancel": "Estorno de despesa",
        "burger_manual": "Lançamento manual",
        "manual": "Lançamento manual",
    }
    if normalized in labels:
        return labels[normalized]
    if not normalized:
        return "Sem referência"
    return normalized.replace("_", " ").title()


def _parse_money_input(raw_value):
    cleaned = (raw_value or "").strip().replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    return Decimal(cleaned)


def _compose_happened_at(date_value):
    current_time = timezone.localtime().time().replace(microsecond=0)
    naive = datetime.combine(date_value, current_time)
    return timezone.make_aware(naive, timezone.get_current_timezone())
