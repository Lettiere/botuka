"""Administração de contas de usuário."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied

from apps.accounts.models import Usuario, UsuarioGrupo, UsuarioPermissao
from apps.accounts.permissions import usuario_e_master

GLOBAL_PROFILE_NAMES = ('MASTER', 'ADMIN_GLOBAL', 'SUPORTE_GLOBAL', 'AUDITOR_GLOBAL')


class MasterOnlyAdminMixin:
    def has_module_permission(self, request):
        return usuario_e_master(request.user)

    def has_view_permission(self, request, obj=None):
        return usuario_e_master(request.user)

    def has_add_permission(self, request):
        return usuario_e_master(request.user)

    def has_change_permission(self, request, obj=None):
        return usuario_e_master(request.user)

    def has_delete_permission(self, request, obj=None):
        return usuario_e_master(request.user)


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

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj)
        if obj is not None and usuario_e_master(obj) and not usuario_e_master(request.user):
            return False
        return allowed

    def has_delete_permission(self, request, obj=None):
        allowed = super().has_delete_permission(request, obj)
        if obj is not None and usuario_e_master(obj) and not usuario_e_master(request.user):
            return False
        return allowed

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'perfil' and not usuario_e_master(request.user):
            kwargs['queryset'] = db_field.remote_field.model.objects.exclude(nome__in=GLOBAL_PROFILE_NAMES)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        perfil_global = obj.perfil and obj.perfil.nome.upper() in GLOBAL_PROFILE_NAMES
        if (perfil_global or obj.is_superuser) and not usuario_e_master(request.user):
            raise PermissionDenied('Apenas MASTER pode conceder autoridade global.')
        super().save_model(request, obj, form, change)


@admin.register(UsuarioGrupo)
class UsuarioGrupoAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('usuario', 'grupo', 'criado_em')
    list_filter = ('grupo', 'criado_em')
    search_fields = ('usuario__username', 'usuario__email', 'grupo__name')
    ordering = ('usuario__username', 'grupo__name')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em')


@admin.register(UsuarioPermissao)
class UsuarioPermissaoAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
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
