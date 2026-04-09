from django.urls import path

from sales import views

app_name = "sales"

urlpatterns = [
    path("", views.sale_list, name="list"),
    path("new/", views.sale_new, name="new"),
    path("<int:pk>/", views.sale_detail, name="detail"),
    path("<int:pk>/items/add/", views.sale_add_item, name="add_item"),
    path("<int:pk>/items/<int:item_id>/remove/", views.sale_remove_item, name="remove_item"),
    path("<int:pk>/confirm/", views.sale_confirm, name="confirm"),
    path("<int:pk>/cancel/", views.sale_cancel, name="cancel"),
    path("<int:pk>/discount/", views.sale_update_discount, name="discount_update"),
    path("products/<int:product_id>/stock/", views.sale_product_stock, name="product_stock"),
    path(
        "products/<int:product_id>/price/",
        views.sale_product_price_update,
        name="product_price_update",
    ),
    path(
        "customers/<int:customer_id>/open-debt/",
        views.customer_open_debt,
        name="customer_open_debt",
    ),
]
