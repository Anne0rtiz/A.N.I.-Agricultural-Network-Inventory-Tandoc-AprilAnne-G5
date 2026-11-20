from django.contrib import admin

from .models import Machine


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("name", "machine_type", "cooperative", "hourly_rate", "status")
    list_filter = ("machine_type", "status", "cooperative")
    search_fields = ("name",)
