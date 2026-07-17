"""Administração de organizações."""

from django.contrib import admin

from apps.organizations.models import (
    Capacidade,
    CNAE,
    CNPJConsulta,
    Endereco,
    Empresa,
    EmpresaCapacidade,
    EmpresaCNAE,
    EmpresaEndereco,
    EmpresaFuncao,
    EmpresaPropriedade,
    EmpresaSolicitacao,
    EmpresaUsuario,
    EmpresaUsuarioFuncao,
    EmpresaUsuarioPermissao,
    Organizacao,
    OrganizacaoUsuario,
    Unidade,
    UsuarioCapacidade,
)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = (
        'nome_fantasia',
        'tipo_cadastro',
        'cpf_cnpj',
        'cidade',
        'estado',
        'status',
        'usuario_proprietario',
        'ativo',
        'verificada',
    )
    list_filter = (
        'status',
        'tipo_cadastro',
        'ativo',
        'verificada',
        'perfil_publico',
        'estado',
        'cidade',
    )
    search_fields = (
        'nome_fantasia',
        'razao_social',
        'cpf_cnpj',
        'email',
        'usuario_proprietario__username',
        'usuario_proprietario__email',
    )
    autocomplete_fields = (
        'usuario_proprietario',
        'categoria_empresa',
        'estado',
        'cidade',
    )
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'excluido_em')
    list_select_related = (
        'usuario_proprietario',
        'categoria_empresa',
        'cidade',
        'estado',
    )
    ordering = ('nome_fantasia',)
    prepopulated_fields = {'slug': ('nome_fantasia',)}


@admin.register(EmpresaUsuario)
class EmpresaUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        'empresa',
        'usuario',
        'funcao',
        'proprietario',
        'administrador',
        'ativo',
    )
    list_filter = (
        'funcao',
        'proprietario',
        'administrador',
        'ativo',
        'pode_editar',
        'pode_publicar_servico',
        'pode_gerenciar_equipe',
    )
    search_fields = (
        'empresa__nome_fantasia',
        'empresa__cpf_cnpj',
        'usuario__username',
        'usuario__email',
    )
    autocomplete_fields = ('empresa', 'usuario')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em')
    list_select_related = ('empresa', 'usuario')
    ordering = ('empresa__nome_fantasia', 'usuario__username')


@admin.register(Capacidade)
class CapacidadeAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'exige_aprovacao', 'ativo')
    list_filter = ('exige_aprovacao', 'ativo')
    search_fields = ('codigo', 'nome')


@admin.register(UsuarioCapacidade)
class UsuarioCapacidadeAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'capacidade', 'status', 'ativo')
    list_filter = ('status', 'ativo', 'capacidade')
    search_fields = ('usuario__username', 'usuario__email', 'capacidade__codigo')
    autocomplete_fields = ('usuario', 'capacidade', 'aprovado_por')


@admin.register(EmpresaCapacidade)
class EmpresaCapacidadeAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'capacidade', 'status', 'ativo')
    list_filter = ('status', 'ativo', 'capacidade')
    search_fields = ('empresa__nome_fantasia', 'capacidade__codigo')
    autocomplete_fields = ('empresa', 'capacidade', 'aprovado_por')


@admin.register(EmpresaEndereco)
class EmpresaEnderecoAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'endereco', 'principal', 'publico', 'ativo')
    list_filter = ('principal', 'publico', 'ativo')
    search_fields = ('empresa__nome_fantasia', 'endereco__logradouro')
    autocomplete_fields = ('empresa', 'endereco')


@admin.register(EmpresaPropriedade)
class EmpresaPropriedadeAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'usuario', 'atual', 'origem', 'inicio_em', 'fim_em')
    list_filter = ('atual', 'origem')
    search_fields = ('empresa__nome_fantasia', 'usuario__username', 'usuario__email')
    autocomplete_fields = ('empresa', 'usuario', 'aprovado_por')


@admin.register(EmpresaFuncao)
class EmpresaFuncaoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('codigo', 'nome')


admin.site.register(EmpresaUsuarioFuncao)
admin.site.register(EmpresaUsuarioPermissao)


@admin.register(CNAE)
class CNAEAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descricao', 'ativo')
    list_filter = ('ativo', 'secao', 'divisao')
    search_fields = ('codigo', 'descricao')


@admin.register(EmpresaCNAE)
class EmpresaCNAEAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'cnae', 'principal', 'origem', 'ativo')
    list_filter = ('principal', 'origem', 'ativo')
    search_fields = ('empresa__nome_fantasia', 'cnae__codigo')
    autocomplete_fields = ('empresa', 'cnae')


@admin.register(CNPJConsulta)
class CNPJConsultaAdmin(admin.ModelAdmin):
    list_display = ('cnpj', 'provider', 'sucesso', 'codigo_resposta', 'consultado_em', 'expira_em')
    list_filter = ('provider', 'sucesso', 'consultado_em')
    search_fields = ('cnpj', 'erro_resumido')
    autocomplete_fields = ('solicitado_por',)
    readonly_fields = ('resposta_json',)


@admin.register(EmpresaSolicitacao)
class EmpresaSolicitacaoAdmin(admin.ModelAdmin):
    list_display = ('tipo_solicitacao', 'empresa', 'cnpj', 'usuario_solicitante', 'status', 'criado_em')
    list_filter = ('tipo_solicitacao', 'status', 'criado_em')
    search_fields = ('cnpj', 'empresa__nome_fantasia', 'usuario_solicitante__username')
    autocomplete_fields = ('empresa', 'usuario_solicitante', 'analisado_por')


@admin.register(Organizacao)
class OrganizacaoAdmin(admin.ModelAdmin):
    list_display = (
        'nome_fantasia',
        'documento',
        'categoria',
        'proprietario',
        'ativo',
    )
    list_filter = ('ativo', 'categoria', 'criado_em', 'atualizado_em')
    search_fields = (
        'nome_fantasia',
        'razao_social',
        'documento',
        'email',
        'proprietario__username',
        'proprietario__email',
    )
    ordering = ('nome_fantasia',)
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')
    prepopulated_fields = {'slug': ('nome_fantasia',)}


@admin.register(OrganizacaoUsuario)
class OrganizacaoUsuarioAdmin(admin.ModelAdmin):
    list_display = ('organizacao', 'usuario', 'ativo', 'criado_em')
    list_filter = ('ativo', 'organizacao', 'criado_em')
    search_fields = (
        'organizacao__nome_fantasia',
        'usuario__username',
        'usuario__email',
    )
    ordering = ('organizacao__nome_fantasia', 'usuario__username')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = (
        'nome',
        'organizacao',
        'categoria',
        'responsavel',
        'principal',
        'ativo',
    )
    list_filter = ('ativo', 'principal', 'categoria', 'criado_em')
    search_fields = (
        'nome',
        'email',
        'telefone',
        'organizacao__nome_fantasia',
        'responsavel__username',
        'responsavel__email',
    )
    ordering = ('organizacao__nome_fantasia', 'nome')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(Endereco)
class EnderecoAdmin(admin.ModelAdmin):
    list_display = ('unidade', 'cidade', 'bairro', 'logradouro', 'numero', 'ativo')
    list_filter = ('ativo', 'cidade__estado', 'cidade', 'bairro')
    search_fields = (
        'logradouro',
        'numero',
        'complemento',
        'cep',
        'unidade__nome',
        'unidade__organizacao__nome_fantasia',
        'cidade__nome',
        'bairro__nome',
    )
    ordering = ('cidade__nome', 'logradouro', 'numero')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')
