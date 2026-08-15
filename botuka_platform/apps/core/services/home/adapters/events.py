from datetime import date, datetime

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Evento
from apps.government.models import AcaoPublica
from apps.sports.models import Campeonato

from .dto import EventoPublicoDTO


def _imagem(campo):
    return campo.url if campo and getattr(campo, "name", "") else ""


def _data_ordenacao(valor):
    """
    Normaliza DateTimeField e DateField para evitar comparação entre
    datetime e date ao consolidar eventos de origens diferentes.
    """
    if valor is None:
        return date.max

    if isinstance(valor, datetime):
        if timezone.is_aware(valor):
            return timezone.localtime(valor).date()
        return valor.date()

    return valor


def _organizador_evento(evento):
    if evento.organizador:
        return evento.organizador

    if evento.empresa_promotora:
        return evento.empresa_promotora.nome

    if evento.realizador:
        return evento.realizador

    return "Organização não informada"


def _gratuidade_evento(evento):
    if (
        evento.modalidade_participacao_futura
        == Evento.ParticipacaoFutura.GRATUITA
    ):
        return True

    if (
        evento.modalidade_participacao_futura
        == Evento.ParticipacaoFutura.PAGA
    ):
        return False

    return None


def obter_eventos():
    agora = timezone.now()
    hoje = timezone.localdate()

    cadastrados = (
        Evento.objects.filter(
            ativo=True,
            removido_em__isnull=True,
            publico=True,
            status=Evento.Status.PUBLICADO,
            publicado_em__isnull=False,
            publicado_em__lte=agora,
        )
        .filter(
            Q(fim__gte=agora)
            | Q(fim__isnull=True, inicio__gte=agora)
        )
        .select_related("empresa_promotora")
        .order_by("inicio", "titulo")[:12]
    )

    oficiais = (
        AcaoPublica.objects.filter(
            tipo=AcaoPublica.Tipo.EVENTO,
            ativo=True,
            excluido_em__isnull=True,
            status="PUBLICADO",
            publicado_em__lte=agora,
            orgao__ativo=True,
            orgao__verificado=True,
            orgao__excluido_em__isnull=True,
        )
        .filter(
            Q(conclusao_prevista__isnull=True)
            | Q(conclusao_prevista__gte=hoje)
        )
        .select_related("orgao")
        .order_by("inicio_previsto")[:12]
    )

    esportivos = (
        Campeonato.objects.filter(
            ativo=True,
            excluido_em__isnull=True,
            status__in=["INSCRICOES", "AGENDADO", "EM_ANDAMENTO"],
            organizacao__ativo=True,
            organizacao__verificado=True,
            organizacao__excluido_em__isnull=True,
        )
        .filter(
            Q(data_final__isnull=True)
            | Q(data_final__gte=hoje)
        )
        .select_related("organizacao", "modalidade")
        .order_by("data_inicial")[:12]
    )

    itens = [
        EventoPublicoDTO(
            uuid=e.uuid,
            titulo=e.titulo,
            resumo=e.resumo or e.descricao[:220],
            categoria=e.categoria or "Evento",
            inicio=e.inicio,
            fim=e.fim,
            local=e.local,
            organizador=_organizador_evento(e),
            oficial=False,
            gratuito=_gratuidade_evento(e),
            imagem_url=_imagem(e.imagem_principal),
            url=e.get_absolute_url(),
            origem="Eventos",
        )
        for e in cadastrados
    ]

    itens += [
        EventoPublicoDTO(
            uuid=a.uuid,
            titulo=a.titulo,
            resumo=a.resumo or a.descricao[:220],
            categoria="Evento municipal",
            inicio=a.inicio_previsto,
            fim=a.conclusao_prevista,
            local=a.local or a.bairro or a.cidade,
            organizador=a.orgao.nome,
            oficial=True,
            gratuito=None,
            imagem_url=_imagem(a.imagem),
            url=reverse("government_public:acao", args=[a.slug]),
            origem="Prefeitura",
        )
        for a in oficiais
    ]

    itens += [
        EventoPublicoDTO(
            uuid=c.uuid,
            titulo=c.nome,
            resumo=c.descricao[:220],
            categoria=c.modalidade.nome,
            inicio=c.data_inicial,
            fim=c.data_final,
            local=c.localidade,
            organizador=c.organizacao.nome,
            oficial=False,
            gratuito=None,
            imagem_url=_imagem(c.imagem),
            url=reverse("sports_public:campeonato", args=[c.slug]),
            origem="Esportes",
        )
        for c in esportivos
    ]

    itens.sort(
        key=lambda item: (
            item.inicio is None,
            _data_ordenacao(item.inicio),
            item.titulo.casefold(),
        )
    )

    return itens[:1], itens[1:7]
