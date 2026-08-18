from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.generic import RedirectView


handler404 = 'apps.social.views.runtime_not_found'
handler403 = 'apps.social.views.runtime_forbidden'
handler500 = 'apps.social.views.runtime_error'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='social:home', permanent=False), name='social_runtime_root'),
    path('', include('apps.social.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
