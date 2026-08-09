from django.conf import settings

from .models import Category


def store_context(request):
    """بيانات المتجر المتاحة في كل القوالب."""
    return {
        "STORE_NAME": settings.STORE_NAME,
        "STORE_TAGLINE": settings.STORE_TAGLINE,
        "CURRENCY_SYMBOL": settings.CURRENCY_SYMBOL,
        "FREE_SHIPPING_THRESHOLD": settings.FREE_SHIPPING_THRESHOLD,
        "nav_categories": Category.objects.filter(is_active=True, parent__isnull=True)[:8],
    }
