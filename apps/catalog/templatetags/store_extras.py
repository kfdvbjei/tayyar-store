from django import template
from django.conf import settings

register = template.Library()


@register.filter
def money(value):
    """يعرض المبلغ بصيغة نقدية موحّدة."""
    try:
        return f"{float(value):,.2f} {settings.CURRENCY_SYMBOL}"
    except (TypeError, ValueError):
        return value


@register.filter
def money0(value):
    try:
        return f"{float(value):,.0f} {settings.CURRENCY_SYMBOL}"
    except (TypeError, ValueError):
        return value


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """يحدّث معامِلات الرابط مع الحفاظ على الفلاتر الحالية."""
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        query[key] = value
    return query.urlencode()


@register.filter
def stars(value):
    full = int(round(value or 0))
    return "★" * full + "☆" * (5 - full)


@register.filter
def energy_class(rating):
    return {"A+++": "e-a3", "A++": "e-a2", "A+": "e-a1", "A": "e-a", "B": "e-b", "C": "e-c", "D": "e-d"}.get(rating, "e-a")


@register.filter
def status_class(status):
    return {
        "pending": "warn", "paid": "ok", "processing": "info", "shipped": "info",
        "delivered": "ok", "cancelled": "bad", "refunded": "bad",
        "draft": "muted", "ordered": "info", "received": "ok",
    }.get(status, "muted")
