from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Avg, Count, Sum
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def ar_slug(value, fallback="item"):
    """يولّد slug صالحاً للنصوص العربية (allow_unicode)."""
    return slugify(value, allow_unicode=True) or fallback


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStamped):
    """تصنيف الأجهزة: كبيرة، صغيرة، تكييف، ترفيه..."""

    name = models.CharField(_("الاسم"), max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, allow_unicode=True, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    icon = models.CharField(_("رمز (bootstrap-icon)"), max_length=50, default="bi-plug")
    image = models.ImageField(_("صورة"), upload_to="categories/", blank=True)
    description = models.TextField(_("وصف"), blank=True)
    is_active = models.BooleanField(_("مفعّل"), default=True)
    sort_order = models.PositiveIntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("تصنيف")
        verbose_name_plural = _("التصنيفات")
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ar_slug(self.name, "category")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"{reverse('catalog:products')}?category={self.slug}"


class Brand(TimeStamped):
    name = models.CharField(_("الاسم"), max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, allow_unicode=True, blank=True)
    logo = models.ImageField(_("الشعار"), upload_to="brands/", blank=True)
    country = models.CharField(_("بلد المنشأ"), max_length=60, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("علامة تجارية")
        verbose_name_plural = _("العلامات التجارية")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ar_slug(self.name, "brand")
        super().save(*args, **kwargs)


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def with_stock(self):
        return self.annotate(stock_total=Sum("stock_records__quantity"))

    def with_rating(self):
        return self.annotate(
            rating_avg=Avg("reviews__rating", filter=models.Q(reviews__is_approved=True)),
            rating_count=Count("reviews", filter=models.Q(reviews__is_approved=True)),
        )


class Product(TimeStamped):
    """جهاز كهربائي معروض للبيع."""

    ENERGY_CHOICES = [(c, c) for c in ("A+++", "A++", "A+", "A", "B", "C", "D")]

    name = models.CharField(_("اسم المنتج"), max_length=200)
    slug = models.SlugField(max_length=220, unique=True, allow_unicode=True, blank=True)
    sku = models.CharField(_("رمز المنتج SKU"), max_length=40, unique=True)
    barcode = models.CharField(_("الباركود"), max_length=40, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products", verbose_name=_("التصنيف"))
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products", verbose_name=_("العلامة"))

    short_description = models.CharField(_("وصف مختصر"), max_length=300, blank=True)
    description = models.TextField(_("الوصف الكامل"), blank=True)

    price = models.DecimalField(_("سعر البيع"), max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(_("السعر قبل الخصم"), max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(_("سعر التكلفة"), max_digits=10, decimal_places=2, default=Decimal("0"))

    power_watt = models.PositiveIntegerField(_("القدرة (واط)"), null=True, blank=True)
    voltage = models.CharField(_("الجهد"), max_length=30, default="220V / 60Hz")
    energy_rating = models.CharField(_("كفاءة الطاقة"), max_length=5, choices=ENERGY_CHOICES, default="A")
    warranty_months = models.PositiveIntegerField(_("الضمان بالأشهر"), default=12)
    capacity = models.CharField(_("السعة"), max_length=60, blank=True, help_text="مثال: 18 قدم، 12000 وحدة")
    dimensions = models.CharField(_("الأبعاد"), max_length=80, blank=True)
    weight_kg = models.DecimalField(_("الوزن (كجم)"), max_digits=6, decimal_places=2, null=True, blank=True)
    specs = models.JSONField(_("مواصفات إضافية"), default=dict, blank=True)

    is_active = models.BooleanField(_("معروض في المتجر"), default=True)
    is_featured = models.BooleanField(_("مميّز في الرئيسية"), default=False)
    requires_installation = models.BooleanField(_("يحتاج تركيباً"), default=False)
    views_count = models.PositiveIntegerField(default=0, editable=False)

    wishlisted_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="wishlist", verbose_name=_("قائمة الرغبات")
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = _("منتج")
        verbose_name_plural = _("المنتجات")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["sku"]),
            models.Index(fields=["is_active", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.brand} {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = ar_slug(self.name, "product")
            slug, i = base, 2
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:product_detail", args=[self.slug])

    # ── المخزون ────────────────────────────────────────────────
    @property
    def stock(self):
        return self.stock_records.aggregate(t=Sum("quantity"))["t"] or 0

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def is_low_stock(self):
        return 0 < self.stock <= settings.LOW_STOCK_THRESHOLD

    # ── السعر ──────────────────────────────────────────────────
    @property
    def has_discount(self):
        return bool(self.compare_at_price and self.compare_at_price > self.price)

    @property
    def discount_percent(self):
        if not self.has_discount:
            return 0
        return int(round((self.compare_at_price - self.price) / self.compare_at_price * 100))

    @property
    def profit_margin(self):
        if not self.cost_price:
            return None
        return round((self.price - self.cost_price) / self.price * 100, 1)

    @property
    def main_image(self):
        img = self.images.first()
        return img.image.url if img else None

    @property
    def rating(self):
        return self.reviews.filter(is_approved=True).aggregate(a=Avg("rating"))["a"] or 0


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/")
    alt = models.CharField(max_length=150, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = _("صورة منتج")
        verbose_name_plural = _("صور المنتجات")

    def __str__(self):
        return self.alt or f"صورة {self.product_id}"


class Review(TimeStamped):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(_("التقييم"), choices=[(i, i) for i in range(1, 6)])
    title = models.CharField(_("عنوان"), max_length=120, blank=True)
    body = models.TextField(_("رأيك"))
    is_approved = models.BooleanField(_("منشور"), default=False)

    class Meta:
        unique_together = ("product", "user")
        ordering = ["-created_at"]
        verbose_name = _("تقييم")
        verbose_name_plural = _("التقييمات")

    def __str__(self):
        return f"{self.product} — {self.rating}/5"


class Banner(models.Model):
    """شرائح العرض في الصفحة الرئيسية."""

    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to="banners/")
    link = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = _("بانر")
        verbose_name_plural = _("البانرات")

    def __str__(self):
        return self.title
