"""Administração de localidades."""

from django.contrib import admin

from apps.locations.models import Bairro, Cidade, Estado, Pais


@admin.register(Pais)
class PaisAdmin(admin.ModelAdmin):
    list_display = ('nome', 'codigo_iso_2', 'codigo_iso_3', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'nome_oficial', 'codigo_iso_2', 'codigo_iso_3')
    ordering = ('nome',)
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')


@admin.register(Estado)
class EstadoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'sigla', 'pais', 'ativo')
    list_filter = ('ativo', 'pais')
    search_fields = ('nome', 'sigla', 'codigo_ibge', 'pais__nome')
    ordering = ('pais__nome', 'nome')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')


@admin.register(Cidade)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'estado', 'codigo_ibge', 'ativo')
    list_filter = ('ativo', 'estado__pais', 'estado')
    search_fields = ('nome', 'codigo_ibge', 'estado__nome', 'estado__sigla')
    ordering = ('estado__sigla', 'nome')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')


@admin.register(Bairro)
class BairroAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cidade', 'ativo')
    list_filter = ('ativo', 'cidade__estado', 'cidade')
    search_fields = ('nome', 'cidade__nome', 'cidade__estado__sigla')
    ordering = ('cidade__nome', 'nome')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')
