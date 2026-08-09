from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.accounts.models import Address
from apps.catalog.models import Product

from . import payments
from .cart import get_cart
from .forms import CheckoutForm, CouponForm
from .models import Cart, CartItem, Coupon, Order, OrderItem, Payment


def cart_detail(request):
    cart = get_cart(request)
    return render(request, "orders/cart.html", {"cart": cart, "coupon_form": CouponForm()})


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    quantity = max(1, int(request.POST.get("quantity", 1) or 1))
    cart = get_cart(request)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": quantity})
    if not created:
        item.quantity += quantity
    available = product.stock
    if available and item.quantity > available:
        item.quantity = available
        messages.warning(request, f"المتوفر من «{product.name}» {available} قطعة فقط.")
    item.save()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"count": cart.item_count, "total": str(cart.total)})
    messages.success(request, f"أُضيف «{product.name}» إلى السلة.")
    return redirect(request.POST.get("next") or "orders:cart")


@require_POST
def cart_update(request, item_id):
    cart = get_cart(request)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    quantity = int(request.POST.get("quantity", 1) or 1)
    if quantity < 1:
        item.delete()
    else:
        available = item.product.stock
        if available and quantity > available:
            quantity = available
            messages.warning(request, f"المتوفر {available} قطعة فقط.")
        item.quantity = quantity
        item.save()
    return redirect("orders:cart")


@require_POST
def cart_remove(request, item_id):
    cart = get_cart(request)
    get_object_or_404(CartItem, pk=item_id, cart=cart).delete()
    messages.info(request, "أُزيل المنتج من السلة.")
    return redirect("orders:cart")


@require_POST
def apply_coupon(request):
    cart = get_cart(request)
    form = CouponForm(request.POST)
    if form.is_valid():
        coupon = Coupon.objects.filter(code__iexact=form.cleaned_data["code"].strip()).first()
        if not coupon:
            messages.error(request, "رمز الكوبون غير موجود.")
        else:
            ok, reason = coupon.is_valid_for(cart.subtotal)
            if ok:
                cart.coupon = coupon
                cart.save(update_fields=["coupon"])
                messages.success(request, f"طُبِّق الكوبون. وفّرت {cart.discount:,.2f} ر.س.")
            else:
                messages.error(request, reason)
    return redirect("orders:cart")


@require_POST
def remove_coupon(request):
    cart = get_cart(request)
    cart.coupon = None
    cart.save(update_fields=["coupon"])
    return redirect("orders:cart")


@transaction.atomic
def _build_order(cart, form, user):
    order = form.save(commit=False)
    if user.is_authenticated:
        order.user = user
    order.subtotal = cart.subtotal
    order.discount = cart.discount
    order.tax = cart.tax
    order.shipping_cost = cart.shipping
    order.total = cart.total
    order.coupon_code = cart.coupon.code if cart.coupon else ""
    order.save()
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                product=item.product,
                product_name=str(item.product),
                sku=item.product.sku,
                unit_price=item.product.price,
                cost_price=item.product.cost_price,
                quantity=item.quantity,
            )
            for item in cart.items.select_related("product")
        ]
    )
    if cart.coupon:
        Coupon.objects.filter(pk=cart.coupon_id).update(used_count=cart.coupon.used_count + 1)
    return order


def checkout(request):
    cart = get_cart(request)
    if not cart or not cart.items.exists():
        messages.info(request, "سلتك فارغة. اختر جهازاً لتبدأ.")
        return redirect("catalog:products")

    # تحقق من توفر المخزون قبل إتمام الطلب
    for item in cart.items.select_related("product"):
        if item.product.stock < item.quantity:
            messages.error(request, f"المتوفر من «{item.product.name}» {item.product.stock} فقط. عدّل الكمية للمتابعة.")
            return redirect("orders:cart")

    form = CheckoutForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        order = _build_order(cart, form, request.user)
        if form.cleaned_data.get("save_address") and request.user.is_authenticated:
            Address.objects.get_or_create(
                user=request.user,
                city=order.city,
                street=order.street,
                defaults={
                    "full_name": order.full_name,
                    "phone": order.phone,
                    "district": order.district,
                    "postal_code": order.postal_code,
                    "is_default": not request.user.addresses.exists(),
                },
            )
        cart.items.all().delete()
        cart.coupon = None
        cart.save(update_fields=["coupon"])

        if order.payment_method == Order.PaymentMethod.CARD:
            try:
                return redirect(payments.create_checkout_session(request, order))
            except payments.PaymentError as exc:
                messages.error(request, str(exc))
                return redirect("orders:payment_cancel", number=order.number)
        payments.record_offline_payment(order)
        return redirect("orders:payment_success", number=order.number)

    return render(
        request,
        "orders/checkout.html",
        {"cart": cart, "form": form, "stripe_ready": payments.stripe_enabled()},
    )


def payment_success(request, number):
    order = get_object_or_404(Order, number=number)
    if order.payment_method == Order.PaymentMethod.CARD and not order.is_paid:
        if payments.confirm_stripe_session(order):
            order.mark_paid()
        else:
            messages.warning(request, "لم يُؤكَّد الدفع بعد. سنحدّث حالة الطلب فور وصول التأكيد من البنك.")
    return render(request, "orders/order_success.html", {"order": order})


def payment_cancel(request, number):
    order = get_object_or_404(Order, number=number)
    return render(request, "orders/payment_cancel.html", {"order": order})


@csrf_exempt
def stripe_webhook(request):
    """يعتمد الدفع من طرف البنك مباشرة — الأكثر موثوقية من صفحة النجاح."""
    if not payments.stripe_enabled():
        return HttpResponse(status=503)
    import stripe

    payload = request.body
    signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponseBadRequest("توقيع غير صالح")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order = Order.objects.filter(number=session.get("metadata", {}).get("order_number")).first()
        if order and not order.is_paid:
            Payment.objects.filter(order=order, reference=session.get("id")).update(
                status=Payment.Status.SUCCEEDED, raw_response={"id": session.get("id")}
            )
            order.mark_paid()
    return HttpResponse(status=200)


def invoice(request, number):
    order = get_object_or_404(Order.objects.prefetch_related("items"), number=number)
    if not (request.user.is_staff or (request.user.is_authenticated and order.user_id == request.user.id)):
        return HttpResponseBadRequest("غير مصرّح لك بعرض هذه الفاتورة.")
    return render(request, "orders/invoice.html", {"order": order, "vat_rate": int(settings.VAT_RATE * 100)})
