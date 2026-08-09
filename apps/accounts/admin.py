from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Address, User


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "phone", "is_staff", "created_at")
    search_fields = ("username", "email", "phone", "first_name", "last_name")
    inlines = [AddressInline]
    fieldsets = BaseUserAdmin.fieldsets + (("بيانات إضافية", {"fields": ("phone", "is_verified", "newsletter")}),)
