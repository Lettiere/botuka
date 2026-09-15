"""URLs do painel de gestão."""

from django.urls import include, path

from apps.gestao import views
from apps.gestao import (
    analytics_views,
    business_taxonomy_views,
    central_views,
    company_views,
    location_views,
    advertising_views,
)
from apps.products import taxonomy_views

app_name = 'gestao'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path(
        'publicidade/configuracoes/',
        advertising_views.configuracao_comercial,
        name='publicidade_configuracao',
    ),
    path(
        'publicidade/planos/novo/',
        advertising_views.plano_form,
        name='publicidade_plano_novo',
    ),
    path(
        'publicidade/planos/<int:pk>/editar/',
        advertising_views.plano_form,
        name='publicidade_plano_editar',
    ),
    path(
        'publicidade/posicionamentos/novo/',
        advertising_views.posicionamento_form,
        name='publicidade_posicionamento_novo',
    ),
    path(
        'publicidade/posicionamentos/<int:pk>/editar/',
        advertising_views.posicionamento_form,
        name='publicidade_posicionamento_editar',
    ),
    path(
        'publicidade/campanhas/',
        advertising_views.campanha_lista,
        name='publicidade_campanhas',
    ),
    path(
        'publicidade/campanhas/<uuid:uuid>/',
        advertising_views.campanha_detalhe,
        name='publicidade_campanha_detalhe',
    ),
    path(
        'publicidade/campanhas/<uuid:uuid>/aprovar/',
        advertising_views.campanha_aprovar,
        name='publicidade_campanha_aprovar',
    ),
    path(
        'publicidade/campanhas/<uuid:uuid>/moderar/<str:acao>/',
        advertising_views.campanha_moderar,
        name='publicidade_campanha_moderar',
    ),
    path('analytics/ga4/', analytics_views.ga4_dashboard, name='analytics_ga4'),
    path('empresas/', company_views.empresa_lista, name='empresas_lista'),
    path('empresas/nova/', company_views.empresa_form, name='empresa_nova'),
    path('empresas/configuracoes/<str:kind>/', company_views.catalogo_lista, name='empresa_catalogo_lista'),
    path('empresas/configuracoes/<str:kind>/nova/', company_views.catalogo_form, name='empresa_catalogo_novo'),
    path('empresas/configuracoes/<str:kind>/<int:pk>/', company_views.catalogo_detalhe, name='empresa_catalogo_detalhe'),
    path('empresas/configuracoes/<str:kind>/<int:pk>/editar/', company_views.catalogo_form, name='empresa_catalogo_editar'),
    path('empresas/configuracoes/<str:kind>/<int:pk>/status/', company_views.catalogo_status, name='empresa_catalogo_status'),
    path('empresas/solicitacoes/', company_views.solicitacao_lista, name='solicitacoes_lista'),
    path('empresas/solicitacoes/<int:pk>/', company_views.solicitacao_analisar, name='solicitacao_analisar'),
    path('empresas/<uuid:uuid>/', company_views.empresa_detalhe, name='empresa_detalhe'),
    path('empresas/<uuid:uuid>/editar/', company_views.empresa_form, name='empresa_editar'),
    path('empresas/<uuid:uuid>/inativar/', company_views.empresa_inativar, name='empresa_inativar'),
    path('empresas/<uuid:uuid>/reativar/', company_views.empresa_reativar, name='empresa_reativar'),
    path('empresas/<uuid:empresa_uuid>/vinculos/novo/', company_views.empresa_vinculo_form, name='empresa_vinculo_novo'),
    path('empresas/<uuid:empresa_uuid>/vinculos/<int:pk>/', company_views.empresa_vinculo_form, name='empresa_vinculo_editar'),
    path('empresas/<uuid:empresa_uuid>/vinculos/<int:pk>/inativar/', company_views.empresa_vinculo_inativar, name='empresa_vinculo_inativar'),
    path('empresas/<uuid:empresa_uuid>/vinculos/<int:pk>/reativar/', company_views.empresa_vinculo_reativar, name='empresa_vinculo_reativar'),
    path('empresas/<uuid:empresa_uuid>/capacidades/<int:pk>/', company_views.capacidade_editar, name='empresa_capacidade_editar'),
    path('comunicacao/', include('apps.comunicacao.urls')),
    path('taxonomias/produtos/', taxonomy_views.dashboard, name='taxonomia_produtos_dashboard'),
    path('taxonomia-empresarial/<str:kind>/', business_taxonomy_views.lista, name='taxonomia_empresarial_lista'),
    path('taxonomia-empresarial/<str:kind>/novo/', business_taxonomy_views.formulario, name='taxonomia_empresarial_novo'),
    path('taxonomia-empresarial/<str:kind>/<int:pk>/', business_taxonomy_views.detalhe, name='taxonomia_empresarial_detalhe'),
    path('taxonomia-empresarial/<str:kind>/<int:pk>/editar/', business_taxonomy_views.formulario, name='taxonomia_empresarial_editar'),
    path('taxonomia-empresarial/<str:kind>/<int:pk>/status/', business_taxonomy_views.status, name='taxonomia_empresarial_status'),
    path('central/<str:kind>/', central_views.lista, name='central_lista'),
    path('central/<str:kind>/<int:pk>/', central_views.detalhe, name='central_detalhe'),
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
    path('usuarios/<int:pk>/papel-global/', views.usuario_papel_global, name='usuario_papel_global'),
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
    path('acessos/<str:kind>/<int:pk>/', views.controle_detalhe, name='controle_detalhe'),
    path('acessos/<str:kind>/<int:pk>/status/', views.controle_status, name='controle_status'),
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

