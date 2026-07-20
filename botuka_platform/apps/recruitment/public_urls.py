from django.urls import path
from . import views

app_name = 'recruitment_public'
urlpatterns = [
    path('vagas/', views.vagas_publicas, name='vagas'),
    path('vagas/<slug:slug>/', views.vaga_publica, name='vaga'),
    path('vagas/<slug:slug>/candidatar/', views.candidatar, name='candidatar'),
    path('curriculos/<uuid:uuid>/', views.curriculo_publico_view, name='curriculo'),
]
