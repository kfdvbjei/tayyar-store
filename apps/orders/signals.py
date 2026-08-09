from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .cart import merge_session_cart


@receiver(user_logged_in)
def merge_cart_on_login(sender, request, user, **kwargs):
    merge_session_cart(request, user)
