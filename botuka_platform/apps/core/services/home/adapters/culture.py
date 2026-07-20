from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.government.models import AcaoPublica
from apps.news.models import Artigo

from .dto import ConteudoCidadeDTO


TERMOS = Q(titulo__icontains="cultur") | Q(resumo__icontains="cultur") | Q(titulo__icontains="museu") | Q(titulo__icontains="festival")


def _imagem(campo):
    return campo.url if campo and getattr(campo, "name", "") else ""


def obter_cultura():
    artigos = Artigo.objects.filter(
        status="PUBLICADO", ativo=True, excluido_em__isnull=True,
        publicado_em__lte=timezone.now(), categoria__ativo=True,
        categoria__excluido_em__isnull=True,
    ).filter(Q(categoria__slug="cultura") | Q(categoria__nome__iexact="Cultura")).select_related("categoria").order_by("-destaque", "-publicado_em")[:6]
    acoes = AcaoPublica.objects.filter(
        TERMOS, ativo=True, excluido_em__isnull=True, status="PUBLICADO",
        publicado_em__lte=timezone.now(), orgao__ativo=True,
        orgao__verificado=True, orgao__excluido_em__isnull=True,
    ).select_related("orgao").order_by("-destaque", "-publicado_em")[:4]
    itens = [ConteudoCidadeDTO(
        uuid=a.uuid, titulo=a.titulo, resumo=a.resumo or a.subtitulo,
        categoria=a.categoria.nome, local="", imagem_url=_imagem(a.imagem_capa),
        url=reverse("news_public:artigo", args=[a.slug]), origem="BOTUKA News",
    ) for a in artigos]
    itens += [ConteudoCidadeDTO(
        uuid=a.uuid, titulo=a.titulo, resumo=a.resumo or a.descricao[:220],
        categoria="Ação cultural", local=a.local or a.bairro,
        imagem_url=_imagem(a.imagem), url=reverse("government_public:acao", args=[a.slug]),
        origem=a.orgao.nome, oficial=True,
    ) for a in acoes]
    return itens[:1], itens[1:7]
