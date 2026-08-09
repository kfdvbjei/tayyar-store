from django.contrib import admin

from .models import PurchaseItem, PurchaseOrder, Supplier


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone", "payment_terms", "is_active")
    search_fields = ("name", "phone", "email")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "supplier", "warehouse", "status", "order_date", "total")
    list_filter = ("status", "warehouse", "supplier")
    search_fields = ("number", "invoice_number")
    inlines = [PurchaseItemInline]
    actions = ["receive_orders"]

    @admin.action(description="استلام أوامر الشراء المحددة")
    def receive_orders(self, request, queryset):
        done = 0
        for order in queryset:
            if order.can_receive:
                order.receive(user=request.user)
                done += 1
        self.message_user(request, f"استُلم {done} أمر شراء وأُضيف للمخزون.")
