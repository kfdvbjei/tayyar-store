from django import forms

from apps.catalog.models import Product

from .models import Stock, StockMovement, Warehouse


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        exclude = ("created_at", "updated_at")


class StockAdjustForm(forms.Form):
    """تسوية جرد أو إدخال/إخراج يدوي."""

    product = forms.ModelChoiceField(queryset=Product.objects.active(), label="المنتج")
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True), label="المستودع")
    kind = forms.ChoiceField(choices=StockMovement.Kind.choices, label="نوع الحركة")
    quantity = forms.IntegerField(label="الكمية", min_value=1)
    note = forms.CharField(label="ملاحظة", required=False, max_length=250)

    def clean(self):
        data = super().clean()
        kind, qty = data.get("kind"), data.get("quantity")
        product, warehouse = data.get("product"), data.get("warehouse")
        outbound = kind in {StockMovement.Kind.OUT, StockMovement.Kind.DAMAGE, StockMovement.Kind.TRANSFER_OUT}
        if outbound and product and warehouse:
            current = Stock.objects.filter(product=product, warehouse=warehouse).first()
            available = current.available if current else 0
            if qty and qty > available:
                self.add_error("quantity", f"الرصيد المتاح {available} فقط في هذا المستودع.")
        return data


class ReorderLevelForm(forms.ModelForm):
    class Meta:
        model = Stock
        fields = ("reorder_level", "shelf")
        labels = {"reorder_level": "حد إعادة الطلب", "shelf": "موقع الرف"}


class TransferForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.active(), label="المنتج")
    source = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True), label="من مستودع")
    destination = forms.ModelChoiceField(queryset=Warehouse.objects.filter(is_active=True), label="إلى مستودع")
    quantity = forms.IntegerField(label="الكمية", min_value=1)

    def clean(self):
        data = super().clean()
        if data.get("source") and data.get("source") == data.get("destination"):
            self.add_error("destination", "اختر مستودعاً مختلفاً عن المصدر.")
        src, product, qty = data.get("source"), data.get("product"), data.get("quantity")
        if src and product and qty:
            stock = Stock.objects.filter(product=product, warehouse=src).first()
            if not stock or stock.available < qty:
                self.add_error("quantity", "الرصيد في المستودع المصدر لا يكفي.")
        return data
