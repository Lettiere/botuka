from django.urls import path
from . import views

urlpatterns = [
    path('produtos/api/setores/', views.api_setores, name='api_produtos_setores'),
    path('produtos/api/categorias/', views.api_categorias, name='api_produtos_categorias'),
    path('produtos/api/familias/', views.api_familias, name='api_produtos_familias'),
    path('produtos/api/tipos/', views.api_tipos, name='api_produtos_tipos'),
    path('produtos/', views.painel_lista, name='produtos_lista'),
    path('produtos/novo/', views.painel_criar, name='produto_criar'),
    path('empresas/<uuid:empresa_uuid>/produtos/', views.painel_empresa_produtos, name='empresa_produtos'),
    path('empresas/<uuid:empresa_uuid>/produtos/novo/', views.painel_criar, name='empresa_produto_criar'),
    path('conversas/', views.painel_conversas, name='produto_conversas'),
    path('produtos/denuncias/', views.painel_denuncias, name='produto_denuncias'),
    path('produtos/<uuid:uuid>/', views.painel_detalhe, name='produto_detalhe'),
    path('produtos/<uuid:uuid>/editar/', views.painel_editar, name='produto_editar'),
    path('produtos/<uuid:uuid>/status/', views.painel_status, name='produto_status'),
    path('produtos/<uuid:uuid>/imagens/', views.painel_imagens, name='produto_imagens'),
    path('produtos/<uuid:uuid>/excluir/', views.painel_excluir, name='produto_excluir'),
    path('produtos/<uuid:uuid>/imagens/<uuid:image_uuid>/excluir/', views.painel_excluir_imagem, name='produto_imagem_excluir'),
]
