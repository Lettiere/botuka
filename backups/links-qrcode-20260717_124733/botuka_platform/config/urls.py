from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from apps.core.views import home, offline, pwa_manifest, service_worker

urlpatterns = [
    path("", home, name="home"),
    path("manifest.webmanifest", pwa_manifest, name="pwa_manifest"),
    path("service-worker.js", service_worker, name="service_worker"),
    path("offline/", offline, name="offline"),
    path("conta/", include("apps.accounts.urls")),
    path("painel/", include("apps.painel.urls")),
    path("gestao/", include("apps.gestao.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
