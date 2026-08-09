from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Address, User


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(label="الاسم الأول", max_length=60)
    last_name = forms.CharField(label="اسم العائلة", max_length=60, required=False)
    email = forms.EmailField(label="البريد الإلكتروني")
    phone = forms.CharField(label="رقم الجوال", max_length=20, required=False)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone")
        labels = {"username": "اسم المستخدم"}

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("هذا البريد مسجّل بالفعل. سجّل الدخول أو استخدم بريداً آخر.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data.get("phone", "")
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="البريد الإلكتروني أو اسم المستخدم")
    password = forms.CharField(label="كلمة المرور", widget=forms.PasswordInput)
    error_messages = {
        "invalid_login": "البيانات غير صحيحة. تحقق من البريد وكلمة المرور.",
        "inactive": "هذا الحساب موقوف. تواصل مع الدعم لتفعيله.",
    }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "newsletter")
        labels = {
            "first_name": "الاسم الأول",
            "last_name": "اسم العائلة",
            "email": "البريد الإلكتروني",
            "phone": "رقم الجوال",
            "newsletter": "أريد استلام عروض المتجر",
        }


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        exclude = ("user",)
