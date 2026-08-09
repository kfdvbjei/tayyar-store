from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Max, Min, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from .forms import ReviewForm
from .models import Banner, Brand, Category, Product

SORT_OPTIONS = {
    "newest": ("-created_at", "الأحدث"),
    "price_asc": ("price", "الأقل سعراً"),
    "price_desc": ("-price", "الأعلى سعراً"),
    "popular": ("-views_count", "الأكثر مشاهدة"),
    "discount": ("-discount_calc", "أكبر خصم"),
}


def home(request):
    products = Product.objects.active().select_related("brand", "category").prefetch_related("images")
    context = {
        "banners": Banner.objects.filter(is_active=True),
        "categories": Category.objects.filter(is_active=True, parent__isnull=True)[:8],
        "featured": products.filter(is_featured=True)[:8],
        "newest": products.order_by("-created_at")[:8],
        "deals": products.filter(compare_at_price__gt=F("price"))[:8],
        "brands": Brand.objects.filter(is_active=True)[:12],
    }
    return render(request, "catalog/home.html", context)


class ProductListView(ListView):
    """قائمة المنتجات مع البحث والفلترة والترتيب."""

    model = Product
    template_name = "catalog/product_list.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        qs = (
            Product.objects.active()
            .select_related("brand", "category")
            .prefetch_related("images")
            .with_stock()
        )
        p = self.request.GET

        if q := p.get("q", "").strip():
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(sku__icontains=q)
                | Q(description__icontains=q)
                | Q(short_description__icontains=q)
                | Q(brand__name__icontains=q)
                | Q(category__name__icontains=q)
            )
        if cats := p.getlist("category"):
            qs = qs.filter(Q(category__slug__in=cats) | Q(category__parent__slug__in=cats))
        if brands := p.getlist("brand"):
            qs = qs.filter(brand__slug__in=brands)
        if energy := p.getlist("energy"):
            qs = qs.filter(energy_rating__in=energy)
        if (mn := p.get("min_price", "")).isdigit():
            qs = qs.filter(price__gte=mn)
        if (mx := p.get("max_price", "")).isdigit():
            qs = qs.filter(price__lte=mx)
        if p.get("in_stock") == "1":
            qs = qs.filter(stock_total__gt=0)
        if p.get("on_sale") == "1":
            qs = qs.filter(compare_at_price__gt=F("price"))

        sort = p.get("sort", "newest")
        if sort == "discount":
            qs = qs.annotate(discount_calc=F("compare_at_price") - F("price"))
        return qs.order_by(SORT_OPTIONS.get(sort, SORT_OPTIONS["newest"])[0])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        bounds = Product.objects.active().aggregate(lo=Min("price"), hi=Max("price"))
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx.update(
            {
                "categories": Category.objects.filter(is_active=True).annotate(n=Count("products")),
                "brands": Brand.objects.filter(is_active=True).annotate(n=Count("products")),
                "energy_choices": Product.ENERGY_CHOICES,
                "sort_options": SORT_OPTIONS,
                "current_sort": self.request.GET.get("sort", "newest"),
                "q": self.request.GET.get("q", ""),
                "selected_categories": self.request.GET.getlist("category"),
                "selected_brands": self.request.GET.getlist("brand"),
                "selected_energy": self.request.GET.getlist("energy"),
                "price_floor": int(bounds["lo"] or 0),
                "price_ceiling": int(bounds["hi"] or 10000),
                "querystring": params.urlencode(),
            }
        )
        return ctx


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("brand", "category").prefetch_related("images", "reviews__user"),
        slug=slug,
        is_active=True,
    )
    Product.objects.filter(pk=product.pk).update(views_count=F("views_count") + 1)
    related = (
        Product.objects.active()
        .filter(category=product.category)
        .exclude(pk=product.pk)
        .select_related("brand")[:4]
    )
    has_reviewed = request.user.is_authenticated and product.reviews.filter(user=request.user).exists()
    context = {
        "product": product,
        "related": related,
        "reviews": product.reviews.filter(is_approved=True),
        "review_form": ReviewForm(),
        "has_reviewed": has_reviewed,
        "stock_by_warehouse": product.stock_records.select_related("warehouse"),
    }
    return render(request, "catalog/product_detail.html", context)


@login_required
def add_review(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid() and not product.reviews.filter(user=request.user).exists():
            review = form.save(commit=False)
            review.product, review.user = product, request.user
            review.save()
            messages.success(request, "وصل تقييمك. سيُنشر بعد المراجعة.")
        else:
            messages.error(request, "تعذّر حفظ التقييم — لديك تقييم سابق لهذا المنتج أو البيانات ناقصة.")
    return redirect(product.get_absolute_url())


@login_required
def toggle_wishlist(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if product.wishlisted_by.filter(pk=request.user.pk).exists():
        product.wishlisted_by.remove(request.user)
        added = False
    else:
        product.wishlisted_by.add(request.user)
        added = True
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"added": added})
    return redirect(product.get_absolute_url())


def compare(request):
    slugs = [s for s in request.GET.getlist("p") if s][:4]
    products = Product.objects.filter(slug__in=slugs).select_related("brand", "category")
    return render(request, "catalog/compare.html", {"products": products})


def search_suggest(request):
    """اقتراحات فورية أثناء الكتابة في شريط البحث."""
    q = request.GET.get("q", "").strip()
    results = []
    if len(q) >= 2:
        for p in Product.objects.active().filter(Q(name__icontains=q) | Q(brand__name__icontains=q))[:6]:
            results.append(
                {
                    "name": str(p),
                    "url": p.get_absolute_url(),
                    "price": f"{p.price:,.0f} {settings.CURRENCY_SYMBOL}",
                    "image": p.main_image or "",
                }
            )
    return JsonResponse({"results": results})


def about(request):
    return render(request, "catalog/about.html")


def contact(request):
    if request.method == "POST":
        messages.success(request, "وصلت رسالتك. نرد خلال يوم عمل.")
        return redirect("catalog:contact")
    return render(request, "catalog/contact.html")


def error_404(request, exception):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)
