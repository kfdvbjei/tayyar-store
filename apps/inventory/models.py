from django.conf import settings
from django.db import models, transaction
from django.db.models import F, Sum
from django.utils.translation import gettext_lazy as _

from apps.catalog.models import Product, TimeStamped


class Warehouse(TimeStamped):
    """مستودع أو فرع يحتفظ ببضاعة."""

    name = models.CharField(_("اسم المستودع"), max_length=100, unique=True)
    code = models.CharField(_("الرمز"), max_length=20, unique=True)
    city = models.CharField(_("المدينة"), max_length=60, blank=True)
    address = models.CharField(_("العنوان"), max_length=250, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="managed_warehouses"
    )
    is_default = models.BooleanField(_("المستودع الافتراضي"), default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("مستودع")
        verbose_name_plural = _("المستودعات")
        ordering = ["-is_default", "name"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if self.is_default:
            Warehouse.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @property
    def total_units(self):
        return self.stock_records.aggregate(t=Sum("quantity"))["t"] or 0

    @property
    def stock_value(self):
        return sum(r.quantity * r.product.cost_price for r in self.stock_records.select_related("product"))


class Stock(models.Model):
    """رصيد منتج داخل مستودع محدد."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_records")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="stock_records")
    quantity = models.IntegerField(_("الكمية"), default=0)
    reserved = models.IntegerField(_("محجوز لطلبات"), default=0)
    reorder_level = models.PositiveIntegerField(_("حد إعادة الطلب"), default=5)
    shelf = models.CharField(_("موقع الرف"), max_length=40, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("product", "warehouse")
        verbose_name = _("رصيد مخزون")
        verbose_name_plural = _("أرصدة المخزون")
        ordering = ["product__name"]

    def __str__(self):
        return f"{self.product} @ {self.warehouse}: {self.quantity}"

    @property
    def available(self):
        return self.quantity - self.reserved

    @property
    def needs_reorder(self):
        return self.available <= self.reorder_level


class StockMovement(models.Model):
    """سجل كل حركة دخول أو خروج — مصدر الحقيقة للجرد."""

    class Kind(models.TextChoices):
        IN = "in", _("إدخال (شراء)")
        OUT = "out", _("إخراج (بيع)")
        RETURN = "return", _("مرتجع")
        ADJUST = "adjust", _("تسوية جرد")
        TRANSFER_OUT = "t_out", _("تحويل صادر")
        TRANSFER_IN = "t_in", _("تحويل وارد")
        DAMAGE = "damage", _("تالف")

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(_("نوع الحركة"), max_length=10, choices=Kind.choices)
    quantity = models.IntegerField(_("الكمية"), help_text="موجبة دائماً؛ الاتجاه يحدده نوع الحركة")
    unit_cost = models.DecimalField(_("تكلفة الوحدة"), max_digits=10, decimal_places=2, default=0)
    reference = models.CharField(_("المرجع"), max_length=60, blank=True)
    note = models.CharField(_("ملاحظة"), max_length=250, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    INBOUND = {Kind.IN, Kind.RETURN, Kind.TRANSFER_IN}

    class Meta:
        verbose_name = _("حركة مخزون")
        verbose_name_plural = _("حركات المخزون")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} × {self.quantity} — {self.product}"

    @property
    def signed_quantity(self):
        if self.kind in self.INBOUND:
            return self.quantity
        if self.kind == self.Kind.ADJUST:
            return self.quantity  # التسوية تُحفظ بإشارتها من الواجهة
        return -self.quantity


@transaction.atomic
def apply_movement(*, product, warehouse, kind, quantity, unit_cost=0, reference="", note="", user=None):
    """يسجّل الحركة ويحدّث الرصيد في عملية واحدة آمنة."""
    movement = StockMovement.objects.create(
        product=product,
        warehouse=warehouse,
        kind=kind,
        quantity=quantity,
        unit_cost=unit_cost,
        reference=reference,
        note=note,
        created_by=user,
    )
    stock, _created = Stock.objects.select_for_update().get_or_create(product=product, warehouse=warehouse)
    Stock.objects.filter(pk=stock.pk).update(quantity=F("quantity") + movement.signed_quantity)
    return movement
