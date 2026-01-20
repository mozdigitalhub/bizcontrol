from django.urls import path

from quotations import views


app_name = "quotations"

urlpatterns = [
    path("", views.quotation_list, name="list"),
    path("new/", views.quotation_create, name="create"),
    path("<int:pk>/", views.quotation_detail, name="detail"),
    path("<int:pk>/edit/", views.quotation_edit, name="edit"),
    path("<int:pk>/approve/", views.quotation_approve, name="approve"),
    path("<int:pk>/stock-check/", views.quotation_stock_check, name="stock_check"),
    path("<int:pk>/reject/", views.quotation_reject, name="reject"),
    path("<int:pk>/cancel/", views.quotation_cancel, name="cancel"),
    path("<int:pk>/duplicate/", views.quotation_duplicate, name="duplicate"),
    path("<int:pk>/pdf/", views.quotation_pdf_view, name="pdf_view"),
]
