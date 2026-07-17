from django.urls import path

from apps.services import views

app_name = 'publico'

urlpatterns = [
    path('servicos/<slug:slug>/', views.servico_publico, name='servico'),
    path('empresas/<slug:slug>/', views.empresa_publica, name='empresa'),
    path('q/s/<uuid:token>/', views.qrcode_servico_redirect, name='qrcode_servico'),
    path('q/e/<uuid:token>/', views.qrcode_empresa_redirect, name='qrcode_empresa'),
]
