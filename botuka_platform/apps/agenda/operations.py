"""Transições empresariais da Agenda."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.models import Empresa

from .dashboard import construir_central_agenda
from .models import AgendaEmpresa


def agenda_empresa_aberta(empresa):
    return AgendaEmpresa.objects.filter(
        empresa_id=empresa.pk,
        status=AgendaEmpresa.Status.ABERTA,
    ).exists()


@transaction.atomic
def abrir_agenda_empresa(*, empresa, usuario):
    empresa = Empresa.objects.select_for_update().get(pk=empresa.pk)
    diagnostico = construir_central_agenda(empresa, considerar_estado=False)
    pendencias = [item['rotulo'] for item in diagnostico['checklist'] if not item['ok']]
    if pendencias:
        raise ValidationError(
            'Não foi possível abrir a Agenda. Pendências: ' + ', '.join(pendencias) + '.'
        )
    agenda, _ = AgendaEmpresa.objects.select_for_update().get_or_create(empresa=empresa)
    agenda.status = AgendaEmpresa.Status.ABERTA
    agenda.aberto_em = timezone.now()
    agenda.fechado_em = None
    agenda.atualizado_por = usuario
    agenda.save(update_fields=[
        'status', 'aberto_em', 'fechado_em', 'atualizado_por', 'atualizado_em',
    ])
    return agenda


@transaction.atomic
def fechar_agenda_empresa(*, empresa, usuario):
    empresa = Empresa.objects.select_for_update().get(pk=empresa.pk)
    agenda, _ = AgendaEmpresa.objects.select_for_update().get_or_create(empresa=empresa)
    agenda.status = AgendaEmpresa.Status.FECHADA
    agenda.fechado_em = timezone.now()
    agenda.atualizado_por = usuario
    agenda.save(update_fields=[
        'status', 'fechado_em', 'atualizado_por', 'atualizado_em',
    ])
    return agenda
