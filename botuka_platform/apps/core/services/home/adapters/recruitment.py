from django.db.models import Q
from django.utils import timezone

from apps.recruitment.models import Vaga


def obter_vagas_recentes():
    hoje = timezone.localdate()
    return list(
        Vaga.objects.filter(
            ativo=True,
            excluido_em__isnull=True,
            status=Vaga.Status.PUBLICADA,
            empresa__ativo=True,
            empresa__perfil_publico=True,
            empresa__status="ATIVA",
            empresa__excluido_em__isnull=True,
        )
        .filter(Q(inicio__isnull=True) | Q(inicio__lte=hoje))
        .filter(Q(encerramento__isnull=True) | Q(encerramento__gte=hoje))
        .select_related("empresa", "usuario_responsavel")
        .order_by("-publicado_em", "-criado_em")[:6]
    )
