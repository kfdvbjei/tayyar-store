from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.catalog.models import Product, TimeStamped
from apps.inventory.models import StockMovement, Warehouse, apply_movement

ZERO = Decimal("0.00")


class Coupon(models.Model):
    code = models.CharField(_("الرمز"), max_length=30, unique=True)
    percent_off = models.PositiveSmallIntegerField(_("نسبة الخصم %"), default=0)
    amount_off = models.DecimalField(_("خصم ثابت"), max_digits=10, decimal_places=2, default=0)
    min_total = models.DecimalField(_("أقل مبلغ للطلب"), max_digits=10, decimal_places=2, default=0)
    valid_until = models.DateField(_("صالح حتى"), null=True, blank=True)
    usage_limit = models.PositiveIntegerField(_("حد الاستخدام"), default=0, help_text="0 = بلا حد")
    used_count = models.PositiveIntegerField(default=0, editable=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("كوبون")
        verbose_name_plural = _("الكوبونات")

    def __str__(self):
        return self.code

    def is_valid_for(self, subtotal):
        if not self.is_active:
            return False, "هذا الكوبون غير مفعّل."
        if self.valid_until and self.valid_until < timezone.localdate():
            return False, "انتهت صلاحية الكوبون."
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, "بلغ الكوبون حد الاستخدام."
        if subtotal < self.min_total:
            return False, f"الكوبون يبدأ من {self.min_total:,.0f} ر.س."
        return True, ""

    def discount_for(self, subtotal):
        value = subtotal * Decimal(self.percent_off) / 100 if self.percent_off else self.amount_off
        return min(value, subtotal).quantize(Decimal("0.01"))


class Cart(TimeStamped):
    """سلة مرتبطة بمستخدم أو بجلسة زائر."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="cart"
    )
    session_key = models.CharField(max_length=60, blank=True, db_index=True)
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = _("سلة")
        verbose_name_plural = _("السلال")

    def __str__(self):
        return f"سلة {self.user or self.session_key}"

    @property
    def item_count(self):
        return sum(i.quantity for i in self.items.all())

    @property
    def subtotal(self):
        return sum((i.line_total for i in self.items.select_related("product")), ZERO)

    @property
    def discount(self):
        return self.coupon.discount_for(self.subtotal) if self.coupon else ZERO

    @property
    def shipping(self):
        base = self.subtotal - self.discount
        if base == 0 or base >= Decimal(str(settings.FREE_SHIPPING_THRESHOLD)):
            return ZERO
        return Decimal(str(settings.SHIPPING_FLAT_RATE))

    @property
    def tax(self):
        return ((self.subtotal - self.discount) * Decimal(str(settings.VAT_RATE))).quantize(Decimal("0.01"))

    @property
    def total(self):
        return self.subtotal - self.discount + self.tax + self.shipping

    @property
    def amount_to_free_shipping(self):
        gap = Decimal(str(settings.FREE_SHIPPING_THRESHOLD)) - (self.subtotal - self.discount)
        return max(gap, ZERO)

    def merge_from(self, other):
        """يدمج سلة الزائر في سلة المستخدم بعد تسجيل الدخول."""
        for item in other.items.all():
            existing = self.items.filter(product=item.product).first()
            if existing:
                existing.quantity += item.quantity
                existing.save(update_fields=["quantity"])
            else:
                item.cart = self
                item.save(update_fields=["cart"])
        other.delete()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("cart", "product")
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.product} × {self.quantity}"

    @property
    def line_total(self):
        return self.product.price * self.quantity


class Order(TimeStamped):
    class Status(models.TextChoices):
        PENDING = "pending", _("بانتظار الدفع")
        PAID = "paid", _("مدفوع")
        PROCESSING = "processing", _("قيد التجهيز")
        SHIPPED = "shipped", _("تم الشحن")
        DELIVERED = "delivered", _("تم التسليم")
        CANCELLED = "cancelled", _("ملغى")
        REFUNDED = "refunded", _("مسترجع")

    class PaymentMethod(models.TextChoices):
        CARD = "card", _("بطاقة مدى / ائتمانية")
        COD = "cod", _("الدفع عند الاستلام")
        TRANSFER = "transfer", _("تحويل بنكي")

    number = models.CharField(_("رقم الطلب"), max_length=20, unique=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
    status = models.CharField(_("الحالة"), max_length=12, choices=Status.choices, default=Status.PENDING)
    payment_method = models.CharField(_("طريقة الدفع"), max_length=10, choices=PaymentMethod.choices)
    is_paid = models.BooleanField(_("مدفوع"), default=False)
    paid_at = models.DateTimeField(null=True, blank=True)

    full_name = models.CharField(_("الاسم"), max_length=120)
    email = models.EmailField(_("البريد"))
    phone = models.CharField(_("الجوال"), max_length=20)
    city = models.CharField(_("المدينة"), max_length=60)
    district = models.CharField(_("الحي"), max_length=80, blank=True)
    street = models.CharField(_("العنوان"), max_length=200)
    postal_code = models.CharField(_("الرمز البريدي"), max_length=12, blank=True)
    notes = models.CharField(_("ملاحظات"), max_length=250, blank=True)

    warehouse = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    coupon_code = models.CharField(max_length=30, blank=True)
    subtotal = models.DecimalField(_("المجموع"), max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(_("الخصم"), max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(_("ضريبة القيمة المضافة"), max_digits=12, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(_("الشحن"), max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(_("الإجمالي"), max_digits=12, decimal_places=2, default=0)

    tracking_number = models.CharField(_("رقم الشحنة"), max_length=60, blank=True)
    stock_released = models.BooleanField(default=False, editable=False)

    class Meta:
        verbose_name = _("طلب")
        verbose_name_plural = _("الطلبات")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["number"]), models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return self.number or f"ORD-{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            number = f"{timezone.now():%y%m}-{self.pk:05d}"
            Order.objects.filter(pk=self.pk).update(number=number)
            self.number = number

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("accounts:order_detail", args=[self.number])

    @property
    def address_line(self):
        return "، ".join(p for p in [self.street, self.district, self.city, self.postal_code] if p)

    @property
    def profit(self):
        return sum((i.line_profit for i in self.items.all()), ZERO)

    @transaction.atomic
    def release_stock(self, user=None):
        """يخصم كميات الطلب من المخزون مرة واحدة فقط."""
        if self.stock_released:
            return
        warehouse = self.warehouse or Warehouse.objects.filter(is_default=True).first() or Warehouse.objects.first()
        if not warehouse:
            return
        for item in self.items.select_related("product"):
            apply_movement(
                product=item.product,
                warehouse=warehouse,
                kind=StockMovement.Kind.OUT,
                quantity=item.quantity,
                unit_cost=item.cost_price,
                reference=self.number,
                note="بيع",
                user=user,
            )
        self.warehouse = warehouse
        self.stock_released = True
        self.save(update_fields=["warehouse", "stock_released"])

    @transaction.atomic
    def restock(self, user=None):
        """يعيد الكميات للمخزون عند الإلغاء أو الاسترجاع."""
        if not self.stock_released:
            return
        warehouse = self.warehouse or Warehouse.objects.filter(is_default=True).first()
        for item in self.items.select_related("product"):
            apply_movement(
                product=item.product,
                warehouse=warehouse,
                kind=StockMovement.Kind.RETURN,
                quantity=item.quantity,
                unit_cost=item.cost_price,
                reference=self.number,
                note="إلغاء/استرجاع طلب",
                user=user,
            )
        self.stock_released = False
        self.save(update_fields=["stock_released"])

    def mark_paid(self, user=None):
        self.is_paid = True
        self.paid_at = timezone.now()
        self.status = self.Status.PAID
        self.save(update_fields=["is_paid", "paid_at", "status"])
        self.release_stock(user=user)


class OrderItem(models.Model):
    """يحفظ نسخة من بيانات المنتج وقت الشراء."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL, related_name="order_items")
    product_name = models.CharField(max_length=250)
    sku = models.CharField(max_length=40, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = _("بند طلب")
        verbose_name_plural = _("بنود الطلبات")

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def line_profit(self):
        return (self.unit_price - self.cost_price) * self.quantity


class Payment(models.Model):
    class Status(models.TextChoices):
        INITIATED = "initiated", _("قيد التنفيذ")
        SUCCEEDED = "succeeded", _("ناجحة")
        FAILED = "failed", _("فاشلة")
        REFUNDED = "refunded", _("مستردة")

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    provider = models.CharField(max_length=30, default="stripe")
    reference = models.CharField(max_length=120, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.INITIATED)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("عملية دفع")
        verbose_name_plural = _("عمليات الدفع")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider} — {self.get_status_display()}"
