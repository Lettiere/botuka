from django.contrib import admin
from django.urls import path, include

from apps.core.views import home

urlpatterns = [
    path("", home, name="home"),
    path("conta/", include("apps.accounts.urls")),
    path("admin/", admin.site.urls),
]