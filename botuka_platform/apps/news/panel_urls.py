from django.urls import path
from . import views
def routes(prefix,name,v):
 l,n,e=v;return [path(f'news/{prefix}/',l,name=f'news_{name}_lista'),path(f'news/{prefix}/novo/',n,name=f'news_{name}_novo'),path(f'news/{prefix}/<uuid:uuid>/editar/',e,name=f'news_{name}_editar')]
urlpatterns=[]
for a in [('categorias','categorianoticia',(views.categoria_lista,views.categoria_novo,views.categoria_editar)),('artigos','artigo',(views.artigo_lista,views.artigo_novo,views.artigo_editar)),('blocos','artigobloco',(views.bloco_lista,views.bloco_novo,views.bloco_editar)),('fontes','artigofonte',(views.fonte_lista,views.fonte_novo,views.fonte_editar))]:urlpatterns+=routes(*a)
urlpatterns += [path('news/',views.artigo_lista,name='news_dashboard'),path('news/revisao/',views.artigo_lista,name='news_revisao')]
