"""Consultas públicas e composição editorial do BOTUKA Notícias."""

from django.db.models import Q
from django.utils import timezone

from .models import Artigo, Colunista, DestaqueEditorial, EditorialStatus


AGRO_SLUGS = {
    "agro", "agronegocio", "agricultura", "pecuaria",
    "tecnologia-no-campo",
}
UNIVERSIDADE_SLUGS = {
    "universidade", "educacao-superior", "pesquisa", "ciencia",
    "extensao", "vida-universitaria",
}


def artigos_publicos(agora=None):
    """Retorna exclusivamente artigos publicáveis no instante informado."""
    agora = agora or timezone.now()
    return (
        Artigo.objects.filter(
            status=EditorialStatus.PUBLICADO,
            ativo=True,
            excluido_em__isnull=True,
            publicado_em__isnull=False,
            publicado_em__lte=agora,
            categoria__ativo=True,
            categoria__excluido_em__isnull=True,
        )
        .filter(
            Q(autor_editorial__isnull=True)
            | Q(
                autor_editorial__ativo=True,
                autor_editorial__excluido_em__isnull=True,
            )
        )
        .select_related("categoria", "autor_editorial", "coluna", "serie")
        .prefetch_related("temas")
        .order_by("-publicado_em", "-criado_em")
    )


def _destaques_validos(posicao, agora):
    return (
        DestaqueEditorial.objects.filter(
            posicao=posicao,
            ativo=True,
            excluido_em__isnull=True,
            artigo__status=EditorialStatus.PUBLICADO,
            artigo__ativo=True,
            artigo__excluido_em__isnull=True,
            artigo__publicado_em__isnull=False,
            artigo__publicado_em__lte=agora,
            artigo__categoria__ativo=True,
            artigo__categoria__excluido_em__isnull=True,
        )
        .filter(Q(inicio__isnull=True) | Q(inicio__lte=agora))
        .filter(Q(fim__isnull=True) | Q(fim__gte=agora))
        .select_related(
            "artigo", "artigo__categoria", "artigo__autor_editorial",
            "artigo__coluna", "artigo__serie",
        )
        .order_by("ordem", "-artigo__publicado_em", "id")
    )


def _adicionar_unicos(destino, candidatos, usados, limite, exige_imagem=False):
    for artigo in candidatos:
        if artigo.pk in usados or (exige_imagem and not artigo.imagem_capa):
            continue
        destino.append(artigo)
        usados.add(artigo.pk)
        if len(destino) >= limite:
            break


def artigos_por_area(slugs, usados=(), limite=3, agora=None):
    nomes_base = {slug.replace("-", " ") for slug in slugs}
    nomes = nomes_base | {nome.title() for nome in nomes_base}
    queryset = artigos_publicos(agora).filter(
        Q(categoria__slug__in=slugs)
        | Q(categoria__nome__in=nomes)
        | Q(
            temas__slug__in=slugs,
            temas__ativo=True,
            temas__excluido_em__isnull=True,
        )
        | Q(
            temas__nome__in=nomes,
            temas__ativo=True,
            temas__excluido_em__isnull=True,
        )
    ).exclude(pk__in=usados).distinct()
    return list(queryset[:limite])


def colunistas_publicos(limite=4, agora=None):
    publicados = artigos_publicos(agora)
    return list(
        Colunista.objects.filter(
            ativo=True,
            excluido_em__isnull=True,
            autor__ativo=True,
            autor__excluido_em__isnull=True,
        )
        .filter(
            Q(
                autor__colunas__ativo=True,
                autor__colunas__excluido_em__isnull=True,
            )
            | Q(autor__artigos__in=publicados)
        )
        .select_related("autor")
        .prefetch_related("autor__colunas")
        .distinct()
        .order_by("-destaque", "ordem", "autor__nome")[:limite]
    )


def obter_home_noticias(agora=None):
    """Monta os blocos editoriais sem reutilizar artigos entre eles."""
    agora = agora or timezone.now()
    base = artigos_publicos(agora)
    usados = set()

    destaques_configurados = [
        destaque.artigo
        for destaque in _destaques_validos(
            DestaqueEditorial.Posicao.HOME_PRINCIPAL, agora
        )
    ]
    manchetes = []
    _adicionar_unicos(manchetes, destaques_configurados, usados, 1)
    if not manchetes:
        _adicionar_unicos(manchetes, base.filter(destaque=True), usados, 1)
    if not manchetes:
        _adicionar_unicos(manchetes, base, usados, 1)
    manchete = manchetes[0] if manchetes else None

    destaques = []
    _adicionar_unicos(
        destaques, destaques_configurados, usados, 3, exige_imagem=True
    )
    if len(destaques) < 3:
        _adicionar_unicos(
            destaques, base.filter(destaque=True), usados, 3,
            exige_imagem=True,
        )
    if len(destaques) < 3:
        _adicionar_unicos(
            destaques, base.exclude(imagem_capa=""), usados, 3,
            exige_imagem=True,
        )

    agro = artigos_por_area(AGRO_SLUGS, usados, 3, agora)
    usados.update(artigo.pk for artigo in agro)
    universidade = artigos_por_area(
        UNIVERSIDADE_SLUGS, usados, 3, agora
    )
    usados.update(artigo.pk for artigo in universidade)
    recentes = []
    _adicionar_unicos(recentes, base, usados, 4)

    return {
        "manchete": manchete,
        "destaques": destaques,
        "recentes": recentes,
        "agro": agro,
        "universidade": universidade,
        "colunistas": colunistas_publicos(4, agora),
        "ids_usados": usados,
    }
