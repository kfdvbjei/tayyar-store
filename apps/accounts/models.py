from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """مستخدم مخصص: الدخول بالبريد أو اسم المستخدم."""

    email = models.EmailField(_("البريد الإلكتروني"), unique=True)
    phone = models.CharField(_("رقم الجوال"), max_length=20, blank=True)
    is_verified = models.BooleanField(_("موثّق"), default=False)
    newsletter = models.BooleanField(_("النشرة البريدية"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = _("مستخدم")
        verbose_name_plural = _("المستخدمون")

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.first_name or self.username


class Address(models.Model):
    """عنوان شحن محفوظ."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(_("التسمية"), max_length=40, default="المنزل")
    full_name = models.CharField(_("الاسم الكامل"), max_length=120)
    phone = models.CharField(_("الجوال"), max_length=20)
    city = models.CharField(_("المدينة"), max_length=60)
    district = models.CharField(_("الحي"), max_length=80, blank=True)
    street = models.CharField(_("الشارع والمبنى"), max_length=200)
    postal_code = models.CharField(_("الرمز البريدي"), max_length=12, blank=True)
    notes = models.CharField(_("ملاحظات للمندوب"), max_length=200, blank=True)
    is_default = models.BooleanField(_("العنوان الافتراضي"), default=False)

    class Meta:
        verbose_name = _("عنوان")
        verbose_name_plural = _("العناوين")
        ordering = ["-is_default", "id"]

    def __str__(self):
        return f"{self.label} — {self.city}"

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @property
    def one_line(self):
        parts = [self.street, self.district, self.city, self.postal_code]
        return "، ".join(p for p in parts if p)
