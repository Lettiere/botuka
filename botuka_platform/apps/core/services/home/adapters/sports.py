from django.utils import timezone

from apps.sports.models import Campeonato, Disputa, Modalidade


def obter_esportes():
    agora = timezone.now()
    modalidades = list(
        Modalidade.objects.filter(ativo=True, excluido_em__isnull=True)
        .order_by("ordem", "nome")[:6]
    )
    campeonatos = list(
        Campeonato.objects.filter(
            ativo=True,
            excluido_em__isnull=True,
            status__in=["INSCRICOES", "AGENDADO", "EM_ANDAMENTO"],
            organizacao__ativo=True,
            organizacao__verificado=True,
            organizacao__excluido_em__isnull=True,
        )
        .select_related("organizacao", "modalidade", "estilo", "categoria")
        .order_by("data_inicial")[:6]
    )
    proximos = list(
        Disputa.objects.filter(
            ativo=True,
            excluido_em__isnull=True,
            status__in=["AGENDADA", "EM_ANDAMENTO"],
            data_hora__gte=agora,
            campeonato__organizacao__ativo=True,
            campeonato__organizacao__verificado=True,
            campeonato__organizacao__excluido_em__isnull=True,
            campeonato__status__in=["INSCRICOES", "AGENDADO", "EM_ANDAMENTO"],
        )
        .select_related("campeonato", "participante_a", "participante_b")
        .order_by("data_hora")[:6]
    )
    resultados = list(
        Disputa.objects.filter(ativo=True, excluido_em__isnull=True, status="ENCERRADA", campeonato__status__in=["EM_ANDAMENTO", "FINALIZADO"], campeonato__organizacao__ativo=True, campeonato__organizacao__verificado=True, campeonato__organizacao__excluido_em__isnull=True)
        .select_related("campeonato", "participante_a", "participante_b")
        .order_by("-data_hora")[:6]
    )
    return modalidades, campeonatos, proximos, resultados
