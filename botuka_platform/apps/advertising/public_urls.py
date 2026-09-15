from django.urls import path

from .views import entrega_clique

app_name = 'advertising_public'
urlpatterns = [
    path('entrega/<uuid:uuid>/clique/', entrega_clique, name='entrega_clique'),
]
