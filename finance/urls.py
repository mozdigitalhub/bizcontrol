from django.urls import path

from finance import views


app_name = "finance"

urlpatterns = [
    path("cashflow/", views.cashflow_list, name="cashflow_list"),
    path("cashflow/<int:pk>/modal/", views.cashflow_detail_modal, name="cashflow_detail_modal"),
    path("purchases/", views.purchase_list, name="purchase_list"),
    path("purchases/new/", views.purchase_create, name="purchase_create"),
    path("purchases/<int:pk>/", views.purchase_detail, name="purchase_detail"),
    path("purchases/<int:pk>/cancel/", views.purchase_cancel, name="purchase_cancel"),
    path("expenses/", views.expense_list, name="expense_list"),
    path("expenses/new/", views.expense_create, name="expense_create"),
    path("expenses/<int:pk>/", views.expense_detail, name="expense_detail"),
    path("expenses/<int:pk>/cancel/", views.expense_cancel, name="expense_cancel"),
    path("suppliers/new/", views.supplier_create, name="supplier_create"),
    path("expense-categories/new/", views.expense_category_create, name="expense_category_create"),
]
