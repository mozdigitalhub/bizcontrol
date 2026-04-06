from django.urls import path

from inventory import views

app_name = "inventory"

urlpatterns = [
    path("", views.stock_list, name="stock_list"),
    path("movements/", views.movement_list, name="movement_list"),
    path("products/<int:pk>/movements/", views.product_movements, name="product_movements"),
    path("new/", views.movement_create, name="movement_create"),
    path("receipts/", views.receipt_list, name="receipt_list"),
    path("receipts/new/", views.receipt_create, name="receipt_create"),
    path("receipts/<int:pk>/", views.receipt_detail, name="receipt_detail"),
    path("import/", views.stock_import, name="stock_import"),
]
