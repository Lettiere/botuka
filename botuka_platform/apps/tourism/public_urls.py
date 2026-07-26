from django.urls import path

from . import views

app_name = 'tourism_public'

urlpatterns = [
    path('turismo/', views.turismo_home, name='home'),
    path('turismo/locais/', views.locais_publicos, name='locais'),
    path('turismo/local/<slug:slug>/', views.local_publico, name='local'),
    path('turismo/guias/', views.guias_publicos, name='guias'),
    path('turismo/guia/<slug:slug>/', views.guia_publico, name='guia'),
    path('turismo/roteiros/', views.roteiros_publicos, name='roteiros'),
    path('turismo/roteiro/<slug:slug>/', views.roteiro_publico, name='roteiro'),
]
