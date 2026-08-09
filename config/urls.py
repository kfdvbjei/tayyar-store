from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("secure-admin/", admin.site.urls),
    path("", include("apps.catalog.urls")),
    path("account/", include("apps.accounts.urls")),
    path("cart/", include("apps.orders.urls")),
    path("manage/", include("apps.dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "تيّار — لوحة إدارة Django"
admin.site.site_title = "تيّار"
admin.site.index_title = "إدارة المتجر"

handler404 = "apps.catalog.views.error_404"
handler500 = "apps.catalog.views.error_500"
