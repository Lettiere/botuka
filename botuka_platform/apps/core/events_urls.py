from django.urls import path

from . import public_views
from apps.events import views as event_views

app_name = "events"
urlpatterns = [
    path("eventos/", public_views.eventos_lista, name="lista"),
    path("eventos/<slug:slug>/", event_views.publico_detalhe, name="detalhe"),
    path("eventos/<slug:slug>/interesse/", event_views.alternar_interesse, name="interesse"),
]
