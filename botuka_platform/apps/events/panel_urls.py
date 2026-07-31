from django.urls import path
from . import views

urlpatterns = [
    path('eventos/', views.painel_lista, name='eventos_lista'),
    path('eventos/novo/', views.painel_criar, name='evento_criar'),
    path('eventos/<uuid:uuid>/', views.painel_detalhe, name='evento_detalhe'),
    path('eventos/<uuid:uuid>/editar/', views.painel_editar, name='evento_editar'),
    path('eventos/<uuid:uuid>/status/', views.painel_status, name='evento_status'),
    path('eventos/<uuid:uuid>/interessados/', views.painel_interessados, name='evento_interessados'),
    path('eventos/<uuid:uuid>/metricas/', views.painel_metricas, name='evento_metricas'),
]
