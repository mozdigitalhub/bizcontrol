from django.urls import path

from food import views

app_name = "food"

urlpatterns = [
    path("tables/", views.table_list, name="table_list"),
    path("tables/new/", views.table_create, name="table_create"),
    path("tables/<int:pk>/edit/", views.table_edit, name="table_edit"),
    path("tables/<int:pk>/status/", views.table_set_status, name="table_status"),
    path("menu/", views.menu_list, name="menu_list"),
    path("menu/new/", views.menu_create, name="menu_create"),
    path("menu/<int:pk>/edit/", views.menu_edit, name="menu_edit"),
    path("ingredients/", views.ingredient_list, name="ingredient_list"),
    path("ingredients/new/", views.ingredient_create, name="ingredient_create"),
    path("ingredients/<int:pk>/edit/", views.ingredient_edit, name="ingredient_edit"),
    path("ingredients/entries/", views.ingredient_entry_list, name="ingredient_entry_list"),
    path("ingredients/entries/new/", views.ingredient_entry_create, name="ingredient_entry_create"),
    path("orders/", views.order_list, name="order_list"),
    path("orders/new/", views.order_create, name="order_create"),
    path("kds/", views.kds, name="kds"),
    path("orders/<int:pk>/status/", views.update_status, name="order_status"),
]
