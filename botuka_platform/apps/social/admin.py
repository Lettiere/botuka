from django.contrib import admin

from .models import (
    EmpresaSeguidor, SocialBlock, SocialConversation, SocialFollow,
    SocialFollowRequest, SocialMessage, SocialPost, SocialPostComment,
    SocialPostLike, SocialPostSave, SocialProfile, SocialStory,
)


@admin.register(SocialProfile)
class SocialProfileAdmin(admin.ModelAdmin):
    list_display = ('slug', 'nome_exibicao', 'visibilidade', 'ativo', 'criado_em')
    list_filter = ('visibilidade', 'ativo')
    search_fields = ('slug', 'nome_exibicao')
    readonly_fields = ('uuid', 'criado_em', 'atualizado_em')


@admin.register(SocialFollow)
class SocialFollowAdmin(admin.ModelAdmin):
    list_display = ('seguidor', 'seguido', 'criado_em')
    readonly_fields = ('uuid', 'criado_em')
    raw_id_fields = ('seguidor', 'seguido')


@admin.register(EmpresaSeguidor)
class EmpresaSeguidorAdmin(admin.ModelAdmin):
    list_display = ('usuario_id', 'empresa', 'criado_em')
    readonly_fields = ('uuid', 'criado_em')
    raw_id_fields = ('usuario', 'empresa')


for model in (
    SocialPost, SocialStory, SocialPostLike, SocialPostComment, SocialPostSave,
    SocialFollowRequest, SocialBlock, SocialConversation, SocialMessage,
):
    admin.site.register(model)