for category_kind in business_taxonomy_views.CATEGORY_CONFIG:
    urlpatterns += [
        path(f'{category_kind}/', business_taxonomy_views.categoria_lista, {'kind': category_kind}, name=f'{category_kind}_lista'),
        path(f'{category_kind}/novo/', business_taxonomy_views.categoria_form, {'kind': category_kind}, name=f'{category_kind}_novo'),
        path(f'{category_kind}/<int:pk>/', business_taxonomy_views.categoria_detalhe, {'kind': category_kind}, name=f'{category_kind}_detalhe'),
        path(f'{category_kind}/<int:pk>/editar/', business_taxonomy_views.categoria_form, {'kind': category_kind}, name=f'{category_kind}_editar'),
        path(f'{category_kind}/<int:pk>/status/', business_taxonomy_views.categoria_status, {'kind': category_kind}, name=f'{category_kind}_status'),
    ]

for location_kind in location_views.CONFIG:
    urlpatterns += [
        path(f'{location_kind}/', location_views.lista, {'kind': location_kind}, name=f'{location_kind}_lista'),
        path(f'{location_kind}/novo/', location_views.formulario, {'kind': location_kind}, name=f'{location_kind}_novo'),
        path(f'{location_kind}/<int:pk>/', location_views.detalhe, {'kind': location_kind}, name=f'{location_kind}_detalhe'),
        path(f'{location_kind}/<int:pk>/editar/', location_views.formulario, {'kind': location_kind}, name=f'{location_kind}_editar'),
        path(f'{location_kind}/<int:pk>/status/', location_views.status, {'kind': location_kind}, name=f'{location_kind}_status'),
    ]

for slug in views.CRUD_CONFIGS:
    if slug in business_taxonomy_views.CATEGORY_CONFIG or slug in location_views.CONFIG:
        continue
    urlpatterns += [
        path(f'{slug}/', views.build_list_view(slug), name=f'{slug}_lista'),
        path(f'{slug}/novo/', views.build_create_view(slug), name=f'{slug}_novo'),
        path(f'{slug}/<int:pk>/editar/', views.build_update_view(slug), name=f'{slug}_editar'),
    ]
    if slug in {'organizacoes', 'unidades', 'enderecos', 'categorias', 'subcategorias', 'paises', 'estados', 'cidades', 'bairros'}:
        urlpatterns += [
            path(f'{slug}/<int:pk>/', views.build_detail_view(slug), name=f'{slug}_detalhe'),
            path(f'{slug}/<int:pk>/status/', views.crud_status, {'slug': slug}, name=f'{slug}_status'),
        ]
