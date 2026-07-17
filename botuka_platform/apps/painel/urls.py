"""URLs da área interna do usuário."""

from django.urls import path

from apps.painel import views

app_name = 'painel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('perfil/', views.perfil, name='perfil'),
    # --- Empresas ---
    path('empresas/', views.empresas_lista, name='empresas_lista'),
    path('empresas/nova/', views.empresa_criar, name='empresa_criar'),
    path('empresas/adicionar/', views.empresa_adicionar, name='empresa_adicionar'),
    path('empresas/ajax/consultar-cnpj/', views.empresa_ajax_consultar_cnpj, name='empresa_ajax_consultar_cnpj'),
    path('empresas/solicitacoes/', views.empresa_solicitacoes_lista, name='empresa_solicitacoes_lista'),
    path('empresas/solicitacoes/<int:pk>/analisar/', views.empresa_solicitacao_analisar, name='empresa_solicitacao_analisar'),
    # Preferir UUID se disponível, mantendo pk apenas se dependência forte (ver instruções)
    path('empresas/<uuid:uuid>/', views.empresa_detalhe, name='empresa_detalhe'),
    path('empresas/<uuid:uuid>/editar/', views.empresa_editar, name='empresa_editar'),
    path('empresas/<uuid:uuid>/equipe/', views.empresa_equipe, name='empresa_equipe'),
    path('empresas/<uuid:uuid>/links/', views.empresa_links, name='empresa_links'),
    path('empresas/<uuid:uuid>/qrcode/', views.empresa_qrcode, name='empresa_qrcode'),
    path('empresas/<uuid:uuid>/capacidades/', views.empresa_capacidades, name='empresa_capacidades'),
    path('empresas/<uuid:uuid>/documentos/', views.empresa_documentos, name='empresa_documentos'),
    path('empresas/<uuid:uuid>/enderecos/', views.empresa_enderecos, name='empresa_enderecos'),
    path('empresas/<uuid:uuid>/solicitacoes/', views.empresa_solicitacoes, name='empresa_solicitacoes'),
    path('empresas/<uuid:uuid>/status/', views.empresa_alterar_status, name='empresa_alterar_status'),
    path('empresas/<uuid:uuid>/excluir/', views.empresa_excluir, name='empresa_excluir'),
    # --- Publicações e outros módulos padrão ---
    path('publicacoes/', views.publicacoes_lista, name='publicacoes_lista'),
    # --- Serviços (UUID padrão: todas as rotas dependentes de serviço) ---
    path('servicos/', views.servicos_lista, name='servicos_lista'),
    path('servicos/novo/', views.servico_criar, name='servico_criar'),
    path('servicos/ajax/profissoes/', views.servicos_ajax_profissoes, name='servicos_ajax_profissoes'),
    path('servicos/<uuid:uuid>/', views.servico_detalhe, name='servico_detalhe'),
    path('servicos/<uuid:uuid>/editar/', views.servico_editar, name='servico_editar'),
    path('servicos/<uuid:uuid>/excluir/', views.servico_excluir, name='servico_excluir'),
    path('servicos/<uuid:uuid>/status/', views.servico_alterar_status, name='servico_alterar_status'),
    path('servicos/<uuid:uuid>/imagens/', views.servico_imagens, name='servico_imagens'),
    path('servicos/<uuid:uuid>/areas/', views.servico_areas, name='servico_areas'),
    path('servicos/<uuid:uuid>/caracteristicas/', views.servico_caracteristicas, name='servico_caracteristicas'),
    path('servicos/<uuid:uuid>/links/', views.servico_links, name='servico_links'),
    path('servicos/<uuid:uuid>/qrcode/', views.servico_qrcode, name='servico_qrcode'),
    path('servicos/<uuid:uuid>/preview/', views.servico_preview, name='servico_preview'),
    # --- Produtos, Vagas, Currículo, etc ---
    path('produtos/', views.produtos_lista, name='produtos_lista'),
    path('vagas/', views.vagas_lista, name='vagas_lista'),
    path('curriculo/', views.curriculo, name='curriculo'),
    path('eventos/', views.eventos_lista, name='eventos_lista'),
    path('rede-social/', views.rede_social, name='rede_social'),
    path('mensagens/', views.mensagens, name='mensagens'),
    path('configuracoes/', views.configuracoes, name='configuracoes'),
]
