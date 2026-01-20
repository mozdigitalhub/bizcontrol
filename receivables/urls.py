from django.urls import path

from receivables import views

app_name = "receivables"

urlpatterns = [
    path("", views.receivable_list, name="list"),
    path("<int:pk>/", views.receivable_detail, name="detail"),
    path("<int:pk>/pay/", views.payment_create, name="pay"),
    path("<int:pk>/pay/modal/", views.payment_modal, name="pay_modal"),
]
