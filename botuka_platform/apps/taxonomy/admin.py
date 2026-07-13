"""Administração da taxonomia."""

from django.contrib import admin

from apps.taxonomy.models import Categoria, Subcategoria


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'ordem', 'ativo')
    list_filter = ('ativo', 'criado_em', 'atualizado_em')
    search_fields = ('nome', 'slug', 'descricao')
    ordering = ('ordem', 'nome')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(Subcategoria)
class SubcategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'categoria', 'slug', 'ordem', 'ativo')
    list_filter = ('ativo', 'categoria', 'criado_em', 'atualizado_em')
    search_fields = ('nome', 'slug', 'descricao', 'categoria__nome')
    ordering = ('categoria__nome', 'ordem', 'nome')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em', 'removido_em')
    prepopulated_fields = {'slug': ('nome',)}
