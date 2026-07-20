from apps.organizations.models import Empresa


def obter_empresas_destaque():
    return list(
        Empresa.objects.filter(
            ativo=True,
            perfil_publico=True,
            status=Empresa.Status.ATIVA,
            excluido_em__isnull=True,
        )
        .select_related("cidade", "estado", "categoria_empresa")
        .order_by("-verificada", "-atualizado_em")[:6]
    )
