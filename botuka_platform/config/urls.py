from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import index as sitemap_index, sitemap
from django.views.decorators.cache import cache_page
from django.urls import path, include

from apps.core.views import home, offline, pwa_manifest, service_worker
from apps.core.seo.sitemaps import SITEMAPS
from apps.core.seo.views import robots_txt

handler404 = 'apps.core.views.not_found'
handler500 = 'apps.core.views.server_error'

urlpatterns = [
    path('robots.txt', cache_page(3600)(robots_txt), name='robots_txt'),
    path('sitemap.xml', cache_page(3600)(sitemap_index), {'sitemaps': SITEMAPS, 'sitemap_url_name': 'sitemap-section'}, name='sitemap-index'),
    path('sitemaps/<section>.xml', cache_page(3600)(sitemap), {'sitemaps': SITEMAPS}, name='sitemap-section'),
    path("", include("apps.core.events_urls")),
    path("", include("apps.services.urls")),
    path("", include("apps.recruitment.public_urls")),
    path("", include("apps.sports.public_urls")),
    path("", include("apps.media.public_urls")),
    path("", include("apps.news.public_urls")),
    path("", include("apps.government.public_urls")),
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
