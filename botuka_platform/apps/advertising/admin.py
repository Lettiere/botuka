from django.contrib import admin

from .models import (AuditoriaPublicidade, Campanha, CampanhaSegmentacao,
                     ContratacaoPublicidade, Criativo, EntregaPublicidade,
                     PlanoPublicitario, Posicionamento)


class CriativoInline(admin.TabularInline):
    model = Criativo
    extra = 0


@admin.register(Campanha)
class CampanhaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'empresa', 'plano', 'status', 'inicio', 'fim')
    list_filter = ('status', 'plano', 'empresa')
    readonly_fields = ('status', 'aprovada_em', 'aprovada_por')
    inlines = (CriativoInline,)


admin.site.register((PlanoPublicitario, Posicionamento, CampanhaSegmentacao,
                     ContratacaoPublicidade, EntregaPublicidade,
                     AuditoriaPublicidade))
