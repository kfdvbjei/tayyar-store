"""لوحة تحكم الإدارة: مبيعات، مشتريات، مخزون، وتقارير."""
import csv
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce, TruncDay, TruncMonth
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.forms import ProductForm
from apps.catalog.models import Category, Product
from apps.inventory.forms import ReorderLevelForm, StockAdjustForm, TransferForm, WarehouseForm
from apps.inventory.models import Stock, StockMovement, Warehouse, apply_movement
from apps.orders.forms import OrderStatusForm
from apps.orders.models import Order, OrderItem
from apps.purchasing.forms import PurchaseItemFormSet, PurchaseOrderForm, SupplierForm
from apps.purchasing.models import PurchaseOrder, Supplier

DEC = DecimalField(max_digits=14, decimal_places=2)
PAID_STATUSES = [Order.Status.PAID, Order.Status.PROCESSING, Order.Status.SHIPPED, Order.Status.DELIVERED]


def _date_range(request, default_days=30):
    end = timezone.localdate()
    start = end - timedelta(days=int(request.GET.get("days", default_days)))
    return start, end


# ── نظرة عامة ──────────────────────────────────────────────────
@staff_member_required
def overview(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    sold = Order.objects.filter(status__in=PAID_STATUSES)

    month_sales = sold.filter(created_at__date__gte=month_start).aggregate(
        total=Coalesce(Sum("total"), Decimal("0"), output_field=DEC),
        count=Count("id"),
    )
    prev_start = (month_start - timedelta(days=1)).replace(day=1)
    prev_sales = sold.filter(created_at__date__gte=prev_start, created_at__date__lt=month_start).aggregate(
        total=Coalesce(Sum("total"), Decimal("0"), output_field=DEC)
    )["total"]
    growth = None
    if prev_sales:
        growth = round((month_sales["total"] - prev_sales) / prev_sales * 100, 1)

    purchases_month = PurchaseOrder.objects.filter(
        status=PurchaseOrder.Status.RECEIVED, order_date__gte=month_start
    ).aggregate(total=Coalesce(Sum("total"), Decimal("0"), output_field=DEC))["total"]

    low_stock = (
        Stock.objects.select_related("product", "warehouse")
        .filter(quantity__lte=F("reorder_level"))
        .order_by("quantity")[:8]
    )
    stock_value = sum(
        (s.quantity * s.product.cost_price for s in Stock.objects.select_related("product")), Decimal("0")
    )

    best_sellers = (
        OrderItem.objects.filter(order__status__in=PAID_STATUSES)
        .values("product_name")
        .annotate(units=Sum("quantity"), revenue=Sum(F("unit_price") * F("quantity"), output_field=DEC))
        .order_by("-units")[:5]
    )

    context = {
        "today_sales": sold.filter(created_at__date=today).aggregate(
            t=Coalesce(Sum("total"), Decimal("0"), output_field=DEC)
        )["t"],
        "month_sales": month_sales["total"],
        "month_orders": month_sales["count"],
        "growth": growth,
        "purchases_month": purchases_month,
        "pending_orders": Order.objects.filter(status=Order.Status.PENDING).count(),
        "processing_orders": Order.objects.filter(status=Order.Status.PROCESSING).count(),
        "products_count": Product.objects.filter(is_active=True).count(),
        "customers_count": User.objects.filter(is_staff=False).count(),
        "stock_value": stock_value,
        "low_stock": low_stock,
        "best_sellers": best_sellers,
        "recent_orders": Order.objects.select_related("user")[:8],
        "warehouses": Warehouse.objects.filter(is_active=True),
    }
    return render(request, "dashboard/overview.html", context)


@staff_member_required
def sales_series(request):
    """بيانات الرسم البياني: المبيعات مقابل المشتريات آخر N يوم."""
    start, end = _date_range(request)
    sales = dict(
        Order.objects.filter(status__in=PAID_STATUSES, created_at__date__gte=start)
        .annotate(d=TruncDay("created_at"))
        .values("d")
        .annotate(t=Sum("total"))
        .values_list("d", "t")
    )
    purchases = dict(
        PurchaseOrder.objects.filter(status=PurchaseOrder.Status.RECEIVED, order_date__gte=start)
        .annotate(d=TruncDay("order_date"))
        .values("d")
        .annotate(t=Sum("total"))
        .values_list("d", "t")
    )
    labels, sales_data, purchase_data = [], [], []
    day = start
    while day <= end:
        labels.append(day.strftime("%m-%d"))
        sales_data.append(float(next((v for k, v in sales.items() if k.date() == day), 0)))
        purchase_data.append(float(next((v for k, v in purchases.items() if getattr(k, "date", lambda: k)() == day), 0)))
        day += timedelta(days=1)
    return JsonResponse({"labels": labels, "sales": sales_data, "purchases": purchase_data})


# ── الطلبات ────────────────────────────────────────────────────
@staff_member_required
def order_list(request):
    orders = Order.objects.select_related("user").prefetch_related("items")
    if status := request.GET.get("status"):
        orders = orders.filter(status=status)
    if q := request.GET.get("q", "").strip():
        orders = orders.filter(Q(number__icontains=q) | Q(full_name__icontains=q) | Q(phone__icontains=q))
    totals = orders.aggregate(t=Coalesce(Sum("total"), Decimal("0"), output_field=DEC), n=Count("id"))
    return render(
        request,
        "dashboard/orders.html",
        {"orders": orders[:200], "statuses": Order.Status.choices, "totals": totals, "q": request.GET.get("q", "")},
    )


@staff_member_required
def order_detail(request, number):
    order = get_object_or_404(Order.objects.prefetch_related("items"), number=number)
    form = OrderStatusForm(request.POST or None, instance=order)
    if request.method == "POST" and form.is_valid():
        previous = order.status
        updated = form.save()
        if updated.status in PAID_STATUSES and not updated.stock_released:
            updated.release_stock(user=request.user)
        if updated.status in {Order.Status.CANCELLED, Order.Status.REFUNDED} and previous not in {
            Order.Status.CANCELLED,
            Order.Status.REFUNDED,
        }:
            updated.restock(user=request.user)
        messages.success(request, "حُدّثت حالة الطلب.")
        return redirect("dashboard:order_detail", number=number)
    return render(request, "dashboard/order_detail.html", {"order": order, "form": form})


# ── المنتجات ───────────────────────────────────────────────────
@staff_member_required
def product_list(request):
    products = Product.objects.select_related("brand", "category").with_stock()
    if q := request.GET.get("q", "").strip():
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    if cat := request.GET.get("category"):
        products = products.filter(category__slug=cat)
    return render(
        request,
        "dashboard/products.html",
        {"products": products[:200], "categories": Category.objects.all(), "q": request.GET.get("q", "")},
    )


@staff_member_required
def product_create(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, f"أُضيف المنتج «{product.name}». أضف رصيده من صفحة المخزون.")
        return redirect("dashboard:products")
    return render(request, "dashboard/product_form.html", {"form": form, "title": "منتج جديد"})


@staff_member_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "حُفظت تعديلات المنتج.")
        return redirect("dashboard:products")
    return render(request, "dashboard/product_form.html", {"form": form, "title": f"تعديل: {product.name}", "product": product})


