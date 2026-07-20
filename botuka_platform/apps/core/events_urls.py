from django.urls import path

from . import public_views

app_name = "events"
urlpatterns = [path("eventos/", public_views.eventos_lista, name="lista")]
