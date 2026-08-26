from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.services.models import Servico

from .models import (
    Agendamento,
    AgendaBloqueio,
    AgendaDisponibilidade,
    AgendaProfissional,
    AgendaProfissionalServico,
)


STATUS_OCUPANTES = (Agendamento.Status.PENDENTE, Agendamento.Status.CONFIRMADO)


def vinculos_publicos_queryset():
    return AgendaProfissionalServico.objects.filter(
        ativo=True,
        profissional__ativo=True,
        profissional__empresa_usuario__ativo=True,
        profissional__empresa_usuario__empresa__ativo=True,
        profissional__empresa_usuario__empresa__perfil_publico=True,
        profissional__empresa_usuario__empresa__status='ATIVA',
        servico__ativo=True,
        servico__status=Servico.Status.PUBLICADO,
        servico__excluido_em__isnull=True,
        servico__prestador_tipo=Servico.PrestadorTipo.EMPRESA,
        servico__empresa__isnull=False,
    ).filter(
        servico__empresa_id=models.F(
            'profissional__empresa_usuario__empresa_id'
        )
    ).select_related(
        'servico',
        'servico__empresa',
        'profissional__empresa_usuario__usuario',
        'profissional__empresa_usuario__empresa',
    )


def vinculo_publicamente_valido(vinculo):
    empresa = vinculo.servico.empresa
    return bool(
        empresa
        and empresa.pode_aceitar_agendamentos
        and vinculo.profissional.empresa_usuario.empresa_id == empresa.pk
    )


def vinculos_agendaveis(*, empresa=None, servico=None):
    queryset = vinculos_publicos_queryset()
    if empresa is not None:
        if not empresa.pode_aceitar_agendamentos:
            return []
        queryset = queryset.filter(servico__empresa=empresa)
    if servico is not None:
        queryset = queryset.filter(servico=servico)
    return [item for item in queryset if vinculo_publicamente_valido(item)]


def servicos_agendaveis(empresa):
    ids = {item.servico_id for item in vinculos_agendaveis(empresa=empresa)}
    return Servico.objects.filter(pk__in=ids).order_by('titulo')


def nome_publico_profissional(profissional):
    usuario = profissional.usuario
    nome = (usuario.nome_exibicao or usuario.get_full_name()).strip()
    return nome or 'Profissional'


def _aware_local(valor):
    if timezone.is_naive(valor):
        return timezone.make_aware(valor, timezone.get_current_timezone())
    return timezone.localtime(valor)


def interpretar_inicio(valor):
    try:
        inicio = datetime.fromisoformat(valor)
    except (TypeError, ValueError) as exc:
        raise ValidationError('Horário inválido.') from exc
    return _aware_local(inicio)


def _sobrepoe(inicio, fim, outro_inicio, outro_fim):
    return outro_inicio < fim and outro_fim > inicio


def gerar_slots(vinculo, data, *, agora=None):
    if not isinstance(data, date):
        raise ValidationError('Data inválida.')
    if not vinculo_publicamente_valido(vinculo):
        return []
    agora = timezone.localtime(agora or timezone.now())
    duracao = timedelta(minutes=vinculo.duracao_minutos)
    disponibilidades = AgendaDisponibilidade.objects.filter(
        profissional=vinculo.profissional,
        ativo=True,
        dia_semana=data.weekday(),
    ).order_by('hora_inicio')
    slots = {}
    for faixa in disponibilidades:
        cursor = timezone.make_aware(
            datetime.combine(data, faixa.hora_inicio),
            timezone.get_current_timezone(),
        )
        limite = timezone.make_aware(
            datetime.combine(data, faixa.hora_fim),
            timezone.get_current_timezone(),
        )
        while cursor + duracao <= limite:
            fim = cursor + duracao
            if cursor > agora:
                bloqueado = AgendaBloqueio.objects.filter(
                    profissional=vinculo.profissional,
                    ativo=True,
                    inicio__lt=fim,
                    fim__gt=cursor,
                ).exists()
                ocupado = Agendamento.objects.filter(
                    profissional_servico__profissional=vinculo.profissional,
                    status__in=STATUS_OCUPANTES,
                    inicio__lt=fim,
                    fim__gt=cursor,
                ).exists()
                if not bloqueado and not ocupado:
                    slots[cursor.isoformat()] = cursor
            cursor = fim
    return list(slots.values())


def obter_vinculo_publico(uuid):
    try:
        vinculo = vinculos_publicos_queryset().get(uuid=uuid)
    except AgendaProfissionalServico.DoesNotExist as exc:
        raise ValidationError('Vínculo de Agenda indisponível.') from exc
    if not vinculo_publicamente_valido(vinculo):
        raise ValidationError('Agenda indisponível para esta empresa.')
    return vinculo


@transaction.atomic
def criar_agendamento_publico(*, vinculo_uuid, cliente, inicio):
    vinculo_inicial = obter_vinculo_publico(vinculo_uuid)
    AgendaProfissional.objects.select_for_update().get(
        pk=vinculo_inicial.profissional_id
    )
    vinculo = obter_vinculo_publico(vinculo_uuid)
    inicio = interpretar_inicio(inicio) if isinstance(inicio, str) else _aware_local(inicio)
    slots = gerar_slots(vinculo, timezone.localdate(inicio))
    if inicio not in slots:
        raise ValidationError('O horário selecionado não está mais disponível.')
    fim = inicio + timedelta(minutes=vinculo.duracao_minutos)
    agendamento = Agendamento(
        profissional_servico=vinculo,
        cliente=cliente,
        inicio=inicio,
        fim=fim,
        status=Agendamento.Status.PENDENTE,
    )
    agendamento.full_clean()
    agendamento.save()
    return agendamento


@transaction.atomic
def cancelar_agendamento_cliente(*, agendamento_uuid, cliente):
    try:
        agendamento = Agendamento.objects.select_for_update().get(
            uuid=agendamento_uuid,
            cliente=cliente,
        )
    except Agendamento.DoesNotExist as exc:
        raise ValidationError('Agendamento não encontrado.') from exc
    if agendamento.status not in (
        Agendamento.Status.PENDENTE,
        Agendamento.Status.CONFIRMADO,
    ):
        raise ValidationError('Este agendamento não pode ser cancelado.')
    Agendamento.objects.filter(pk=agendamento.pk).update(
        status=Agendamento.Status.CANCELADO
    )
    agendamento.status = Agendamento.Status.CANCELADO
    return agendamento
