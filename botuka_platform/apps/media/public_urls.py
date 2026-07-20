from django.urls import path
from . import views
app_name='media_public'
urlpatterns=[path('ytv/',views.home,name='home'),path('ytv/programas/<slug:slug>/',views.programa,name='programa'),path('ytv/episodios/<slug:slug>/',views.episodio,name='episodio'),path('ytv/ao-vivo/',views.ao_vivo,name='ao_vivo')]
