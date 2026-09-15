from django.urls import path

from . import views

app_name = 'advertising'
urlpatterns = [
    path('', views.campanha_lista, name='campanha_lista'),
    path('nova/', views.campanha_criar, name='campanha_criar'),
    path('administracao/', views.campanha_administracao, name='campanha_administracao'),
    path('administracao/configuracoes/', views.configuracao_comercial, name='configuracao_comercial'),
    path('administracao/planos/novo/', views.plano_editar, name='plano_criar'),
    path('administracao/planos/<int:pk>/', views.plano_editar, name='plano_editar'),
    path('administracao/posicionamentos/novo/', views.posicionamento_editar, name='posicionamento_criar'),
    path('administracao/posicionamentos/<int:pk>/', views.posicionamento_editar, name='posicionamento_editar'),
    path('<uuid:uuid>/', views.campanha_detalhe, name='campanha_detalhe'),
    path('<uuid:uuid>/editar/', views.campanha_editar, name='campanha_editar'),
    path('<uuid:uuid>/criativo/', views.campanha_adicionar_criativo, name='campanha_criativo'),
    path('<uuid:uuid>/segmentacao/', views.campanha_segmentar, name='campanha_segmentar'),
    path('<uuid:uuid>/contratar/', views.campanha_contratar, name='campanha_contratar'),
    path('<uuid:uuid>/pagar-local/', views.campanha_pagar_fake, name='campanha_pagar_fake'),
    path('<uuid:uuid>/cancelar/', views.campanha_cancelar, name='campanha_cancelar'),
    path('<uuid:uuid>/aprovar/', views.campanha_aprovar, name='campanha_aprovar'),
    path('<uuid:uuid>/moderar/<slug:acao>/', views.campanha_moderar, name='campanha_moderar'),
]
