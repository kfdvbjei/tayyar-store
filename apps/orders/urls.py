from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.cart_detail, name="cart"),
    path("add/<int:product_id>/", views.cart_add, name="cart_add"),
    path("update/<int:item_id>/", views.cart_update, name="cart_update"),
    path("remove/<int:item_id>/", views.cart_remove, name="cart_remove"),
    path("coupon/apply/", views.apply_coupon, name="apply_coupon"),
    path("coupon/remove/", views.remove_coupon, name="remove_coupon"),
    path("checkout/", views.checkout, name="checkout"),
    path("payment/<str:number>/success/", views.payment_success, name="payment_success"),
    path("payment/<str:number>/cancel/", views.payment_cancel, name="payment_cancel"),
    path("payment/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("invoice/<str:number>/", views.invoice, name="invoice"),
]
