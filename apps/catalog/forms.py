from django import forms

from .models import Product, Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ("rating", "title", "body")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 4, "placeholder": "كيف كانت تجربتك مع الجهاز؟"}),
            "rating": forms.RadioSelect,
        }


class ProductForm(forms.ModelForm):
    """نموذج إضافة/تعديل منتج من لوحة التحكم."""

    class Meta:
        model = Product
        exclude = ("slug", "views_count", "wishlisted_by", "created_at", "updated_at")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "short_description": forms.Textarea(attrs={"rows": 2}),
            "specs": forms.Textarea(attrs={"rows": 3, "placeholder": '{"عدد الأبواب": "2", "نوع الضاغط": "إنفرتر"}'}),
        }

    def clean(self):
        data = super().clean()
        price, compare = data.get("price"), data.get("compare_at_price")
        if price and compare and compare <= price:
            self.add_error("compare_at_price", "السعر قبل الخصم يجب أن يكون أعلى من سعر البيع.")
        return data
