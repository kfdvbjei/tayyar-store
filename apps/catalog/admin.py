from django.contrib import admin
from django.utils.html import format_html

from .models import Banner, Brand, Category, Product, ProductImage, Review


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name",)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "is_active")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "brand", "category", "price", "stock", "is_active", "is_featured")
    list_filter = ("category", "brand", "energy_rating", "is_active", "is_featured")
    search_fields = ("name", "sku", "barcode")
    list_editable = ("price", "is_active", "is_featured")
    inlines = [ProductImageInline]
    readonly_fields = ("views_count", "preview")
    autocomplete_fields = ("category", "brand")

    @admin.display(description="المخزون")
    def stock(self, obj):
        return obj.stock

    @admin.display(description="معاينة")
    def preview(self, obj):
        return format_html('<img src="{}" height="120">', obj.main_image) if obj.main_image else "—"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "is_approved", "created_at")
    list_filter = ("is_approved", "rating")
    actions = ["approve"]

    @admin.action(description="نشر التقييمات المحددة")
    def approve(self, request, queryset):
        queryset.update(is_approved=True)


admin.site.register(Banner)
