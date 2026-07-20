from django.db.models import Q

from apps.services.models import Servico


def obter_servicos_destaque():
    return list(
        Servico.objects.filter(
            ativo=True,
            status=Servico.Status.PUBLICADO,
            excluido_em__isnull=True,
        )
        .filter(
            Q(prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA, empresa__isnull=True)
            | Q(
                prestador_tipo=Servico.PrestadorTipo.EMPRESA,
                empresa__ativo=True,
                empresa__perfil_publico=True,
                empresa__status="ATIVA",
                empresa__excluido_em__isnull=True,
                empresa__capacidades_empresa__ativo=True,
                empresa__capacidades_empresa__status="APROVADA",
                empresa__capacidades_empresa__capacidade__codigo="PRESTAR_SERVICOS",
            )
        )
        .select_related("empresa", "usuario_responsavel", "setor", "profissao")
        .distinct()
        .order_by("-destaque", "-verificado", "-publicado_em")[:6]
    )
