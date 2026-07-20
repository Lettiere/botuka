from django.db.models import Q
from django.urls import reverse

from apps.organizations.models import Empresa

from .dto import ConteudoCidadeDTO


TERMOS = ("gastronom", "restaurant", "bar", "lanchon", "cafeter", "padaria", "pizz", "hamburg", "sorvet", "doceria")


def _imagem(empresa):
    campo = empresa.imagem_capa or empresa.logo
    return campo.url if campo and getattr(campo, "name", "") else ""


def obter_gastronomia():
    filtro = Q()
    for termo in TERMOS:
        filtro |= Q(categoria_empresa__slug__icontains=termo) | Q(categoria_empresa__nome__icontains=termo)
    empresas = Empresa.objects.filter(
        filtro, ativo=True, perfil_publico=True, status=Empresa.Status.ATIVA,
        excluido_em__isnull=True, categoria_empresa__ativo=True,
        categoria_empresa__removido_em__isnull=True,
    ).select_related("categoria_empresa", "cidade", "estado").order_by("-verificada", "nome_fantasia")[:6]
    return [ConteudoCidadeDTO(
        uuid=e.uuid, titulo=e.nome_fantasia, resumo=e.descricao_curta,
        categoria=e.categoria_empresa.nome, local=" · ".join(filter(None, [e.bairro, str(e.cidade)])),
        imagem_url=_imagem(e), url=reverse("publico:empresa", args=[e.slug]),
        origem="Empresa local",
    ) for e in empresas]