@staff_member_required
def product_toggle(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.save(update_fields=["is_active"])
    messages.info(request, "أُعيد عرض المنتج." if product.is_active else "أُخفي المنتج من المتجر.")
    return redirect("dashboard:products")


# ── المخزون ────────────────────────────────────────────────────
@staff_member_required
def inventory_list(request):
    records = Stock.objects.select_related("product", "product__brand", "warehouse")
    if wh := request.GET.get("warehouse"):
        records = records.filter(warehouse__code=wh)
    if request.GET.get("low") == "1":
        records = records.filter(quantity__lte=F("reorder_level"))
    if q := request.GET.get("q", "").strip():
        records = records.filter(Q(product__name__icontains=q) | Q(product__sku__icontains=q))
    return render(
        request,
        "dashboard/inventory.html",
        {
            "records": records[:300],
            "warehouses": Warehouse.objects.filter(is_active=True),
            "adjust_form": StockAdjustForm(),
            "q": request.GET.get("q", ""),
        },
    )


@staff_member_required
def stock_move(request):
    form = StockAdjustForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        apply_movement(
            product=data["product"],
            warehouse=data["warehouse"],
            kind=data["kind"],
            quantity=data["quantity"],
            note=data["note"],
            user=request.user,
        )
        messages.success(request, "سُجّلت الحركة وحُدّث الرصيد.")
        return redirect("dashboard:inventory")
    return render(request, "dashboard/stock_form.html", {"form": form, "title": "حركة مخزون"})


@staff_member_required
def stock_transfer(request):
    form = TransferForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        reference = f"TRF-{timezone.now():%Y%m%d%H%M}"
        apply_movement(
            product=data["product"], warehouse=data["source"], kind=StockMovement.Kind.TRANSFER_OUT,
            quantity=data["quantity"], reference=reference, user=request.user,
            note=f"تحويل إلى {data['destination']}",
        )
        apply_movement(
            product=data["product"], warehouse=data["destination"], kind=StockMovement.Kind.TRANSFER_IN,
            quantity=data["quantity"], reference=reference, user=request.user,
            note=f"تحويل من {data['source']}",
        )
        messages.success(request, "تم التحويل بين المستودعين.")
        return redirect("dashboard:inventory")
    return render(request, "dashboard/stock_form.html", {"form": form, "title": "تحويل بين المستودعات"})


@staff_member_required
def movement_log(request):
    movements = StockMovement.objects.select_related("product", "warehouse", "created_by")
    if kind := request.GET.get("kind"):
        movements = movements.filter(kind=kind)
    return render(
        request,
        "dashboard/movements.html",
        {"movements": movements[:300], "kinds": StockMovement.Kind.choices},
    )


@staff_member_required
def warehouse_list(request):
    return render(request, "dashboard/warehouses.html", {"warehouses": Warehouse.objects.all()})


@staff_member_required
def warehouse_create(request):
    form = WarehouseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "أُضيف المستودع.")
        return redirect("dashboard:warehouses")
    return render(request, "dashboard/simple_form.html", {"form": form, "title": "مستودع جديد"})


