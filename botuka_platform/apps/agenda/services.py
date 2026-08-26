from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Agendamento


TRANSICOES_STATUS = {
    Agendamento.Status.PENDENTE: {
        Agendamento.Status.CONFIRMADO,
        Agendamento.Status.CANCELADO,
    },
    Agendamento.Status.CONFIRMADO: {
        Agendamento.Status.CONCLUIDO,
        Agendamento.Status.CANCELADO,
        Agendamento.Status.FALTOU,
    },
}


@transaction.atomic
def alterar_status_agendamento(*, empresa, agendamento_id, novo_status):
    agendamento = (
        Agendamento.objects.select_for_update()
        .filter(
            profissional_servico__profissional__empresa_usuario__empresa=empresa,
            pk=agendamento_id,
        )
        .first()
    )
    if agendamento is None:
        raise Agendamento.DoesNotExist
    if novo_status not in TRANSICOES_STATUS.get(agendamento.status, set()):
        raise ValidationError('Transição de status não permitida.')
    Agendamento.objects.filter(pk=agendamento.pk).update(status=novo_status)
    agendamento.status = novo_status
    return agendamento
