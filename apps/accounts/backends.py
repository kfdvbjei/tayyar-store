from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """يسمح بتسجيل الدخول بالبريد الإلكتروني أو اسم المستخدم."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            user = User.objects.get(Q(username__iexact=username) | Q(email__iexact=username))
        except User.DoesNotExist:
            User().set_password(password)  # يمنع تسريب وجود الحساب عبر توقيت الرد
            return None
        except User.MultipleObjectsReturned:
            user = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).order_by("id").first()
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
