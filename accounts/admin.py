from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Cooperative, User


@admin.register(Cooperative)
class CooperativeAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "join_code", "created_at")
    search_fields = ("name", "location")
    readonly_fields = ("join_code", "created_at")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "role", "cooperative", "farmer_code", "is_active")
    list_filter = ("role", "cooperative", "is_active")
    readonly_fields = ("farmer_code",)
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("A.N.I. details", {"fields": ("role", "contact_number", "profile_photo", "cooperative", "farmer_code")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("A.N.I. details", {"fields": ("email", "role", "contact_number", "cooperative")}),
    )
