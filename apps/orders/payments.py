"""طبقة الدفع: Stripe للبطاقات، والدفع عند الاستلام والتحويل بدون بوابة."""
from decimal import Decimal

from django.conf import settings
from django.urls import reverse

from .models import Order, Payment

try:
    import stripe
except ImportError:  # pragma: no cover
    stripe = None


class PaymentError(Exception):
    pass


def stripe_enabled():
    return bool(stripe and settings.STRIPE_SECRET_KEY)


def create_checkout_session(request, order):
    """ينشئ جلسة دفع Stripe ويعيد رابط التحويل."""
    if not stripe_enabled():
        raise PaymentError("بوابة الدفع غير مهيأة. أضف مفاتيح Stripe في ملف .env.")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    base = request.build_absolute_uri("/").rstrip("/")
    line_items = [
        {
            "price_data": {
                "currency": settings.CURRENCY.lower(),
                "unit_amount": int(item.unit_price * 100),
                "product_data": {"name": item.product_name},
            },
            "quantity": item.quantity,
        }
        for item in order.items.all()
    ]
    extras = order.tax + order.shipping_cost - order.discount
    if extras > 0:
        line_items.append(
            {
                "price_data": {
                    "currency": settings.CURRENCY.lower(),
                    "unit_amount": int(extras * 100),
                    "product_data": {"name": "الضريبة والشحن"},
                },
                "quantity": 1,
            }
        )
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        customer_email=order.email,
        client_reference_id=order.number,
        success_url=f"{base}{reverse('orders:payment_success', args=[order.number])}",
        cancel_url=f"{base}{reverse('orders:payment_cancel', args=[order.number])}",
        metadata={"order_number": order.number},
    )
    Payment.objects.create(
        order=order,
        provider="stripe",
        reference=session.id,
        amount=order.total,
        status=Payment.Status.INITIATED,
    )
    return session.url


def confirm_stripe_session(order):
    """يتحقق من حالة الدفع لدى Stripe قبل اعتماد الطلب."""
    if not stripe_enabled():
        return False
    stripe.api_key = settings.STRIPE_SECRET_KEY
    payment = order.payments.filter(provider="stripe").first()
    if not payment or not payment.reference:
        return False
    session = stripe.checkout.Session.retrieve(payment.reference)
    if session.get("payment_status") == "paid":
        payment.status = Payment.Status.SUCCEEDED
        payment.raw_response = {"id": session.get("id"), "payment_status": session.get("payment_status")}
        payment.save(update_fields=["status", "raw_response"])
        return True
    payment.status = Payment.Status.FAILED
    payment.save(update_fields=["status"])
    return False


def record_offline_payment(order):
    """الدفع عند الاستلام أو التحويل: يُسجَّل كعملية معلّقة."""
    Payment.objects.create(
        order=order,
        provider=order.payment_method,
        amount=order.total,
        status=Payment.Status.INITIATED,
    )
    order.status = Order.Status.PROCESSING
    order.save(update_fields=["status"])
    order.release_stock()
