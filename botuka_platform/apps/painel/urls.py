"""URLs da área interna do usuário."""

from django.urls import path

from apps.painel import views

app_name = 'painel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('perfil/', views.perfil, name='perfil'),
    path('empresas/', views.empresas_lista, name='empresas_lista'),
    path('empresas/nova/', views.empresa_criar, name='empresa_criar'),
    path('empresas/adicionar/', views.empresa_adicionar, name='empresa_adicionar'),
    path('empresas/ajax/consultar-cnpj/', views.empresa_ajax_consultar_cnpj, name='empresa_ajax_consultar_cnpj'),
    path('empresas/solicitacoes/', views.empresa_solicitacoes_lista, name='empresa_solicitacoes_lista'),
    path('empresas/solicitacoes/<int:pk>/analisar/', views.empresa_solicitacao_analisar, name='empresa_solicitacao_analisar'),
    path('empresas/<int:pk>/', views.empresa_detalhe, name='empresa_detalhe'),
    path('empresas/<int:pk>/editar/', views.empresa_editar, name='empresa_editar'),
    path('empresas/<int:pk>/equipe/', views.empresa_equipe, name='empresa_equipe'),
    path('empresas/<int:pk>/capacidades/', views.empresa_capacidades, name='empresa_capacidades'),
    path('empresas/<int:pk>/documentos/', views.empresa_documentos, name='empresa_documentos'),
    path('empresas/<int:pk>/enderecos/', views.empresa_enderecos, name='empresa_enderecos'),
    path('empresas/<int:pk>/solicitacoes/', views.empresa_solicitacoes, name='empresa_solicitacoes'),
    path('empresas/<int:pk>/status/', views.empresa_alterar_status, name='empresa_alterar_status'),
    path('empresas/<int:pk>/excluir/', views.empresa_excluir, name='empresa_excluir'),
    path('publicacoes/', views.publicacoes_lista, name='publicacoes_lista'),
    path('servicos/', views.servicos_lista, name='servicos_lista'),
    path('servicos/novo/', views.servico_criar, name='servico_criar'),
    path('servicos/ajax/profissoes/', views.servicos_ajax_profissoes, name='servicos_ajax_profissoes'),
    path('servicos/<int:pk>/', views.servico_detalhe, name='servico_detalhe'),
    path('servicos/<int:pk>/editar/', views.servico_editar, name='servico_editar'),
    path('servicos/<int:pk>/excluir/', views.servico_excluir, name='servico_excluir'),
    path('servicos/<int:pk>/status/', views.servico_alterar_status, name='servico_alterar_status'),
    path('servicos/<int:pk>/imagens/', views.servico_imagens, name='servico_imagens'),
    path('servicos/<int:pk>/areas/', views.servico_areas, name='servico_areas'),
    path('servicos/<int:pk>/caracteristicas/', views.servico_caracteristicas, name='servico_caracteristicas'),
    path('servicos/<int:pk>/preview/', views.servico_preview, name='servico_preview'),
    path('produtos/', views.produtos_lista, name='produtos_lista'),
    path('vagas/', views.vagas_lista, name='vagas_lista'),
    path('curriculo/', views.curriculo, name='curriculo'),
    path('eventos/', views.eventos_lista, name='eventos_lista'),
    path('rede-social/', views.rede_social, name='rede_social'),
    path('mensagens/', views.mensagens, name='mensagens'),
    path('configuracoes/', views.configuracoes, name='configuracoes'),
]
