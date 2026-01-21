from django.urls import path

from reports import views

app_name = "reports"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("reports/overview/", views.overview, name="overview"),
    path("reports/sales/", views.sales_report, name="sales"),
    path("reports/payments/", views.payment_methods_report, name="payments"),
    path("reports/cashflow/", views.cashflow_report, name="cashflow"),
    path("reports/stock/", views.stock_report, name="stock"),
    path("reports/receivables/", views.receivables_report, name="receivables"),
    path("reports/staff/", views.staff_report, name="staff"),
]
