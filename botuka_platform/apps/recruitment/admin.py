"""Administração de vagas, currículos e candidaturas."""

from django.contrib import admin

from apps.recruitment.models import (
    Candidatura, Curso, Curriculo, CurriculoInformacaoAdicional,
    CurriculoPrivacidade, Experiencia, Formacao, Habilidade, Idioma, Projeto,
    Vaga,
)


@admin.register(Vaga)
class VagaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'empresa', 'status', 'modalidade', 'publicado_em', 'encerramento')
    list_filter = ('status', 'modalidade', 'tipo_contrato', 'aceita_pcd')
    search_fields = ('titulo', 'empresa__nome_fantasia', 'cidade', 'bairro')
    autocomplete_fields = ('empresa', 'usuario_responsavel')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'publicado_em', 'excluido_em')


@admin.register(Curriculo)
class CurriculoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'titulo_profissional', 'status', 'visibilidade', 'etapa_atual', 'ativo')
    list_filter = ('status', 'visibilidade', 'ativo')
    search_fields = ('usuario__username', 'usuario__email', 'titulo_profissional', 'area_profissional')
    autocomplete_fields = ('usuario',)
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'excluido_em')


@admin.register(Candidatura)
class CandidaturaAdmin(admin.ModelAdmin):
    list_display = ('vaga', 'usuario', 'status', 'criado_em')
    list_filter = ('status', 'criado_em')
    search_fields = ('vaga__titulo', 'usuario__username', 'usuario__email')
    autocomplete_fields = ('vaga', 'usuario', 'curriculo')
    readonly_fields = ('uuid', 'curriculo_snapshot', 'consentimento_compartilhamento_em', 'criado_em', 'atualizado_em', 'excluido_em')


admin.site.register(Experiencia)
admin.site.register(Formacao)
admin.site.register(Curso)
admin.site.register(Habilidade)
admin.site.register(Idioma)
admin.site.register(Projeto)
admin.site.register(CurriculoPrivacidade)
admin.site.register(CurriculoInformacaoAdicional)
