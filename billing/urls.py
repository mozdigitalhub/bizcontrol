from django.urls import path

from billing import views

app_name = "billing"

urlpatterns = [
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/pay/modal/", views.invoice_payment_modal, name="invoice_pay_modal"),
    path("invoices/<int:pk>/pay/", views.invoice_payment_create, name="invoice_pay"),
    path("invoices/<int:pk>/pdf/", views.invoice_pdf_view, name="invoice_pdf"),
    path("invoices/<int:pk>/pdf/download/", views.invoice_pdf_download, name="invoice_pdf_download"),
    path("invoices/<int:pk>/email/", views.invoice_email_modal, name="invoice_email"),
    path("invoices/sale/<int:sale_id>/create/", views.invoice_create_from_sale, name="invoice_create"),
    path("receipts/", views.receipt_list, name="receipt_list"),
    path("receipts/<int:pk>/", views.receipt_detail, name="receipt_detail"),
    path("receipts/<int:pk>/pdf/", views.receipt_pdf_view, name="receipt_pdf"),
    path("receipts/<int:pk>/pdf/download/", views.receipt_pdf_download, name="receipt_pdf_download"),
    path("receipts/<int:pk>/email/", views.receipt_email_modal, name="receipt_email"),
]
