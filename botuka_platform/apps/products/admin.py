from django.contrib import admin

from .models import (
    AtributoProduto,
    BloqueioNegociacao,
    CategoriaProduto,
    Conversa,
    DenunciaNegociacao,
    FamiliaProduto,
    LogVerificacaoVendedor,
    MensagemConversa,
    SegmentoProduto,
    SetorProduto,
    TipoProduto,
    TipoProdutoSegmento,
)


for model in (
    SetorProduto, CategoriaProduto, FamiliaProduto, TipoProduto, SegmentoProduto, TipoProdutoSegmento,
    AtributoProduto, Conversa, MensagemConversa, DenunciaNegociacao,
    BloqueioNegociacao, LogVerificacaoVendedor,
):
    admin.site.register(model)
