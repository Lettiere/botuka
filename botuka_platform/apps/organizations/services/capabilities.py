"""Sincronização de capacidades derivadas do perfil da empresa."""

from django.utils import timezone

from apps.organizations.models import Capacidade, Empresa, EmpresaCapacidade


def sincronizar_capacidades_do_perfil(empresa: Empresa) -> EmpresaCapacidade | None:
    """Aprova a capacidade inerente ao perfil, sem alterar capacidades extras."""

    if not empresa.ativo or empresa.atuacao not in {
        Empresa.Atuacao.SERVICOS,
        Empresa.Atuacao.COMERCIO_E_SERVICOS,
    }:
        return None

    capacidade = Capacidade.objects.filter(
        codigo='PRESTAR_SERVICOS',
        ativo=True,
    ).first()
    if capacidade is None:
        return None

    agora = timezone.now()
    vinculo, criado = EmpresaCapacidade.objects.get_or_create(
        empresa=empresa,
        capacidade=capacidade,
        defaults={
            'status': EmpresaCapacidade.Status.APROVADA,
            'ativo': True,
            'aprovado_por': None,
            'aprovado_em': agora,
            'motivo_rejeicao': '',
        },
    )

    if (
        not criado
        and vinculo.ativo
        and vinculo.status == EmpresaCapacidade.Status.PENDENTE
    ):
        EmpresaCapacidade.objects.filter(
            pk=vinculo.pk,
            ativo=True,
            status=EmpresaCapacidade.Status.PENDENTE,
        ).update(
            status=EmpresaCapacidade.Status.APROVADA,
            aprovado_por=None,
            aprovado_em=agora,
            motivo_rejeicao='',
            atualizado_em=agora,
        )
        vinculo.refresh_from_db()

    return vinculo
