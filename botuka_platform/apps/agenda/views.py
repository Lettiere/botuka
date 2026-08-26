from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import BloqueioForm, DisponibilidadeForm, ProfissionalServicoForm
from .models import (
    Agendamento,
    AgendaBloqueio,
    AgendaDisponibilidade,
    AgendaProfissional,
    AgendaProfissionalServico,
)
from .permissions import agenda_empresa_required
from .services import TRANSICOES_STATUS, alterar_status_agendamento


def _profissionais(empresa):
    return AgendaProfissional.objects.filter(
        empresa_usuario__empresa=empresa,
    ).select_related('empresa_usuario__usuario')


def _vinculos(empresa):
    return AgendaProfissionalServico.objects.filter(
        profissional__empresa_usuario__empresa=empresa,
    ).select_related('profissional__empresa_usuario__usuario', 'servico')


def _disponibilidades(empresa):
    return AgendaDisponibilidade.objects.filter(
        profissional__empresa_usuario__empresa=empresa,
    ).select_related('profissional__empresa_usuario__usuario')


def _bloqueios(empresa):
    return AgendaBloqueio.objects.filter(
        profissional__empresa_usuario__empresa=empresa,
    ).select_related('profissional__empresa_usuario__usuario')


def _agendamentos(empresa):
    return Agendamento.objects.filter(
        profissional_servico__profissional__empresa_usuario__empresa=empresa,
    ).select_related(
        'cliente',
        'profissional_servico__servico',
        'profissional_servico__profissional__empresa_usuario__usuario',
    )


@login_required
@agenda_empresa_required
def dashboard(request, empresa):
    context = {
        'empresa': empresa,
        'profissionais': _profissionais(empresa).filter(
            ativo=True, empresa_usuario__ativo=True
        ),
        'servicos_agenda': _vinculos(empresa).filter(ativo=True),
        'disponibilidades': _disponibilidades(empresa).filter(ativo=True),
        'bloqueios': _bloqueios(empresa).filter(ativo=True),
        'agendamentos': _agendamentos(empresa).order_by('-inicio')[:10],
    }
    return render(request, 'painel/agenda/dashboard.html', context)


@login_required
@agenda_empresa_required
def vinculo_lista(request, empresa):
    return render(request, 'painel/agenda/vinculo_lista.html', {
        'empresa': empresa, 'itens': _vinculos(empresa)
    })


