from django.urls import path
from . import views
app_name='sports_public';urlpatterns=[path('esportes/',views.home,name='home'),path('esportes/modalidades/<slug:slug>/',views.modalidade,name='modalidade'),path('esportes/equipes/<slug:slug>/',views.equipe,name='equipe'),path('esportes/atletas/<uuid:uuid>/',views.atleta,name='atleta'),path('esportes/campeonatos/<slug:slug>/',views.campeonato,name='campeonato'),path('esportes/jogos/<uuid:uuid>/',views.jogo,name='jogo')]
