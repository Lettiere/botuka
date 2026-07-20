from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.government.models import AcaoPublica

from .dto import ConteudoCidadeDTO


TERMOS = ("parque", "praça", "praca", "trilha", "mirante", "área verde", "area verde", "espaço público", "espaco publico")


def obter_parques():
    filtro = Q()
    for termo in TERMOS:
        filtro |= Q(titulo__icontains=termo) | Q(resumo__icontains=termo) | Q(descricao__icontains=termo)
    acoes = AcaoPublica.objects.filter(
        filtro, ativo=True, excluido_em__isnull=True, status="PUBLICADO",
        publicado_em__lte=timezone.now(), orgao__ativo=True,
        orgao__verificado=True, orgao__excluido_em__isnull=True,
    ).select_related("orgao").order_by("-destaque", "-publicado_em")[:5]
    return [ConteudoCidadeDTO(
        uuid=a.uuid, titulo=a.titulo, resumo=a.resumo or a.descricao[:220],
        categoria="Espaço público", local=a.bairro or a.local,
        imagem_url=a.imagem.url if a.imagem and a.imagem.name else "",
        url=reverse("government_public:acao", args=[a.slug]), origem=a.orgao.nome,
        oficial=True,
    ) for a in acoes]
