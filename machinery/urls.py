from django.urls import path

from . import views

app_name = "machinery"

urlpatterns = [
    path("machines/", views.machine_list, name="machine_list"),
    path("machines/new/", views.machine_create, name="machine_create"),
    path("machines/<int:pk>/edit/", views.machine_edit, name="machine_edit"),
    path("machines/<int:pk>/delete/", views.machine_delete, name="machine_delete"),
    # farmer
    path("catalog/", views.machine_catalog, name="machine_catalog"),
    path("reservations/", views.my_reservations, name="my_reservations"),
    path("reservations/new/", views.reservation_create, name="reservation_create"),
    path("reservations/<int:pk>/", views.reservation_detail, name="reservation_detail"),
    path("reservations/<int:pk>/edit/", views.reservation_edit, name="reservation_edit"),
    path("reservations/<int:pk>/cancel/", views.reservation_cancel, name="reservation_cancel"),
    path("reservations/<int:pk>/delete/", views.reservation_delete, name="reservation_delete"),
    # cooperative admin
    path("manage/reservations/", views.reservation_manage, name="reservation_manage"),
    path("manage/reservations/<int:pk>/review/", views.reservation_review, name="reservation_review"),
    path("manage/reservations/<int:pk>/complete/", views.reservation_complete, name="reservation_complete"),
]
