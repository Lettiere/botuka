"""Administração dos modelos centrais."""

from django.contrib import admin
from apps.accounts.permissions import usuario_e_master, usuario_tem_permissao

from apps.core.models import (
    Auditoria,
    BairroCidade,
    CidadeBrasil,
    CNHDetalhe,
    ConfiguracaoSistema,
    ContatoInstitucional,
    DocumentoRequisito,
    EnderecoCore,
    EstadoBrasil,
    Perfil,
    PerfilPermissao,
    Permissao,
    PessoaDocumento,
    RegiaoCidade,
    TipoDocumento,
    UsuarioEndereco,
    ZonaCidade,
)


class MasterOnlyAdminMixin:
    """Restringe configurações e RBAC globais ao MASTER."""

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


@admin.register(ConfiguracaoSistema)
class ConfiguracaoSistemaAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('chave', 'ativo', 'criado_em', 'atualizado_em')
    list_filter = ('ativo', 'criado_em', 'atualizado_em')
    search_fields = ('chave', 'valor', 'descricao')
    ordering = ('chave',)
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')


@admin.register(ContatoInstitucional)
class ContatoInstitucionalAdmin(admin.ModelAdmin):
    list_display = (
        'nome',
        'tipo',
        'valor',
        'ativo',
        'exibir_topbar',
        'exibir_rodape',
        'ordem',
    )
    list_filter = ('tipo', 'ativo', 'exibir_topbar', 'exibir_rodape')
    search_fields = ('nome', 'valor', 'url')
    ordering = ('ordem', 'nome')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em')


@admin.register(Perfil)
class PerfilAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('nome', 'ativo', 'criado_em', 'atualizado_em')
    list_filter = ('ativo', 'criado_em', 'atualizado_em')
    search_fields = ('nome', 'descricao')
    ordering = ('nome',)
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')


@admin.register(Permissao)
class PermissaoAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'ativo', 'criado_em', 'atualizado_em')
    list_filter = ('ativo', 'criado_em', 'atualizado_em')
    search_fields = ('codigo', 'nome', 'descricao')
    ordering = ('codigo',)
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')


@admin.register(PerfilPermissao)
class PerfilPermissaoAdmin(MasterOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('perfil', 'permissao', 'ativo', 'criado_em')
    list_filter = ('ativo', 'perfil', 'permissao', 'criado_em')
    search_fields = ('perfil__nome', 'permissao__codigo', 'permissao__nome')
    ordering = ('perfil__nome', 'permissao__codigo')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')


@admin.register(EstadoBrasil)
class EstadoBrasilAdmin(admin.ModelAdmin):
    list_display = ('nome', 'sigla', 'codigo_ibge', 'regiao_brasileira', 'ativo')
    list_filter = ('regiao_brasileira', 'ativo')
    search_fields = ('nome', 'sigla', 'codigo_ibge')


@admin.register(CidadeBrasil)
class CidadeBrasilAdmin(admin.ModelAdmin):
    list_display = ('nome', 'estado', 'codigo_ibge', 'capital', 'ativo')
    list_filter = ('ativo', 'capital', 'estado')
    search_fields = ('nome', 'codigo_ibge', 'estado__sigla')
    autocomplete_fields = ('estado',)


@admin.register(RegiaoCidade)
class RegiaoCidadeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cidade', 'tipo', 'ativo')
    list_filter = ('tipo', 'ativo')
    search_fields = ('nome', 'cidade__nome')
    autocomplete_fields = ('cidade',)


@admin.register(ZonaCidade)
class ZonaCidadeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cidade', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'cidade__nome')
    autocomplete_fields = ('cidade',)


@admin.register(BairroCidade)
class BairroCidadeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cidade', 'zona', 'ativo')
    list_filter = ('ativo', 'cidade__estado')
    search_fields = ('nome', 'cidade__nome')
    autocomplete_fields = ('cidade', 'zona')


@admin.register(EnderecoCore)
class EnderecoCoreAdmin(admin.ModelAdmin):
    list_display = ('logradouro', 'numero', 'cidade', 'estado', 'tipo_endereco', 'principal', 'ativo')
    list_filter = ('tipo_endereco', 'principal', 'validado', 'ativo')
    search_fields = ('logradouro', 'cep', 'bairro_texto', 'cidade__nome')
    autocomplete_fields = ('bairro', 'cidade', 'estado')


@admin.register(UsuarioEndereco)
class UsuarioEnderecoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'endereco', 'principal', 'ativo', 'criado_em')
    list_filter = ('principal', 'ativo')
    search_fields = ('usuario__username', 'usuario__email', 'endereco__logradouro')
    autocomplete_fields = ('usuario', 'endereco')


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'pessoa_fisica', 'pessoa_juridica', 'sensivel', 'ativo')
    list_filter = ('pessoa_fisica', 'pessoa_juridica', 'sensivel', 'ativo')
    search_fields = ('codigo', 'nome')


@admin.register(PessoaDocumento)
class PessoaDocumentoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo_documento', 'numero_mascarado', 'status_validacao', 'principal', 'ativo')
    list_filter = ('status_validacao', 'principal', 'ativo', 'tipo_documento')
    search_fields = ('usuario__username', 'usuario__email', 'tipo_documento__codigo')
    autocomplete_fields = ('usuario', 'tipo_documento', 'validado_por')
    readonly_fields = ('uuid', 'numero_mascarado', 'criado_em', 'atualizado_em', 'excluido_em')


@admin.register(DocumentoRequisito)
class DocumentoRequisitoAdmin(admin.ModelAdmin):
    list_display = ('tipo_documento', 'contexto', 'modulo', 'obrigatorio', 'condicional', 'ativo')
    list_filter = ('contexto', 'modulo', 'obrigatorio', 'ativo')
    search_fields = ('tipo_documento__codigo', 'modulo')
    autocomplete_fields = ('tipo_documento',)


@admin.register(CNHDetalhe)
class CNHDetalheAdmin(admin.ModelAdmin):
    list_display = ('documento', 'categoria', 'possui_ear', 'validade', 'ativo')
    list_filter = ('categoria', 'possui_ear', 'ativo')
    search_fields = ('documento__usuario__username',)
    autocomplete_fields = ('documento',)


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('acao', 'entidade', 'registro_id', 'usuario', 'criado_em')
    list_filter = ('acao', 'entidade', 'criado_em')
    search_fields = ('acao', 'entidade', 'registro_id', 'usuario__username')
    autocomplete_fields = ('usuario',)
    readonly_fields = (
        'uuid', 'usuario', 'acao', 'entidade', 'registro_id',
        'dados_antes_json', 'dados_depois_json', 'motivo', 'ip',
        'user_agent', 'organizacao_uuid', 'sucesso', 'origem', 'criado_em',
    )

    def has_module_permission(self, request):
        return usuario_e_master(request.user) or usuario_tem_permissao(request.user, 'auditoria.global.visualizar')

    def has_view_permission(self, request, obj=None):
        return usuario_e_master(request.user) or usuario_tem_permissao(request.user, 'auditoria.global.visualizar')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
