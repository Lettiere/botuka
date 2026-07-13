from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),

    path(
        "prestadores/<slug:slug>/",
        views.prestador_perfil,
        name="prestador_perfil",
    ),
]