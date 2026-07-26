from django.urls import path
from . import views
app_name='media_public'
urlpatterns=[path('ytv/',views.home,name='home'),path('ytv/programas/<slug:slug>/',views.programa,name='programa'),path('ytv/episodios/<slug:slug>/',views.episodio,name='episodio'),path('ytv/ao-vivo/',views.ao_vivo,name='ao_vivo')]
urlpatterns += [
    path('yubotuka/', views.public_home, name='yubotuka_home'),
    path('yubotuka/videos/<slug:slug>/', views.video_publico, name='video'),
    path('yubotuka/categorias/<slug:slug>/', views.categoria_publica, name='categoria'),
    path('yubotuka/playlists/<slug:slug>/', views.playlist_publica, name='playlist'),
    path('yubotuka/canais/<slug:slug>/', views.canal_publico, name='canal'),
    path('yubotuka/programas/<slug:slug>/', views.programa_publico, name='yubotuka_programa'),
    path('yubotuka/programas/<slug:programa_slug>/temporadas/<int:numero>/', views.temporada_publica, name='temporada'),
    path('yubotuka/ao-vivo/', views.transmissao_ao_vivo_publica, name='yubotuka_ao_vivo'),
    path('yubotuka/transmissoes/', views.transmissoes_publicas_lista, name='transmissoes'),
    path('yubotuka/transmissoes/<slug:slug>/', views.transmissao_publica, name='transmissao'),
]
