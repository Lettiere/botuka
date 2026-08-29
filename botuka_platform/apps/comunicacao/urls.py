"""URLs internas do módulo Comunicação."""

from django.urls import path

from apps.comunicacao import views

app_name = "comunicacao"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path(
        "prospeccao/",
        views.prospeccao,
        name="prospeccao",
    ),
    path(
        "distribuicao/",
        views.distribuicao,
        name="distribuicao",
    ),
    path(
        "marketing/",
        views.marketing,
        name="marketing",
    ),
]
