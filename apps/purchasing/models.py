from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.db.models import F, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.catalog.models import Product, TimeStamped
from apps.inventory.models import StockMovement, Warehouse, apply_movement


class Supplier(TimeStamped):
    name = models.CharField(_("اسم المورّد"), max_length=150, unique=True)
    contact_person = models.CharField(_("مسؤول التواصل"), max_length=100, blank=True)
    phone = models.CharField(_("الهاتف"), max_length=20, blank=True)
    email = models.EmailField(_("البريد"), blank=True)
    tax_number = models.CharField(_("الرقم الضريبي"), max_length=30, blank=True)
    address = models.CharField(_("العنوان"), max_length=250, blank=True)
    payment_terms = models.CharField(_("شروط الدفع"), max_length=100, blank=True, default="صافي 30 يوم")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("مورّد")
        verbose_name_plural = _("الموردون")
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def total_purchased(self):
        return self.orders.filter(status=PurchaseOrder.Status.RECEIVED).aggregate(t=Sum("total"))["t"] or 0


class PurchaseOrder(TimeStamped):
    """أمر شراء من مورّد إلى مستودع."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("مسودة")
        ORDERED = "ordered", _("مُرسَل للمورّد")
        RECEIVED = "received", _("مستلَم")
        CANCELLED = "cancelled", _("ملغى")

    number = models.CharField(_("رقم الأمر"), max_length=20, unique=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="orders", verbose_name=_("المورّد"))
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="purchase_orders", verbose_name=_("المستودع"))
    status = models.CharField(_("الحالة"), max_length=12, choices=Status.choices, default=Status.DRAFT)
    order_date = models.DateField(_("تاريخ الأمر"), default=timezone.now)
    expected_date = models.DateField(_("تاريخ التوريد المتوقع"), null=True, blank=True)
    received_at = models.DateTimeField(_("تاريخ الاستلام"), null=True, blank=True)
    invoice_number = models.CharField(_("رقم فاتورة المورّد"), max_length=50, blank=True)
    shipping_cost = models.DecimalField(_("تكلفة الشحن"), max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(_("الضريبة"), max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(_("الإجمالي قبل الضريبة"), max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(_("الإجمالي"), max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(_("ملاحظات"), blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = _("أمر شراء")
        verbose_name_plural = _("أوامر الشراء")
        ordering = ["-order_date", "-id"]

    def __str__(self):
        return self.number or f"PO-{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            PurchaseOrder.objects.filter(pk=self.pk).update(number=f"PO-{self.pk:06d}")
            self.number = f"PO-{self.pk:06d}"

    def recalculate(self, save=True):
        self.subtotal = sum((i.line_total for i in self.items.all()), Decimal("0"))
        self.tax_amount = (self.subtotal * Decimal(str(settings.VAT_RATE))).quantize(Decimal("0.01"))
        self.total = self.subtotal + self.tax_amount + self.shipping_cost
        if save:
            PurchaseOrder.objects.filter(pk=self.pk).update(
                subtotal=self.subtotal, tax_amount=self.tax_amount, total=self.total
            )
        return self.total

    @property
    def can_receive(self):
        return self.status in {self.Status.DRAFT, self.Status.ORDERED} and self.items.exists()

    @transaction.atomic
    def receive(self, user=None):
        """يستلم البضاعة: يضيفها للمخزون ويحدّث تكلفة المنتج."""
        if not self.can_receive:
            raise ValueError("لا يمكن استلام هذا الأمر في حالته الحالية.")
        for item in self.items.select_related("product"):
            apply_movement(
                product=item.product,
                warehouse=self.warehouse,
                kind=StockMovement.Kind.IN,
                quantity=item.quantity,
                unit_cost=item.unit_cost,
                reference=self.number,
                note=f"استلام من {self.supplier}",
                user=user,
            )
            Product.objects.filter(pk=item.product_id).update(cost_price=item.unit_cost)
        self.status = self.Status.RECEIVED
        self.received_at = timezone.now()
        self.save(update_fields=["status", "received_at"])


class PurchaseItem(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="purchase_items")
    quantity = models.PositiveIntegerField(_("الكمية"), default=1)
    unit_cost = models.DecimalField(_("تكلفة الوحدة"), max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = _("بند شراء")
        verbose_name_plural = _("بنود الشراء")

    def __str__(self):
        return f"{self.product} × {self.quantity}"

    @property
    def line_total(self):
        return self.quantity * self.unit_cost
