"""أدوات الحصول على السلة الحالية وربطها بالمستخدم.

سلة الزائر تُخزَّن بمعرّفها داخل الجلسة (وليس بمفتاح الجلسة)، لأن جانجو
يجدّد مفتاح الجلسة عند تسجيل الدخول بينما تبقى بيانات الجلسة كما هي.
"""
from .models import Cart

SESSION_KEY = "cart_id"


def get_cart(request, create=True):
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        if cart is None and create:
            cart = Cart.objects.create(user=request.user)
        return cart

    cart_id = request.session.get(SESSION_KEY)
    cart = Cart.objects.filter(pk=cart_id, user__isnull=True).first() if cart_id else None
    if cart is None and create:
        if not request.session.session_key:
            request.session.create()
        cart = Cart.objects.create(session_key=request.session.session_key)
        request.session[SESSION_KEY] = cart.pk
    return cart


def merge_session_cart(request, user):
    """يُستدعى بعد تسجيل الدخول لدمج سلة الزائر في سلة الحساب."""
    cart_id = request.session.pop(SESSION_KEY, None)
    if not cart_id:
        return
    guest = Cart.objects.filter(pk=cart_id, user__isnull=True).first()
    if not guest:
        return
    user_cart, _ = Cart.objects.get_or_create(user=user)
    if user_cart.pk == guest.pk:
        return
    user_cart.merge_from(guest)