@staff_member_required
def warehouse_edit(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)
    form = WarehouseForm(request.POST or None, instance=warehouse)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "حُفظت بيانات المستودع.")
        return redirect("dashboard:warehouses")
    return render(request, "dashboard/simple_form.html", {"form": form, "title": f"تعديل {warehouse.name}"})


# ── المشتريات ──────────────────────────────────────────────────
@staff_member_required
def purchase_list(request):
    orders = PurchaseOrder.objects.select_related("supplier", "warehouse")
    if status := request.GET.get("status"):
        orders = orders.filter(status=status)
    totals = orders.aggregate(t=Coalesce(Sum("total"), Decimal("0"), output_field=DEC), n=Count("id"))
    return render(
        request,
        "dashboard/purchases.html",
        {"orders": orders[:200], "statuses": PurchaseOrder.Status.choices, "totals": totals},
    )


def _save_purchase(request, instance=None):
    form = PurchaseOrderForm(request.POST or None, instance=instance)
    formset = PurchaseItemFormSet(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        order = form.save(commit=False)
        if not order.pk:
            order.created_by = request.user
        order.save()
        formset.instance = order
        formset.save()
        order.recalculate()
        messages.success(request, f"حُفظ أمر الشراء {order.number}.")
        return None, order
    return (form, formset), None


@staff_member_required
def purchase_create(request):
    forms_or_none, order = _save_purchase(request)
    if order:
        return redirect("dashboard:purchase_detail", pk=order.pk)
    form, formset = forms_or_none
    return render(request, "dashboard/purchase_form.html", {"form": form, "formset": formset, "title": "أمر شراء جديد"})


@staff_member_required
def purchase_edit(request, pk):
    instance = get_object_or_404(PurchaseOrder, pk=pk)
    if instance.status == PurchaseOrder.Status.RECEIVED:
        messages.error(request, "لا يمكن تعديل أمر مستلَم. أنشئ تسوية مخزون بدلاً من ذلك.")
        return redirect("dashboard:purchase_detail", pk=pk)
    forms_or_none, order = _save_purchase(request, instance)
    if order:
        return redirect("dashboard:purchase_detail", pk=order.pk)
    form, formset = forms_or_none
    return render(
        request, "dashboard/purchase_form.html", {"form": form, "formset": formset, "title": f"تعديل {instance.number}"}
    )


@staff_member_required
def purchase_detail(request, pk):
    order = get_object_or_404(PurchaseOrder.objects.select_related("supplier", "warehouse"), pk=pk)
    return render(request, "dashboard/purchase_detail.html", {"order": order})


@staff_member_required
def purchase_receive(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == "POST":
        try:
            order.receive(user=request.user)
            messages.success(request, f"استُلمت بضاعة {order.number} وأُضيفت إلى {order.warehouse}.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect("dashboard:purchase_detail", pk=pk)


@staff_member_required
def supplier_list(request):
    return render(request, "dashboard/suppliers.html", {"suppliers": Supplier.objects.all()})


@staff_member_required
def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "أُضيف المورّد.")
        return redirect("dashboard:suppliers")
    return render(request, "dashboard/simple_form.html", {"form": form, "title": "مورّد جديد"})


@staff_member_required
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "حُفظت بيانات المورّد.")
        return redirect("dashboard:suppliers")
    return render(request, "dashboard/simple_form.html", {"form": form, "title": f"تعديل {supplier.name}"})


# ── التقارير ───────────────────────────────────────────────────
@staff_member_required
def reports(request):
    start, end = _date_range(request, 90)
    sold = Order.objects.filter(status__in=PAID_STATUSES, created_at__date__gte=start)

    monthly = (
        sold.annotate(m=TruncMonth("created_at"))
        .values("m")
        .annotate(revenue=Sum("total"), orders=Count("id"), avg=Avg("total"))
        .order_by("m")
    )
    by_category = (
        OrderItem.objects.filter(order__in=sold)
        .values(name=F("product__category__name"))
        .annotate(units=Sum("quantity"), revenue=Sum(F("unit_price") * F("quantity"), output_field=DEC))
        .order_by("-revenue")[:10]
    )
    top_products = (
        OrderItem.objects.filter(order__in=sold)
        .values("product_name")
        .annotate(
            units=Sum("quantity"),
            revenue=Sum(F("unit_price") * F("quantity"), output_field=DEC),
            profit=Sum((F("unit_price") - F("cost_price")) * F("quantity"), output_field=DEC),
        )
        .order_by("-revenue")[:15]
    )
    top_customers = (
        sold.exclude(user__isnull=True)
        .values("user__username", "full_name")
        .annotate(spent=Sum("total"), orders=Count("id"))
        .order_by("-spent")[:10]
    )
    by_payment = sold.values("payment_method").annotate(n=Count("id"), t=Sum("total"))
    by_city = sold.values("city").annotate(n=Count("id"), t=Sum("total")).order_by("-t")[:10]

    revenue = sold.aggregate(t=Coalesce(Sum("total"), Decimal("0"), output_field=DEC))["t"]
    cost = OrderItem.objects.filter(order__in=sold).aggregate(
        c=Coalesce(Sum(F("cost_price") * F("quantity"), output_field=DEC), Decimal("0"), output_field=DEC)
    )["c"]

    context = {
        "start": start,
        "end": end,
        "days": request.GET.get("days", 90),
        "monthly": monthly,
        "by_category": by_category,
        "top_products": top_products,
        "top_customers": top_customers,
        "by_payment": by_payment,
        "by_city": by_city,
        "revenue": revenue,
        "cost": cost,
        "gross_profit": revenue - cost,
        "margin": round((revenue - cost) / revenue * 100, 1) if revenue else 0,
        "purchases_total": PurchaseOrder.objects.filter(
            status=PurchaseOrder.Status.RECEIVED, order_date__gte=start
        ).aggregate(t=Coalesce(Sum("total"), Decimal("0"), output_field=DEC))["t"],
    }
    return render(request, "dashboard/reports.html", context)


def _csv_response(filename, header, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


@staff_member_required
def export_orders_csv(request):
    rows = [
        [o.number, o.created_at.strftime("%Y-%m-%d"), o.full_name, o.phone, o.city,
         o.get_status_display(), o.get_payment_method_display(), o.subtotal, o.discount, o.tax, o.total]
        for o in Order.objects.all()[:5000]
    ]
    return _csv_response(
        "orders.csv",
        ["رقم الطلب", "التاريخ", "العميل", "الجوال", "المدينة", "الحالة", "الدفع", "المجموع", "الخصم", "الضريبة", "الإجمالي"],
        rows,
    )


@staff_member_required
def export_stock_csv(request):
    rows = [
        [s.product.sku, s.product.name, s.warehouse.name, s.quantity, s.reserved, s.reorder_level,
         s.product.cost_price, s.quantity * s.product.cost_price]
        for s in Stock.objects.select_related("product", "warehouse")[:5000]
    ]
    return _csv_response(
        "stock.csv",
        ["SKU", "المنتج", "المستودع", "الكمية", "محجوز", "حد الطلب", "التكلفة", "قيمة الرصيد"],
        rows,
    )
