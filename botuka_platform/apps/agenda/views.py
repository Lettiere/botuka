from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from .forms import (
    BloqueioForm,
    DisponibilidadeForm,
    FuncionamentoEmpresaForm,
    ProfissionalServicoForm,
)
from .models import (
    Agendamento,
    AgendaBloqueio,
    AgendaDisponibilidade,
    AgendaDisponibilidadeData,
    AgendaFuncionamentoEmpresa,
    AgendaProfissional,
    AgendaProfissionalServico,
)
from .permissions import agenda_empresa_required
from .public_services import resumo_operacional_empresa
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
    return AgendaDisponibilidadeData.objects.filter(
        profissional__empresa_usuario__empresa=empresa,
    ).select_related('profissional__empresa_usuario__usuario')



def _funcionamentos(empresa):
    return AgendaFuncionamentoEmpresa.objects.filter(
        empresa=empresa,
    )


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
    resumo = resumo_operacional_empresa(empresa)
    context = {
        'empresa': empresa,
        'profissionais': _profissionais(empresa).filter(
            ativo=True, empresa_usuario__ativo=True
        ),
        'servicos_agenda': _vinculos(empresa).filter(ativo=True),
        'disponibilidades': _disponibilidades(empresa).filter(ativo=True),
        'bloqueios': _bloqueios(empresa).filter(ativo=True),
        'agendamentos': resumo['proximos'],
        'agenda_resumo': resumo,
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
def funcionamento_lista(request, empresa):
    itens = _funcionamentos(empresa).order_by(
        'dia_semana', 'hora_inicio'
    )
    return render(request, 'painel/agenda/funcionamento_lista.html', {
        'empresa': empresa,
        'itens': itens,
        'configurado': itens.exists(),
        'dias_semana': AgendaFuncionamentoEmpresa.DiaSemana.choices,
    })


@login_required
@agenda_empresa_required
def funcionamento_form(request, empresa, pk=None):
    instance = (
        get_object_or_404(_funcionamentos(empresa), pk=pk)
        if pk else None
    )

    form = FuncionamentoEmpresaForm(
        request.POST or None,
        instance=instance,
        empresa=empresa,
    )

    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.empresa = empresa
        item.ativo = True
        item.save()

        messages.success(
            request,
            'Funcionamento da empresa salvo com sucesso.'
        )

        return redirect(
            'painel:agenda_funcionamento_lista',
            uuid=empresa.uuid,
        )

    return render(request, 'painel/agenda/form.html', {
        'empresa': empresa,
        'form': form,
        'titulo': (
            'Editar funcionamento'
            if instance else
            'Novo período de funcionamento'
        ),
        'voltar_url': 'painel:agenda_funcionamento_lista',
    })


@require_POST
@login_required
@agenda_empresa_required
def funcionamento_status(request, empresa, pk):
    item = get_object_or_404(
        _funcionamentos(empresa),
        pk=pk,
    )

    ativo = request.POST.get('ativo') == '1'

    if ativo:
        item.ativo = True
        try:
            item.save()
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        else:
            messages.success(
                request,
                'Período de funcionamento ativado.'
            )
    else:
        AgendaFuncionamentoEmpresa.objects.filter(
            pk=item.pk
        ).update(ativo=False)

        messages.success(
            request,
            'Período de funcionamento desativado.'
        )

    return redirect(
        'painel:agenda_funcionamento_lista',
        uuid=empresa.uuid,
    )


def _agenda_percentual(valor, inicio_grade=6 * 60, fim_grade=23 * 60):
    minutos = valor.hour * 60 + valor.minute
    total = fim_grade - inicio_grade
    posicao = max(0, min(total, minutos - inicio_grade))
    return round((posicao / total) * 100, 4)


def _agenda_bloco(inicio, fim, *, tipo, titulo, subtitulo='', href=''):
    inicio_local = timezone.localtime(inicio)
    fim_local = timezone.localtime(fim)

    grade_inicio = 6 * 60
    grade_fim = 23 * 60
    total = grade_fim - grade_inicio

    ini_min = inicio_local.hour * 60 + inicio_local.minute
    fim_min = fim_local.hour * 60 + fim_local.minute

    ini = max(grade_inicio, ini_min)
    fim_m = min(grade_fim, fim_min)

    if fim_m <= ini:
        return None

    top = ((ini - grade_inicio) / total) * 100
    height = ((fim_m - ini) / total) * 100

    return {
        'tipo': tipo,
        'titulo': titulo,
        'subtitulo': subtitulo,
        'inicio': inicio_local,
        'fim': fim_local,
        'top': round(top, 4),
        'height': max(round(height, 4), 1.3),
        'href': href,
    }


@login_required
@agenda_empresa_required
def calendario_operacional(request, empresa):
    hoje = timezone.localdate()

    data_texto = request.GET.get('data', '').strip()

    try:
        referencia = date.fromisoformat(data_texto) if data_texto else hoje
    except ValueError:
        referencia = hoje

    inicio_semana = referencia - timedelta(days=referencia.weekday())
    fim_semana = inicio_semana + timedelta(days=7)

    profissional_id = request.GET.get('profissional', '').strip()

    profissionais = _profissionais(empresa).filter(
        ativo=True,
        empresa_usuario__ativo=True,
    )

    profissional_selecionado = None

    if profissional_id:
        profissional_selecionado = get_object_or_404(
            profissionais,
            pk=profissional_id,
        )
        profissionais_calendario = profissionais.filter(
            pk=profissional_selecionado.pk
        )
    else:
        profissionais_calendario = profissionais

    ids_profissionais = list(
        profissionais_calendario.values_list('pk', flat=True)
    )

    inicio_dt = timezone.make_aware(
        datetime.combine(inicio_semana, datetime.min.time())
    )
    fim_dt = timezone.make_aware(
        datetime.combine(fim_semana, datetime.min.time())
    )

    disponibilidades = list(
        _disponibilidades(empresa).filter(
            profissional_id__in=ids_profissionais,
            ativo=True,
        )
    )

    bloqueios = list(
        _bloqueios(empresa).filter(
            profissional_id__in=ids_profissionais,
            ativo=True,
            inicio__lt=fim_dt,
            fim__gt=inicio_dt,
        )
    )

    agendamentos = list(
        _agendamentos(empresa).filter(
            profissional_servico__profissional_id__in=ids_profissionais,
            inicio__lt=fim_dt,
            fim__gt=inicio_dt,
        )
    )

    funcionamentos = list(
        _funcionamentos(empresa).filter(
            ativo=True,
        )
    )

    dias = []

    for offset in range(7):
        data_item = inicio_semana + timedelta(days=offset)

        dia = {
            'data': data_item,
            'hoje': data_item == hoje,
            'funcionamentos': [],
            'disponibilidades': [],
            'eventos': [],
        }

        for funcionamento in funcionamentos:
            if funcionamento.dia_semana != data_item.weekday():
                continue

            ini = timezone.make_aware(
                datetime.combine(
                    data_item,
                    funcionamento.hora_inicio,
                )
            )
            fim = timezone.make_aware(
                datetime.combine(
                    data_item,
                    funcionamento.hora_fim,
                )
            )

            bloco = _agenda_bloco(
                ini,
                fim,
                tipo='funcionamento',
                titulo='Empresa aberta',
                subtitulo=(
                    f'{funcionamento.hora_inicio:%H:%M}–'
                    f'{funcionamento.hora_fim:%H:%M}'
                ),
            )

            if bloco:
                dia['funcionamentos'].append(bloco)

        for disponibilidade in disponibilidades:
            if disponibilidade.dia_semana != data_item.weekday():
                continue

            ini = timezone.make_aware(
                datetime.combine(
                    data_item,
                    disponibilidade.hora_inicio,
                )
            )
            fim = timezone.make_aware(
                datetime.combine(
                    data_item,
                    disponibilidade.hora_fim,
                )
            )

            bloco = _agenda_bloco(
                ini,
                fim,
                tipo='disponibilidade',
                titulo=str(disponibilidade.profissional.usuario),
                subtitulo='Disponível',
            )

            if bloco:
                dia['disponibilidades'].append(bloco)

        for bloqueio in bloqueios:
            inicio_local = timezone.localtime(bloqueio.inicio)
            fim_local = timezone.localtime(bloqueio.fim)

            if not (
                inicio_local.date() <= data_item <
                (
                    fim_local.date()
                    if fim_local.time() != datetime.min.time()
                    else fim_local.date()
                )
            ) and inicio_local.date() != data_item:
                continue

            inicio_bloco = max(
                bloqueio.inicio,
                timezone.make_aware(
                    datetime.combine(
                        data_item,
                        datetime.min.time(),
                    )
                ),
            )

            fim_bloco = min(
                bloqueio.fim,
                timezone.make_aware(
                    datetime.combine(
                        data_item + timedelta(days=1),
                        datetime.min.time(),
                    )
                ),
            )

            bloco = _agenda_bloco(
                inicio_bloco,
                fim_bloco,
                tipo='bloqueio',
                titulo=f'Bloqueio · {bloqueio.profissional.usuario}',
                subtitulo=(
                    bloqueio.motivo
                    or bloqueio.get_tipo_display()
                ),
            )

            if bloco:
                dia['eventos'].append(bloco)

        for agendamento in agendamentos:
            inicio_local = timezone.localtime(agendamento.inicio)

            if inicio_local.date() != data_item:
                continue

            vinculo = agendamento.profissional_servico

            if vinculo.buffer_antes_minutos:
                bloco = _agenda_bloco(
                    agendamento.inicio - timedelta(
                        minutes=vinculo.buffer_antes_minutos
                    ),
                    agendamento.inicio,
                    tipo='buffer',
                    titulo='Buffer',
                    subtitulo='Preparação',
                )

                if bloco:
                    dia['eventos'].append(bloco)

            href = (
                f'/painel/empresas/{empresa.uuid}/agenda/'
                f'agendamentos/{agendamento.pk}/'
            )

            bloco = _agenda_bloco(
                agendamento.inicio,
                agendamento.fim,
                tipo='agendamento',
                titulo=str(agendamento.servico),
                subtitulo=(
                    f'{agendamento.profissional} · '
                    f'{agendamento.get_status_display()}'
                ),
                href=href,
            )

            if bloco:
                dia['eventos'].append(bloco)

            if vinculo.buffer_depois_minutos:
                bloco = _agenda_bloco(
                    agendamento.fim,
                    agendamento.fim + timedelta(
                        minutes=vinculo.buffer_depois_minutos
                    ),
                    tipo='buffer',
                    titulo='Buffer',
                    subtitulo='Intervalo',
                )

                if bloco:
                    dia['eventos'].append(bloco)

        dias.append(dia)

    return render(
        request,
        'painel/agenda/calendario.html',
        {
            'empresa': empresa,
            'dias': dias,
            'inicio_semana': inicio_semana,
            'fim_semana': fim_semana - timedelta(days=1),
            'anterior': inicio_semana - timedelta(days=7),
            'proxima': inicio_semana + timedelta(days=7),
            'hoje': hoje,
            'profissionais': profissionais,
            'profissional_selecionado': profissional_selecionado,
            'funcionamento_configurado': bool(funcionamentos),
        },
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
