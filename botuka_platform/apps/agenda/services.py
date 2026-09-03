from django.core.exceptions import ValidationError
from django.db import transaction

from datetime import timedelta

from django.utils import timezone

from .models import (
    Agendamento, AgendamentoHistorico, AgendaProfissional,
    AgendaProfissionalServico,
)
from .operations import agenda_empresa_aberta


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
def alterar_status_agendamento(*, empresa, agendamento_id, novo_status, usuario=None):
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
    status_anterior = agendamento.status
    Agendamento.objects.filter(pk=agendamento.pk).update(status=novo_status)
    agendamento.status = novo_status
    AgendamentoHistorico.objects.create(
        agendamento=agendamento,
        acao=(AgendamentoHistorico.Acao.CANCELADO if novo_status == Agendamento.Status.CANCELADO else AgendamentoHistorico.Acao.STATUS),
        status_anterior=status_anterior,
        status_novo=novo_status,
        inicio_novo=agendamento.inicio,
        realizado_por=usuario,
    )
    return agendamento


def _vinculo_empresa(empresa, vinculo_id):
    return AgendaProfissionalServico.objects.filter(
        pk=vinculo_id,
        profissional__empresa_usuario__empresa=empresa,
        ativo=True,
        profissional__ativo=True,
        profissional__empresa_usuario__ativo=True,
    ).select_related('profissional', 'servico').first()


@transaction.atomic
def criar_agendamento_interno(*, empresa, vinculo_id, cliente, inicio, usuario):
    if not agenda_empresa_aberta(empresa):
        raise ValidationError('A Agenda precisa estar aberta para criar agendamentos.')
    vinculo = _vinculo_empresa(empresa, vinculo_id)
    if not vinculo:
        raise ValidationError('Profissional e serviço indisponíveis para esta empresa.')
    AgendaProfissional.objects.select_for_update().get(pk=vinculo.profissional_id)
    from .public_services import gerar_slots, interpretar_inicio
    inicio = interpretar_inicio(inicio) if isinstance(inicio, str) else inicio
    if inicio not in gerar_slots(vinculo, timezone.localdate(inicio)):
        raise ValidationError('O horário selecionado não está disponível.')
    item = Agendamento(
        profissional_servico=vinculo, cliente=cliente, inicio=inicio,
        fim=inicio + timedelta(minutes=vinculo.duracao_minutos),
        status=Agendamento.Status.CONFIRMADO,
    )
    item.save()
    AgendamentoHistorico.objects.create(
        agendamento=item, acao=AgendamentoHistorico.Acao.CRIADO,
        status_novo=item.status, inicio_novo=item.inicio, realizado_por=usuario,
    )
    return item


@transaction.atomic
def reagendar_agendamento(*, empresa, agendamento_id, vinculo_id, inicio, usuario):
    if not agenda_empresa_aberta(empresa):
        raise ValidationError('A Agenda precisa estar aberta para reagendar.')
    item = Agendamento.objects.select_for_update().filter(
        pk=agendamento_id,
        profissional_servico__profissional__empresa_usuario__empresa=empresa,
        status__in=(Agendamento.Status.PENDENTE, Agendamento.Status.CONFIRMADO),
    ).first()
    vinculo = _vinculo_empresa(empresa, vinculo_id)
    if not item or not vinculo:
        raise ValidationError('Agendamento ou vínculo indisponível.')
    ids = sorted({item.profissional.pk, vinculo.profissional.pk})
    list(AgendaProfissional.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
    from .public_services import gerar_slots, interpretar_inicio
    inicio = interpretar_inicio(inicio) if isinstance(inicio, str) else inicio
    if inicio not in gerar_slots(
        vinculo, timezone.localdate(inicio), excluir_agendamento_id=item.pk,
    ):
        raise ValidationError('O novo horário não está disponível.')
    inicio_anterior = item.inicio
    item.profissional_servico = vinculo
    item.inicio = inicio
    item.fim = inicio + timedelta(minutes=vinculo.duracao_minutos)
    item.save()
    AgendamentoHistorico.objects.create(
        agendamento=item, acao=AgendamentoHistorico.Acao.REAGENDADO,
        status_anterior=item.status, status_novo=item.status,
        inicio_anterior=inicio_anterior, inicio_novo=inicio, realizado_por=usuario,
    )
    return item
