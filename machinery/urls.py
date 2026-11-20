from django.urls import path

from . import views

app_name = "machinery"

urlpatterns = [
    path("machines/", views.machine_list, name="machine_list"),
    path("machines/new/", views.machine_create, name="machine_create"),
    path("machines/<int:pk>/edit/", views.machine_edit, name="machine_edit"),
    path("machines/<int:pk>/delete/", views.machine_delete, name="machine_delete"),
]
