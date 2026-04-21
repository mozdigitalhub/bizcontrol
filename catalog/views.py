from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from catalog.forms import CategoryForm, ProductForm, ProductVariantForm
from catalog.models import Category, Product, ProductVariant
from inventory.services import get_product_stock
from tenants.decorators import business_required, module_required
from tenants.models import Business


@login_required
@business_required
@module_required(Business.MODULE_CATALOG, message="Catalogo desativado para este negocio.")
@permission_required("catalog.view_product", raise_exception=True)
def product_list(request):
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    status = request.GET.get("status", "").strip()
    products = (
        Product.objects.filter(business=request.business)
        .select_related("category")
        .annotate(variant_count=Count("variants"))
    )
    if query:
        products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    if category_id:
        products = products.filter(category_id=category_id)
    if status == "active":
        products = products.filter(is_active=True)
    elif status == "inactive":
        products = products.filter(is_active=False)
    total_products = products.count()
    active_count = products.filter(is_active=True).count()
    inactive_count = products.filter(is_active=False).count()
    paginator = Paginator(products.order_by("name"), 20)
    page = paginator.get_page(request.GET.get("page"))
    for product in page.object_list:
        product.stock_quantity = get_product_stock(request.business, product)
    categories = Category.objects.filter(business=request.business).order_by("name")
    return render(
        request,
        "catalog/product_list.html",
        {
            "page": page,
            "query": query,
            "category_id": category_id,
            "status": status,
            "categories": categories,
            "total_products": total_products,
            "active_count": active_count,
            "inactive_count": inactive_count,
        },
    )


@login_required
@business_required
@module_required(Business.MODULE_CATALOG, message="Catalogo desativado para este negocio.")
@permission_required("catalog.add_product", raise_exception=True)
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST)
        form.fields["category"].queryset = Category.objects.filter(
            business=request.business
        )
        if form.is_valid():
            product = form.save(commit=False)
            product.business = request.business
            product.created_by = request.user
            product.save()
            messages.success(request, "Produto criado com sucesso.")
            if request.headers.get("HX-Request"):
                form = ProductForm()
                form.fields["category"].queryset = Category.objects.filter(
                    business=request.business
                )
                return render(
                    request,
                    "catalog/partials/product_modal.html",
                    {"form": form, "created": True},
                )
            return redirect("catalog:product_list")
    else:
        form = ProductForm()
        form.fields["category"].queryset = Category.objects.filter(
            business=request.business
        )
    if request.headers.get("HX-Request"):
        return render(request, "catalog/partials/product_modal.html", {"form": form})
    return render(request, "catalog/product_form.html", {"form": form})


@login_required
@business_required
@module_required(Business.MODULE_CATALOG, message="Catalogo desativado para este negocio.")
@permission_required("catalog.change_product", raise_exception=True)
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk, business=request.business)
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        form.fields["category"].queryset = Category.objects.filter(
            business=request.business
        )
        if form.is_valid():
            product = form.save(commit=False)
            product.updated_by = request.user
            product.save()
            messages.success(request, "Produto atualizado com sucesso.")
            if request.headers.get("HX-Request"):
                return render(
                    request,
                    "catalog/partials/product_edit_modal.html",
                    {"form": form, "product": product, "updated": True},
                )
            return redirect("catalog:product_list")
    else:
        form = ProductForm(instance=product)
        form.fields["category"].queryset = Category.objects.filter(
            business=request.business
        )
    if request.headers.get("HX-Request"):
        return render(
            request,
            "catalog/partials/product_edit_modal.html",
            {"form": form, "product": product},
        )
    return render(
        request, "catalog/product_form.html", {"form": form, "product": product}
    )


@login_required
@business_required
@module_required(Business.MODULE_CATALOG, message="Catalogo desativado para este negocio.")
@permission_required("catalog.view_product", raise_exception=True)
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, business=request.business)
    if request.headers.get("HX-Request"):
        return render(
            request, "catalog/partials/product_detail_modal.html", {"product": product}
        )
    return render(request, "catalog/product_detail.html", {"product": product})


@login_required
@business_required
@module_required(Business.MODULE_CATALOG, message="Catalogo desativado para este negocio.")
@permission_required("catalog.add_category", raise_exception=True)
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.business = request.business
            category.save()
            form = CategoryForm()
            return render(
                request,
                "catalog/partials/category_modal.html",
                {"form": form, "created": True, "category": category},
            )
    else:
        form = CategoryForm()
    return render(request, "catalog/partials/category_modal.html", {"form": form})


@login_required
@business_required
@module_required(Business.MODULE_CATALOG, message="Catalogo desativado para este negocio.")
@permission_required("catalog.delete_product", raise_exception=True)
def product_delete(request, pk):
    if request.method != "POST":
        return redirect("catalog:product_list")
    product = get_object_or_404(Product, pk=pk, business=request.business)
    product.delete()
    messages.success(request, "Produto removido com sucesso.")
    return redirect("catalog:product_list")


@login_required
@business_required
@module_required(Business.MODULE_CATALOG, message="Catalogo desativado para este negocio.")
@permission_required("catalog.view_productvariant", raise_exception=True)
def variant_list(request, product_id):
    product = get_object_or_404(Product, id=product_id, business=request.business)
    variants = product.variants.order_by("name", "size", "color")
    return render(
        request,
        "catalog/variant_list.html",
        {"product": product, "variants": variants},
    )


@login_required
@business_required
@module_required(Business.MODULE_CATALOG, message="Catalogo desativado para este negocio.")
@permission_required("catalog.add_productvariant", raise_exception=True)
def variant_create(request, product_id):
    product = get_object_or_404(Product, id=product_id, business=request.business)
    if request.method == "POST":
        form = ProductVariantForm(request.POST)
        if form.is_valid():
            variant = form.save(commit=False)
            variant.product = product
            if not variant.sale_price:
                variant.sale_price = product.sale_price
            variant.save()
            messages.success(request, "Variacao criada com sucesso.")
            return redirect("catalog:variant_list", product_id=product.id)
    else:
        form = ProductVariantForm(initial={"sale_price": product.sale_price})
    return render(
        request,
        "catalog/variant_form.html",
        {"form": form, "product": product},
    )


@login_required
@business_required
@module_required(Business.MODULE_CATALOG, message="Catalogo desativado para este negocio.")
@permission_required("catalog.change_productvariant", raise_exception=True)
def variant_edit(request, product_id, variant_id):
    product = get_object_or_404(Product, id=product_id, business=request.business)
    variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
    if request.method == "POST":
        form = ProductVariantForm(request.POST, instance=variant)
        if form.is_valid():
            form.save()
            messages.success(request, "Variacao atualizada com sucesso.")
            return redirect("catalog:variant_list", product_id=product.id)
    else:
        form = ProductVariantForm(instance=variant)
    return render(
        request,
        "catalog/variant_form.html",
        {"form": form, "product": product, "variant": variant},
    )
