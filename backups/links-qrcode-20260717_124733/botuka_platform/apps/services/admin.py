from django.contrib import admin

from apps.services.models import (
    FormaCobranca,
    Profissao,
    Servico,
    ServicoArea,
    ServicoAvaliacao,
    ServicoCaracteristica,
    ServicoFavorito,
    ServicoImagem,
    Setor,
    TipoServico,
)


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'ordem', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'slug', 'descricao')
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(Profissao)
class ProfissaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'setor', 'exige_registro_profissional', 'ativo')
    list_filter = ('ativo', 'setor')
    search_fields = ('nome', 'setor__nome')
    autocomplete_fields = ('setor',)
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(TipoServico)
class TipoServicoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'slug')
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(FormaCobranca)
class FormaCobrancaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'slug')
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'prestador_tipo', 'empresa', 'usuario_responsavel', 'setor', 'status', 'ativo')
    list_filter = ('status', 'prestador_tipo', 'ativo', 'setor')
    search_fields = ('titulo', 'descricao_curta', 'empresa__nome_fantasia', 'usuario_responsavel__username', 'usuario_responsavel__email')
    autocomplete_fields = ('usuario_responsavel', 'empresa', 'setor', 'profissao', 'tipo_servico', 'forma_cobranca')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'publicado_em', 'excluido_em')
    list_select_related = ('empresa', 'usuario_responsavel', 'setor', 'profissao')
    prepopulated_fields = {'slug': ('titulo',)}


admin.site.register(ServicoArea)
admin.site.register(ServicoImagem)
admin.site.register(ServicoCaracteristica)
admin.site.register(ServicoAvaliacao)
admin.site.register(ServicoFavorito)
