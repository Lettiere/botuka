"""URLs do painel de gestão."""

from django.urls import include, path

from apps.gestao import views
from apps.products import taxonomy_views

app_name = 'gestao'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('comunicacao/', include('apps.comunicacao.urls')),
    path('taxonomias/produtos/', taxonomy_views.dashboard, name='taxonomia_produtos_dashboard'),
    path('taxonomias/produtos/api/setores/', taxonomy_views.api_setores, name='api_produtos_setores'),
    path('taxonomias/produtos/api/categorias/', taxonomy_views.api_categorias, name='api_produtos_categorias'),
    path('taxonomias/produtos/api/familias/', taxonomy_views.api_familias, name='api_produtos_familias'),
    path('taxonomias/produtos/api/tipos/', taxonomy_views.api_tipos, name='api_produtos_tipos'),
    path('taxonomias/produtos/api/segmentos/', taxonomy_views.api_segmentos, name='api_produtos_segmentos'),
    path('taxonomias/produtos/api/atributos/', taxonomy_views.api_atributos, name='api_produtos_atributos'),
    path('usuarios/', views.UsuarioListView.as_view(), name='usuarios_lista'),
    path('usuarios/novo/', views.UsuarioCreateView.as_view(), name='usuarios_novo'),
    path('usuarios/<int:pk>/', views.UsuarioDetailView.as_view(), name='usuarios_detalhe'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuarios_editar'),
    path('usuarios/<int:pk>/ativar/', views.usuario_ativar, name='usuarios_ativar'),
    path('usuarios/<int:pk>/desativar/', views.usuario_desativar, name='usuarios_desativar'),
    path('usuarios/<uuid:uuid>/acessos/', views.usuario_acessos, name='usuario_acessos'),
    path('usuarios/<uuid:uuid>/acessos/novo/', views.usuario_acesso_form, name='usuario_acesso_novo'),
    path('usuarios/<uuid:uuid>/acessos/<uuid:acesso_uuid>/editar/', views.usuario_acesso_form, name='usuario_acesso_editar'),
    path('usuarios/<uuid:uuid>/acessos/<uuid:acesso_uuid>/status/', views.usuario_acesso_status, name='usuario_acesso_status'),
    path('usuarios/<uuid:uuid>/permissoes/', views.usuario_permissoes, name='usuario_permissoes'),
    path('perfis/', views.PerfilListView.as_view(), name='perfis_lista'),
    path('perfis/novo/', views.PerfilCreateView.as_view(), name='perfis_novo'),
    path('perfis/<int:pk>/editar/', views.PerfilUpdateView.as_view(), name='perfis_editar'),
    path('perfis/<int:pk>/permissoes/', views.perfil_permissoes, name='perfil_permissoes'),
    path('permissoes/', views.PermissaoListView.as_view(), name='permissoes_lista'),
    path('permissoes/nova/', views.PermissaoCreateView.as_view(), name='permissoes_nova'),
    path('permissoes/<int:pk>/editar/', views.PermissaoUpdateView.as_view(), name='permissoes_editar'),
    path('contatos/<int:pk>/ativar/', views.contato_ativar, name='contatos_ativar'),
    path('contatos/<int:pk>/desativar/', views.contato_desativar, name='contatos_desativar'),
]

for kind in taxonomy_views.CONFIG:
    urlpatterns += [
        path(f'taxonomias/produtos/{kind}/', taxonomy_views.lista, {'kind': kind}, name=f'taxonomia_{kind}_lista'),
        path(f'taxonomias/produtos/{kind}/novo/', taxonomy_views.formulario, {'kind': kind}, name=f'taxonomia_{kind}_novo'),
        path(f'taxonomias/produtos/{kind}/<uuid:uuid>/', taxonomy_views.detalhe, {'kind': kind}, name=f'taxonomia_{kind}_detalhe'),
        path(f'taxonomias/produtos/{kind}/<uuid:uuid>/editar/', taxonomy_views.formulario, {'kind': kind}, name=f'taxonomia_{kind}_editar'),
        path(f'taxonomias/produtos/{kind}/<uuid:uuid>/status/', taxonomy_views.alternar_status, {'kind': kind}, name=f'taxonomia_{kind}_status'),
    ]

for slug in views.CRUD_CONFIGS:
    urlpatterns += [
        path(f'{slug}/', views.build_list_view(slug), name=f'{slug}_lista'),
        path(f'{slug}/novo/', views.build_create_view(slug), name=f'{slug}_novo'),
        path(f'{slug}/<int:pk>/editar/', views.build_update_view(slug), name=f'{slug}_editar'),
    ]
