from django.urls import path

from catalog import views

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("new/", views.product_create, name="product_create"),
    path("categories/new/", views.category_create, name="category_create"),
    path("<int:product_id>/variants/", views.variant_list, name="variant_list"),
    path("<int:product_id>/variants/new/", views.variant_create, name="variant_create"),
    path(
        "<int:product_id>/variants/<int:variant_id>/edit/",
        views.variant_edit,
        name="variant_edit",
    ),
    path("<int:pk>/", views.product_detail, name="product_detail"),
    path("<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("<int:pk>/delete/", views.product_delete, name="product_delete"),
]
