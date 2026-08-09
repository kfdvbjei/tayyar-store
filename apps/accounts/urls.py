from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("addresses/", views.address_list, name="addresses"),
    path("addresses/add/", views.address_create, name="address_create"),
    path("addresses/<int:pk>/edit/", views.address_edit, name="address_edit"),
    path("addresses/<int:pk>/delete/", views.address_delete, name="address_delete"),
    path("orders/", views.my_orders, name="orders"),
    path("orders/<str:number>/", views.my_order_detail, name="order_detail"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path(
        "password/change/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html",
            success_url="/account/profile/",
        ),
        name="password_change",
    ),
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.txt",
            success_url="/account/password/reset/sent/",
        ),
        name="password_reset",
    ),
    path(
        "password/reset/sent/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_sent.html"),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url="/account/login/",
        ),
        name="password_reset_confirm",
    ),
]
