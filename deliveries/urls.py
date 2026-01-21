from django.urls import path

from deliveries import views


app_name = "deliveries"

urlpatterns = [
    path("guides/", views.guide_list, name="guide_list"),
    path("guides/<int:pk>/", views.guide_detail, name="guide_detail"),
    path("guides/<int:pk>/pdf/", views.guide_pdf_view, name="guide_pdf"),
    path("guides/<int:pk>/pdf/download/", views.guide_pdf_download, name="guide_pdf_download"),
    path("guides/<int:pk>/email/", views.guide_email_modal, name="guide_email"),
    path("guides/<int:pk>/cancel/", views.guide_cancel, name="guide_cancel"),
    path("sales/<int:sale_id>/new/", views.guide_create_modal, name="guide_create_modal"),
    path("sales/<int:sale_id>/create/", views.guide_create, name="guide_create"),
]
