from django import forms

from apps.accounts.models import Address

from .models import Order


class CheckoutForm(forms.ModelForm):
    save_address = forms.BooleanField(label="احفظ هذا العنوان لطلباتي القادمة", required=False, initial=True)

    class Meta:
        model = Order
        fields = (
            "full_name", "email", "phone", "city", "district",
            "street", "postal_code", "notes", "payment_method",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "مثال: الاتصال قبل الوصول بساعة"}),
            "payment_method": forms.RadioSelect,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_method"].empty_label = None
        if user and user.is_authenticated and not self.is_bound:
            default = Address.objects.filter(user=user, is_default=True).first()
            self.initial.setdefault("full_name", user.get_full_name() or user.username)
            self.initial.setdefault("email", user.email)
            self.initial.setdefault("phone", user.phone)
            if default:
                self.initial.update(
                    {
                        "city": default.city,
                        "district": default.district,
                        "street": default.street,
                        "postal_code": default.postal_code,
                    }
                )

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip().replace(" ", "")
        digits = phone.lstrip("+")
        if not digits.isdigit() or len(digits) < 9:
            raise forms.ValidationError("أدخل رقم جوال صحيحاً، مثل 05xxxxxxxx.")
        return phone


class CouponForm(forms.Form):
    code = forms.CharField(label="رمز الكوبون", max_length=30)


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ("status", "tracking_number", "warehouse")
        labels = {"status": "الحالة", "tracking_number": "رقم الشحنة", "warehouse": "المستودع"}
