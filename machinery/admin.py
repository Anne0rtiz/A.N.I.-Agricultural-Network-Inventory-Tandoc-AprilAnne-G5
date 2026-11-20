from django.contrib import admin

from .models import Machine, Reservation


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("name", "machine_type", "cooperative", "hourly_rate", "status")
    list_filter = ("machine_type", "status", "cooperative")
    search_fields = ("name",)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("machine", "farmer", "date", "start_time", "end_time", "status")
    list_filter = ("status", "date")
    search_fields = ("farmer__username", "machine__name")
