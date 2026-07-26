"""URLs do painel de gestão."""

from django.urls import path

from apps.gestao import views

app_name = 'gestao'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('usuarios/', views.UsuarioListView.as_view(), name='usuarios_lista'),
    path('usuarios/novo/', views.UsuarioCreateView.as_view(), name='usuarios_novo'),
    path('usuarios/<int:pk>/', views.UsuarioDetailView.as_view(), name='usuarios_detalhe'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuarios_editar'),
    path('usuarios/<int:pk>/ativar/', views.usuario_ativar, name='usuarios_ativar'),
    path('usuarios/<int:pk>/desativar/', views.usuario_desativar, name='usuarios_desativar'),
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

for slug in views.CRUD_CONFIGS:
    urlpatterns += [
        path(f'{slug}/', views.build_list_view(slug), name=f'{slug}_lista'),
        path(f'{slug}/novo/', views.build_create_view(slug), name=f'{slug}_novo'),
        path(f'{slug}/<int:pk>/editar/', views.build_update_view(slug), name=f'{slug}_editar'),
    ]
