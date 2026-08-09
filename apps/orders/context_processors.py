from .cart import get_cart


def cart_context(request):
    cart = get_cart(request, create=False)
    return {
        "cart": cart,
        "cart_count": cart.item_count if cart else 0,
        "cart_total": cart.total if cart else 0,
    }
