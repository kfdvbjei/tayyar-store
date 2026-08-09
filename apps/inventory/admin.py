from django.contrib import admin

from .models import Stock, StockMovement, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "city", "is_default", "is_active", "total_units")
    search_fields = ("name", "code", "city")


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("product", "warehouse", "quantity", "reserved", "reorder_level", "shelf")
    list_filter = ("warehouse",)
    search_fields = ("product__name", "product__sku")
    list_editable = ("reorder_level", "shelf")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "product", "warehouse", "kind", "quantity", "reference", "created_by")
    list_filter = ("kind", "warehouse")
    search_fields = ("product__name", "reference")
    date_hierarchy = "created_at"