@login_required
@agenda_empresa_required
def vinculo_form(request, empresa, pk=None):
    instance = None
    if pk is not None:
        instance = get_object_or_404(_vinculos(empresa), pk=pk)
    form = ProfissionalServicoForm(
        request.POST or None, instance=instance, empresa=empresa
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Vínculo salvo com sucesso.')
        return redirect('painel:agenda_vinculo_lista', uuid=empresa.uuid)
    return render(request, 'painel/agenda/form.html', {
        'empresa': empresa,
        'form': form,
        'titulo': 'Editar serviço da Agenda' if instance else 'Vincular serviço',
        'voltar_url': 'painel:agenda_vinculo_lista',
    })


def _alterar_ativo(request, *, objeto, ativo, redirect_name):
    if ativo:
        objeto.ativo = True
        try:
            objeto.full_clean()
            objeto.save(update_fields=['ativo', 'atualizado_em'])
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        else:
            messages.success(request, 'Registro ativado com sucesso.')
    else:
        objeto.__class__.objects.filter(pk=objeto.pk).update(ativo=False)
        messages.success(request, 'Registro desativado; o histórico foi preservado.')
    return redirect(redirect_name, uuid=objeto.profissional.empresa.uuid)


@require_POST
@login_required
@agenda_empresa_required
def vinculo_status(request, empresa, pk):
    objeto = get_object_or_404(_vinculos(empresa), pk=pk)
    ativo = request.POST.get('ativo') == '1'
    if ativo and (
        not objeto.profissional.ativo
        or not objeto.profissional.empresa_usuario.ativo
        or not objeto.servico.ativo
        or objeto.servico.status != objeto.servico.Status.PUBLICADO
    ):
        messages.error(request, 'Profissional e serviço precisam estar operacionais.')
        return redirect('painel:agenda_vinculo_lista', uuid=empresa.uuid)
    return _alterar_ativo(
        request, objeto=objeto, ativo=ativo,
        redirect_name='painel:agenda_vinculo_lista'
    )


@login_required
@agenda_empresa_required
def disponibilidade_lista(request, empresa):
    return render(request, 'painel/agenda/disponibilidade_lista.html', {
        'empresa': empresa, 'itens': _disponibilidades(empresa)
    })


@login_required
@agenda_empresa_required
def disponibilidade_form(request, empresa, pk=None):
    instance = get_object_or_404(_disponibilidades(empresa), pk=pk) if pk else None
    form = DisponibilidadeForm(
        request.POST or None, instance=instance, empresa=empresa
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Disponibilidade salva com sucesso.')
        return redirect('painel:agenda_disponibilidade_lista', uuid=empresa.uuid)
    return render(request, 'painel/agenda/form.html', {
        'empresa': empresa, 'form': form,
        'titulo': 'Editar disponibilidade' if instance else 'Nova disponibilidade',
        'voltar_url': 'painel:agenda_disponibilidade_lista',
    })


@require_POST
@login_required
@agenda_empresa_required
def disponibilidade_status(request, empresa, pk):
    objeto = get_object_or_404(_disponibilidades(empresa), pk=pk)
    return _alterar_ativo(
        request, objeto=objeto, ativo=request.POST.get('ativo') == '1',
        redirect_name='painel:agenda_disponibilidade_lista'
    )


@login_required
@agenda_empresa_required
def bloqueio_lista(request, empresa):
    return render(request, 'painel/agenda/bloqueio_lista.html', {
        'empresa': empresa, 'itens': _bloqueios(empresa).order_by('-inicio')
    })


@login_required
@agenda_empresa_required
def bloqueio_form(request, empresa, pk=None):
    instance = get_object_or_404(_bloqueios(empresa), pk=pk) if pk else None
    form = BloqueioForm(request.POST or None, instance=instance, empresa=empresa)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Bloqueio salvo com sucesso.')
        return redirect('painel:agenda_bloqueio_lista', uuid=empresa.uuid)
    return render(request, 'painel/agenda/form.html', {
        'empresa': empresa, 'form': form,
        'titulo': 'Editar bloqueio' if instance else 'Novo bloqueio',
        'voltar_url': 'painel:agenda_bloqueio_lista',
    })


@require_POST
@login_required
@agenda_empresa_required
def bloqueio_status(request, empresa, pk):
    objeto = get_object_or_404(_bloqueios(empresa), pk=pk)
    return _alterar_ativo(
        request, objeto=objeto, ativo=request.POST.get('ativo') == '1',
        redirect_name='painel:agenda_bloqueio_lista'
    )


@login_required
@agenda_empresa_required
def agendamento_lista(request, empresa):
    return render(request, 'painel/agenda/agendamento_lista.html', {
        'empresa': empresa,
        'itens': _agendamentos(empresa).order_by('-inicio'),
    })


@login_required
@agenda_empresa_required
def agendamento_detalhe(request, empresa, pk):
    item = get_object_or_404(_agendamentos(empresa), pk=pk)
    return render(request, 'painel/agenda/agendamento_detalhe.html', {
        'empresa': empresa,
        'item': item,
        'transicoes': TRANSICOES_STATUS.get(item.status, set()),
        'status_choices': Agendamento.Status,
    })


@require_POST
@login_required
@agenda_empresa_required
def agendamento_status(request, empresa, pk):
    novo_status = request.POST.get('status', '')
    try:
        alterar_status_agendamento(
            empresa=empresa, agendamento_id=pk, novo_status=novo_status
        )
    except Agendamento.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    else:
        messages.success(request, 'Status do agendamento atualizado.')
    return redirect('painel:agenda_agendamento_detalhe', uuid=empresa.uuid, pk=pk)
