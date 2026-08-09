from django.contrib import admin

from .models import Cart, CartItem, Coupon, Order, OrderItem, Payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name", "sku", "unit_price", "cost_price", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "full_name", "city", "status", "payment_method", "total", "is_paid", "created_at")
    list_filter = ("status", "payment_method", "is_paid", "created_at")
    search_fields = ("number", "full_name", "phone", "email")
    inlines = [OrderItemInline]
    date_hierarchy = "created_at"
    actions = ["mark_shipped"]

    @admin.action(description="تعليم الطلبات كـ«تم الشحن»")
    def mark_shipped(self, request, queryset):
        queryset.update(status=Order.Status.SHIPPED)


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "percent_off", "amount_off", "min_total", "valid_until", "used_count", "is_active")


admin.site.register([Cart, CartItem, Payment])
