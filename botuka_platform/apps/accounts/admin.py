"""Administração de contas de usuário."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.models import Usuario, UsuarioGrupo, UsuarioPermissao


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'perfil',
        'is_active',
        'is_staff',
        'ultimo_acesso',
    )
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'perfil', 'criado_em')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'telefone', 'celular')
    ordering = ('first_name', 'last_name', 'username')
    filter_horizontal = ()
    readonly_fields = (
        'uuid',
        'last_login',
        'date_joined',
        'criado_em',
        'atualizado_em',
    )
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (
            'Informações pessoais',
            {'fields': ('first_name', 'last_name', 'email')},
        ),
        (
            'Permissões',
            {'fields': ('perfil', 'is_active', 'is_staff', 'is_superuser')},
        ),
        ('Datas importantes', {'fields': ('last_login', 'date_joined')}),
        (
            'Dados BOTUKA',
            {
                'fields': (
                    'uuid',
                    'telefone',
                    'celular',
                    'foto',
                    'ultimo_acesso',
                    'criado_em',
                    'atualizado_em',
                ),
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            'Dados BOTUKA',
            {
                'fields': (
                    'email',
                    'telefone',
                    'celular',
                    'foto',
                    'perfil',
                    'is_active',
                ),
            },
        ),
    )


@admin.register(UsuarioGrupo)
class UsuarioGrupoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'grupo', 'criado_em')
    list_filter = ('grupo', 'criado_em')
    search_fields = ('usuario__username', 'usuario__email', 'grupo__name')
    ordering = ('usuario__username', 'grupo__name')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em')


@admin.register(UsuarioPermissao)
class UsuarioPermissaoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'permissao', 'criado_em')
    list_filter = ('permissao__content_type', 'criado_em')
    search_fields = (
        'usuario__username',
        'usuario__email',
        'permissao__codename',
        'permissao__name',
    )
    ordering = ('usuario__username', 'permissao__codename')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em')
