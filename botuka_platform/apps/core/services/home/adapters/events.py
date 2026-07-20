from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.government.models import AcaoPublica
from apps.sports.models import Campeonato

from .dto import EventoPublicoDTO


def _imagem(campo):
    return campo.url if campo and getattr(campo, "name", "") else ""


def obter_eventos():
    hoje = timezone.localdate()
    oficiais = AcaoPublica.objects.filter(
        tipo=AcaoPublica.Tipo.EVENTO, ativo=True, excluido_em__isnull=True,
        status="PUBLICADO", publicado_em__lte=timezone.now(),
        orgao__ativo=True, orgao__verificado=True, orgao__excluido_em__isnull=True,
    ).filter(Q(conclusao_prevista__isnull=True) | Q(conclusao_prevista__gte=hoje)).select_related("orgao").order_by("inicio_previsto")[:6]
    esportivos = Campeonato.objects.filter(
        ativo=True, excluido_em__isnull=True,
        status__in=["INSCRICOES", "AGENDADO", "EM_ANDAMENTO"],
        organizacao__ativo=True, organizacao__verificado=True,
        organizacao__excluido_em__isnull=True,
    ).filter(Q(data_final__isnull=True) | Q(data_final__gte=hoje)).select_related("organizacao", "modalidade").order_by("data_inicial")[:6]

    itens = [EventoPublicoDTO(
        uuid=a.uuid, titulo=a.titulo, resumo=a.resumo or a.descricao[:220],
        categoria="Evento municipal", inicio=a.inicio_previsto, fim=a.conclusao_prevista,
        local=a.local or a.bairro or a.cidade, organizador=a.orgao.nome, oficial=True,
        gratuito=None, imagem_url=_imagem(a.imagem),
        url=reverse("government_public:acao", args=[a.slug]), origem="Prefeitura",
    ) for a in oficiais]
    itens += [EventoPublicoDTO(
        uuid=c.uuid, titulo=c.nome, resumo=c.descricao[:220],
        categoria=c.modalidade.nome, inicio=c.data_inicial, fim=c.data_final,
        local=c.localidade, organizador=c.organizacao.nome, oficial=False,
        gratuito=None, imagem_url=_imagem(c.imagem),
        url=reverse("sports_public:campeonato", args=[c.slug]), origem="Esportes",
    ) for c in esportivos]
    itens.sort(key=lambda item: (item.inicio is None, item.inicio or hoje, item.titulo))
    return itens[:1], itens[1:7]
