from django.db.models import Q
from django.utils import timezone

from apps.government.models import AcaoPublica, OrgaoPublico


def obter_prefeitura():
    hoje = timezone.localdate()
    orgaos = list(
        OrgaoPublico.objects.filter(
            ativo=True, verificado=True, excluido_em__isnull=True
        ).order_by("nome")[:4]
    )
    acoes = list(
        AcaoPublica.objects.filter(
            ativo=True,
            excluido_em__isnull=True,
            status="PUBLICADO",
            orgao__ativo=True,
            orgao__verificado=True,
            orgao__excluido_em__isnull=True,
            situacao__in=["PLANEJADA", "LICITACAO", "AGENDADA", "EM_ANDAMENTO"],
        )
        .filter(Q(conclusao_prevista__isnull=True) | Q(conclusao_prevista__gte=hoje))
        .select_related("orgao", "autor")
        .order_by("-destaque", "inicio_previsto", "-publicado_em")[:4]
    )
    return acoes, orgaos
