from django.contrib import admin

from .models import Cobranca, ChaveIdempotencia, ItemCobranca, Pagamento, Transacao, Webhook


class ItemInline(admin.TabularInline):
    model = ItemCobranca
    extra = 0
    readonly_fields = ('valor_total',)


@admin.register(Cobranca)
class CobrancaAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'empresa', 'status', 'valor_total', 'criado_em')
    list_filter = ('status', 'empresa')
    readonly_fields = ('valor_total', 'paga_em', 'cancelada_em', 'estornada_em')
    inlines = (ItemInline,)


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'cobranca', 'gateway', 'status', 'valor')
    readonly_fields = ('valor', 'status', 'referencia_gateway', 'confirmado_em')


admin.site.register(Transacao)
admin.site.register(Webhook)
admin.site.register(ChaveIdempotencia)
