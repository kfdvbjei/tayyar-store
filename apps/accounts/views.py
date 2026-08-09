from django.contrib import messages
from django.contrib.auth import login, views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.models import Product
from apps.orders.models import Order

from .forms import AddressForm, LoginForm, ProfileForm, RegisterForm
from .models import Address


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    next_page = "catalog:home"


def register(request):
    if request.user.is_authenticated:
        return redirect("catalog:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="apps.accounts.backends.EmailOrUsernameBackend")
        messages.success(request, f"أهلاً {user.display_name}. حسابك جاهز.")
        return redirect("catalog:home")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "حُفظت بيانات الحساب.")
        return redirect("accounts:profile")
    orders = Order.objects.filter(user=request.user)[:5]
    return render(request, "accounts/profile.html", {"form": form, "orders": orders})


@login_required
def address_list(request):
    return render(request, "accounts/addresses.html", {"addresses": request.user.addresses.all()})


@login_required
def address_create(request):
    form = AddressForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        address.save()
        messages.success(request, "أُضيف العنوان.")
        return redirect("accounts:addresses")
    return render(request, "accounts/address_form.html", {"form": form, "title": "إضافة عنوان"})


@login_required
def address_edit(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    form = AddressForm(request.POST or None, instance=address)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "حُدّث العنوان.")
        return redirect("accounts:addresses")
    return render(request, "accounts/address_form.html", {"form": form, "title": "تعديل عنوان"})


@login_required
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == "POST":
        address.delete()
        messages.info(request, "حُذف العنوان.")
    return redirect("accounts:addresses")


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items")
    return render(request, "accounts/orders.html", {"orders": orders})


@login_required
def my_order_detail(request, number):
    order = get_object_or_404(Order.objects.prefetch_related("items"), number=number, user=request.user)
    return render(request, "accounts/order_detail.html", {"order": order})


@login_required
def wishlist(request):
    products = Product.objects.filter(wishlisted_by=request.user).select_related("brand")
    return render(request, "accounts/wishlist.html", {"products": products})
