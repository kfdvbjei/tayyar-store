from django import forms
from django.forms import inlineformset_factory

from .models import PurchaseItem, PurchaseOrder, Supplier


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        exclude = ("created_at", "updated_at")


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ("supplier", "warehouse", "order_date", "expected_date", "invoice_number", "shipping_cost", "notes")
        widgets = {
            "order_date": forms.DateInput(attrs={"type": "date"}),
            "expected_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


PurchaseItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseItem,
    fields=("product", "quantity", "unit_cost"),
    extra=3,
    can_delete=True,
)
