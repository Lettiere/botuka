from django.urls import path
from . import views
def routes(prefix,name,views3):
    l,n,e=views3;return [path(f'ytv/{prefix}/',l,name=f'media_{name}_lista'),path(f'ytv/{prefix}/novo/',n,name=f'media_{name}_novo'),path(f'ytv/{prefix}/<uuid:uuid>/editar/',e,name=f'media_{name}_editar')]
urlpatterns=[]
for args in [('canais','canal',(views.canal_lista,views.canal_novo,views.canal_editar)),('programas','programa',(views.programa_lista,views.programa_novo,views.programa_editar)),('temporadas','temporada',(views.temporada_lista,views.temporada_novo,views.temporada_editar)),('episodios','episodio',(views.episodio_lista,views.episodio_novo,views.episodio_editar)),('transmissoes','transmissao',(views.transmissao_lista,views.transmissao_novo,views.transmissao_editar)),('pautas','pauta',(views.pauta_lista,views.pauta_novo,views.pauta_editar))]:urlpatterns+=routes(*args)
urlpatterns += [path('ytv/',views.episodio_lista,name='ytv_dashboard')]
