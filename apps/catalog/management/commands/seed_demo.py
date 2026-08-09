"""يعبّئ المتجر ببيانات تجريبية واقعية للاختبار السريع.

    python manage.py seed_demo
"""
import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalog.models import Brand, Category, Product
from apps.inventory.models import StockMovement, Warehouse, apply_movement
from apps.orders.models import Coupon
from apps.purchasing.models import Supplier

CATEGORIES = [
    ("أجهزة كبيرة", "bi-house-gear"),
    ("ثلاجات وفريزرات", "bi-snow"),
    ("غسالات ومجففات", "bi-water"),
    ("تكييف وتبريد", "bi-wind"),
    ("أفران وأجهزة طبخ", "bi-fire"),
    ("أجهزة مطبخ صغيرة", "bi-cup-hot"),
    ("العناية بالمنزل", "bi-stars"),
    ("ترفيه منزلي", "bi-tv"),
]

BRANDS = [
    ("سامسونج", "كوريا الجنوبية"), ("إل جي", "كوريا الجنوبية"), ("بوش", "ألمانيا"),
    ("توشيبا", "اليابان"), ("هيتاشي", "اليابان"), ("دايكن", "اليابان"),
    ("كلاس", "السعودية"), ("ميديا", "الصين"),
]

ITEMS = [
    ("ثلاجة بابين نو فروست 18 قدم", "ثلاجات وفريزرات", 2799, 3499, 1980, "A++", 320, "18 قدم"),
    ("ثلاجة أربعة أبواب إنفرتر 23 قدم", "ثلاجات وفريزرات", 5490, 6390, 4100, "A+++", 380, "23 قدم"),
    ("فريزر رأسي 7 أدراج", "ثلاجات وفريزرات", 2190, None, 1600, "A+", 260, "220 لتر"),
    ("غسالة أوتوماتيك تحميل أمامي 8 كجم", "غسالات ومجففات", 1749, 2149, 1250, "A++", 2000, "8 كجم"),
    ("غسالة ومجفف 10/6 كجم إنفرتر", "غسالات ومجففات", 3290, 3890, 2450, "A+++", 2100, "10 كجم"),
    ("مجفف ملابس حراري 8 كجم", "غسالات ومجففات", 2450, None, 1800, "A+", 2600, "8 كجم"),
    ("مكيّف سبليت 18000 وحدة إنفرتر", "تكييف وتبريد", 2390, 2790, 1750, "A+++", 1600, "18000 وحدة"),
    ("مكيّف شباك 24000 وحدة", "تكييف وتبريد", 1690, None, 1180, "B", 2400, "24000 وحدة"),
    ("فرن كهربائي مدمج 60 سم", "أفران وأجهزة طبخ", 1890, 2290, 1350, "A", 2800, "70 لتر"),
    ("سطح طبخ كهربائي سيراميك 4 عيون", "أفران وأجهزة طبخ", 1290, None, 900, "A", 6000, "60 سم"),
    ("ميكروويف 30 لتر مع شواية", "أجهزة مطبخ صغيرة", 549, 699, 380, "A", 900, "30 لتر"),
    ("خلاط كهربائي 1200 واط", "أجهزة مطبخ صغيرة", 279, 349, 180, "A", 1200, "1.5 لتر"),
    ("مكنسة كهربائية لاسلكية", "العناية بالمنزل", 899, 1099, 620, "A++", 450, "0.6 لتر"),
    ("منقّي هواء لغرفة 40 م²", "العناية بالمنزل", 1150, None, 800, "A+", 55, "40 م²"),
    ("شاشة ذكية 55 بوصة 4K", "ترفيه منزلي", 1990, 2490, 1500, "A+", 120, "55 بوصة"),
    ("مسرح منزلي 5.1", "ترفيه منزلي", 1390, None, 980, "B", 300, "500 واط"),
]


class Command(BaseCommand):
    help = "يضيف تصنيفات وعلامات ومنتجات ومستودعات وأرصدة تجريبية"

    def handle(self, *args, **options):
        User = get_user_model()

        cats = {}
        for name, icon in CATEGORIES:
            cats[name], _ = Category.objects.get_or_create(name=name, defaults={"icon": icon})
        brands = [Brand.objects.get_or_create(name=n, defaults={"country": c})[0] for n, c in BRANDS]

        main, _ = Warehouse.objects.get_or_create(
            code="RUH-01", defaults={"name": "مستودع الرياض الرئيسي", "city": "الرياض", "is_default": True}
        )
        branch, _ = Warehouse.objects.get_or_create(
            code="JED-01", defaults={"name": "مستودع جدة", "city": "جدة"}
        )

        Supplier.objects.get_or_create(
            name="الشركة الوطنية للأجهزة", defaults={"phone": "0112345678", "payment_terms": "صافي 30 يوم"}
        )
        Supplier.objects.get_or_create(
            name="مؤسسة الخليج للتوريدات", defaults={"phone": "0126543210", "payment_terms": "دفع مقدم"}
        )

        Coupon.objects.get_or_create(
            code="WELCOME10", defaults={"percent_off": 10, "min_total": Decimal("500"), "usage_limit": 200}
        )

        created = 0
        for i, (name, cat, price, compare, cost, energy, watt, capacity) in enumerate(ITEMS, start=1):
            brand = brands[i % len(brands)]
            product, made = Product.objects.get_or_create(
                sku=f"TY-{1000 + i}",
                defaults={
                    "name": name,
                    "category": cats[cat],
                    "brand": brand,
                    "price": Decimal(str(price)),
                    "compare_at_price": Decimal(str(compare)) if compare else None,
                    "cost_price": Decimal(str(cost)),
                    "energy_rating": energy,
                    "power_watt": watt,
                    "capacity": capacity,
                    "warranty_months": random.choice([12, 24, 24, 36]),
                    "is_featured": i % 3 == 0,
                    "short_description": f"{name} من {brand.name}، بكفاءة طاقة {energy} وضمان الوكيل.",
                    "description": (
                        f"{name} من {brand.name}. صُمّم للاستخدام اليومي مع استهلاك كهرباء منخفض "
                        f"({energy}) وقدرة {watt} واط. يشمل السعر الضمان المعتمد لدى الوكيل، "
                        "والتركيب متاح داخل المدن الرئيسية."
                    ),
                    "requires_installation": cat in {"تكييف وتبريد", "غسالات ومجففات"},
                },
            )
            if made:
                created += 1
                for warehouse, qty in ((main, random.randint(4, 40)), (branch, random.randint(0, 15))):
                    if qty:
                        apply_movement(
                            product=product, warehouse=warehouse, kind=StockMovement.Kind.IN,
                            quantity=qty, unit_cost=product.cost_price,
                            reference="SEED", note="رصيد افتتاحي",
                        )

        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@tayyar.sa", "Admin12345!")
            self.stdout.write(self.style.WARNING("أُنشئ مستخدم admin بكلمة مرور Admin12345! — غيّرها فوراً."))

        self.stdout.write(self.style.SUCCESS(f"تمت التعبئة: {created} منتج جديد، ومستودعان، وكوبون WELCOME10."))
