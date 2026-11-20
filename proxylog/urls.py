from django.urls import path

from . import views

app_name = "proxylog"

urlpatterns = [
    path("scan/", views.scan, name="scan"),
    path("farmer/<str:code>/", views.farmer_workspace, name="farmer_workspace"),
    path("farmer/<str:code>/deposit/", views.deposit_create, name="deposit_create"),
    path("farmer/<str:code>/rental/", views.rental_create, name="rental_create"),
    path("deposits/<int:pk>/edit/", views.deposit_edit, name="deposit_edit"),
    path("deposits/<int:pk>/delete/", views.deposit_delete, name="deposit_delete"),
    path("rentals/<int:pk>/return/", views.rental_return, name="rental_return"),
    path("rentals/<int:pk>/delete/", views.rental_delete, name="rental_delete"),
    path("transactions/", views.transaction_log, name="transaction_log"),
    path("cards/", views.card_list, name="card_list"),
    path("cards/<str:code>/", views.card_print, name="card_print"),
    path("my/qr/", views.my_qr, name="my_qr"),
    path("my/contributions/", views.my_contributions, name="my_contributions"),
]
