from django.urls import path

from . import views

urlpatterns = [
    path('turismo/', views.dashboard, name='turismo_dashboard'),

    # Nomes públicos estáveis usados pela navegação e integrações existentes.
    path('turismo/locais/novo/', views.local_novo, name='turismo_local_novo'),
    path('turismo/locais/<uuid:uuid>/etapa/<int:etapa>/', views.local_etapa, name='turismo_local_etapa'),
    path('turismo/locais/<uuid:uuid>/geocodificar/', views.local_geocodificar, name='turismo_local_geocodificar'),
    path('turismo/guias/novo/', views.guia_novo, name='turismo_guia_novo'),
    path('turismo/empresas/nova/', views.entidade_nova, {'entidade': 'empresas'}, name='turismo_empresa_nova'),
    path('turismo/videos/novo/', views.video_novo, name='turismo_video_novo'),
    path('turismo/playlists/nova/', views.playlist_nova, name='turismo_playlist_nova'),
    path('turismo/roteiros/novo/', views.entidade_nova, {'entidade': 'roteiros'}, name='turismo_roteiro_novo'),
    path('turismo/experiencias/nova/', views.entidade_nova, {'entidade': 'experiencias'}, name='turismo_experiencia_nova'),

    path('turismo/locais/<uuid:uuid>/fotos/', views.local_fotos, name='turismo_local_fotos'),
    path('turismo/locais/<uuid:uuid>/imagens/', views.local_etapa, {'etapa': 6}, name='turismo_local_imagens'),
    path('turismo/locais/<uuid:uuid>/imagens/nova/', views.local_etapa, {'etapa': 6}, name='turismo_local_imagem_nova'),
    path('turismo/locais/<uuid:uuid>/imagens/<uuid:imagem_uuid>/editar/', views.local_imagem_editar, name='turismo_local_imagem_editar'),
    path('turismo/locais/<uuid:uuid>/imagens/<uuid:imagem_uuid>/remover/', views.local_imagem_remover, name='turismo_local_imagem_remover'),
    path('turismo/locais/<uuid:uuid>/itens/<str:tipo>/<uuid:item_uuid>/remover/', views.local_item_remover, name='turismo_local_item_remover'),
    path('turismo/locais/<uuid:uuid>/videos/', views.local_relacionados, {'tipo': 'videos'}, name='turismo_local_videos'),
    path('turismo/locais/<uuid:uuid>/videos/novo/', views.local_etapa, {'etapa': 7}, name='turismo_local_video_novo'),
    path('turismo/locais/<uuid:uuid>/playlists/', views.local_relacionados, {'tipo': 'playlists'}, name='turismo_local_playlists'),
    path('turismo/locais/<uuid:uuid>/playlists/nova/', views.local_etapa, {'etapa': 7}, name='turismo_local_playlist_nova'),
    path('turismo/locais/<uuid:uuid>/publicar/', views.acao_status, {'entidade': 'locais', 'status': 'PUBLICADO'}, name='turismo_local_publicar'),
    path('turismo/locais/<uuid:uuid>/pausar/', views.acao_status, {'entidade': 'locais', 'status': 'PAUSADO'}, name='turismo_local_pausar'),
    path('turismo/guias/<uuid:uuid>/validar/', views.acao_status, {'entidade': 'guias', 'status': 'PUBLICADO'}, name='turismo_guia_validar'),
    path('turismo/guias/<uuid:uuid>/publicar/', views.acao_status, {'entidade': 'guias', 'status': 'PUBLICADO'}, name='turismo_guia_publicar'),
    path('turismo/guias/<uuid:uuid>/pausar/', views.acao_status, {'entidade': 'guias', 'status': 'PAUSADO'}, name='turismo_guia_pausar'),
    path('turismo/playlists/<uuid:uuid>/videos/', views.playlist_videos, name='turismo_playlist_videos'),

    path('turismo/<str:entidade>/', views.entidade_lista, name='turismo_entidade_lista'),
    path('turismo/<str:entidade>/<uuid:uuid>/', views.entidade_detalhe, name='turismo_entidade_detalhe'),
    path('turismo/<str:entidade>/<uuid:uuid>/editar/', views.entidade_editar, name='turismo_entidade_editar'),
    path('turismo/<str:entidade>/<uuid:uuid>/remover/', views.entidade_remover, name='turismo_entidade_remover'),
    path('turismo/<str:entidade>/<uuid:uuid>/status/', views.entidade_status, name='turismo_entidade_status'),

    # Compatibilidade retroativa.
    path('turismo/locais/<uuid:uuid>/editar/', views.local_editar, name='turismo_local_editar'),
    path('turismo/locais/<uuid:uuid>/status/', views.local_status, name='turismo_local_status'),
]
