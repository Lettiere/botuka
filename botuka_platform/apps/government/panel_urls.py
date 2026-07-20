from django.urls import path
from . import views
def routes(prefix,name,v):
 l,n,e=v;return [path(f'prefeitura/{prefix}/',l,name=f'government_{name}_lista'),path(f'prefeitura/{prefix}/novo/',n,name=f'government_{name}_novo'),path(f'prefeitura/{prefix}/<uuid:uuid>/editar/',e,name=f'government_{name}_editar')]
urlpatterns=[]
for a in [('orgaos','orgaopublico',(views.orgao_lista,views.orgao_novo,views.orgao_editar)),('acoes','acaopublica',(views.acao_lista,views.acao_novo,views.acao_editar)),('atualizacoes','acaoatualizacao',(views.atualizacao_lista,views.atualizacao_novo,views.atualizacao_editar)),('documentos','acaodocumento',(views.documento_lista,views.documento_novo,views.documento_editar)),('links','acaolink',(views.link_lista,views.link_novo,views.link_editar))]:urlpatterns+=routes(*a)
urlpatterns += [path('prefeitura/',views.acao_lista,name='government_dashboard')]
