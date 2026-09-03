from calendar import monthrange
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from apps.services.models import Servico

from .forms import (
    AgendamentoInternoForm,
    AgendamentoOperacionalForm,
    AgendaConfiguracaoForm,
    BloqueioForm,
    DisponibilidadeForm,
    DisponibilidadeSemanalForm,
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
    AgendaEmpresa,
)
from .dashboard import construir_central_agenda
from .operations import (
    abrir_agenda_empresa, fechar_agenda_empresa, solicitar_liberacao_agenda,
)
from .permissions import (
    agenda_empresa_configuracao_required,
    agenda_empresa_required,
)
from .public_services import resumo_operacional_empresa
from .services import (
    TRANSICOES_STATUS, alterar_status_agendamento, criar_agendamento_interno,
    reagendar_agendamento,
)


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


def _disponibilidades_semanais(empresa):
    return AgendaDisponibilidade.objects.filter(
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
@agenda_empresa_configuracao_required
def dashboard(request, empresa):
    return render(request, 'painel/agenda/dashboard.html', {
        'empresa': empresa,
        'central': construir_central_agenda(empresa),
        'agenda_resumo': resumo_operacional_empresa(empresa),
    })


@require_POST
@login_required
@agenda_empresa_configuracao_required
def agenda_estado(request, empresa):
    acao = request.POST.get('acao')
    try:
        if acao == 'abrir':
            if not empresa.pode_aceitar_agendamentos:
                solicitar_liberacao_agenda(empresa)
                messages.info(
                    request,
                    'Estamos liberando sua agenda online. Você poderá ativá-la assim que a liberação for concluída.',
                )
            else:
                abrir_agenda_empresa(empresa=empresa, usuario=request.user)
                messages.success(request, 'Sua agenda está ativa para novos agendamentos.')
        elif acao == 'fechar':
            fechar_agenda_empresa(empresa=empresa, usuario=request.user)
            messages.success(request, 'Agenda desativada. Seus agendamentos existentes foram preservados.')
        else:
            raise ValidationError('Ação inválida para a Agenda.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('painel:empresa_agenda', uuid=empresa.uuid)


@login_required
@agenda_empresa_configuracao_required
def agenda_configuracoes(request, empresa):
    configuracao, _ = AgendaEmpresa.objects.get_or_create(empresa=empresa)
    form = AgendaConfiguracaoForm(request.POST or None, instance=configuracao)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.atualizado_por = request.user
        item.save()
        messages.success(request, 'Configurações da Agenda atualizadas.')
        return redirect('painel:agenda_configuracoes', uuid=empresa.uuid)
    return render(request, 'painel/agenda/configuracoes.html', {
        'empresa': empresa, 'form': form, 'configuracao': configuracao,
    })


@login_required
@agenda_empresa_configuracao_required
def vinculo_lista(request, empresa):
    return render(request, 'painel/agenda/vinculo_lista.html', {
        'empresa': empresa, 'itens': _vinculos(empresa)
    })


@login_required
@agenda_empresa_configuracao_required
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
@agenda_empresa_configuracao_required
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
@agenda_empresa_configuracao_required
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
@agenda_empresa_configuracao_required
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
@agenda_empresa_configuracao_required
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

    modo = request.GET.get('modo', 'semana')
    if modo not in {'dia', 'semana', 'mes'}:
        modo = 'semana'
    if modo == 'dia':
        inicio_periodo, fim_periodo = referencia, referencia + timedelta(days=1)
        anterior, proxima = referencia - timedelta(days=1), referencia + timedelta(days=1)
    elif modo == 'mes':
        inicio_periodo = referencia.replace(day=1)
        fim_periodo = inicio_periodo + timedelta(
            days=monthrange(referencia.year, referencia.month)[1]
        )
        anterior = (inicio_periodo - timedelta(days=1)).replace(day=1)
        proxima = fim_periodo
    else:
        inicio_periodo = referencia - timedelta(days=referencia.weekday())
        fim_periodo = inicio_periodo + timedelta(days=7)
        anterior, proxima = inicio_periodo - timedelta(days=7), inicio_periodo + timedelta(days=7)

    profissional_id = request.GET.get('profissional', '').strip()
    servico_id = request.GET.get('servico', '').strip()

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

    servicos = Servico.objects.filter(
        profissionais_agenda__profissional__empresa_usuario__empresa=empresa,
    ).distinct().order_by('titulo')
    servico_selecionado = None
    if servico_id:
        servico_selecionado = get_object_or_404(servicos, pk=servico_id)

    inicio_dt = timezone.make_aware(
        datetime.combine(inicio_periodo, datetime.min.time())
    )
    fim_dt = timezone.make_aware(
        datetime.combine(fim_periodo, datetime.min.time())
    )

    disponibilidades_semanais = list(
        _disponibilidades_semanais(empresa).filter(
            profissional_id__in=ids_profissionais,
            ativo=True,
        )
    )
    disponibilidades_data = list(_disponibilidades(empresa).filter(
        profissional_id__in=ids_profissionais,
        ativo=True,
        data__gte=inicio_periodo,
        data__lt=fim_periodo,
    ))

    bloqueios = list(
        _bloqueios(empresa).filter(
            profissional_id__in=ids_profissionais,
            ativo=True,
            inicio__lt=fim_dt,
            fim__gt=inicio_dt,
        )
    )

    agendamentos_qs = _agendamentos(empresa).filter(
            profissional_servico__profissional_id__in=ids_profissionais,
            inicio__lt=fim_dt,
            fim__gt=inicio_dt,
        )
    if servico_selecionado:
        agendamentos_qs = agendamentos_qs.filter(
            profissional_servico__servico=servico_selecionado,
        )
    agendamentos = list(agendamentos_qs)

    funcionamentos = list(
        _funcionamentos(empresa).filter(
            ativo=True,
        )
    )

    dias = []

    for offset in range((fim_periodo - inicio_periodo).days):
        data_item = inicio_periodo + timedelta(days=offset)

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

        profissionais_com_excecao = {
            item.profissional_id for item in disponibilidades_data
            if item.data == data_item
        }
        disponibilidades_dia = [
            item for item in disponibilidades_data if item.data == data_item
        ] + [
            item for item in disponibilidades_semanais
            if item.dia_semana == data_item.weekday()
            and item.profissional_id not in profissionais_com_excecao
        ]
        for disponibilidade in disponibilidades_dia:

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
            'inicio_semana': inicio_periodo,
            'fim_semana': fim_periodo - timedelta(days=1),
            'anterior': anterior,
            'proxima': proxima,
            'hoje': hoje,
            'modo': modo,
            'profissionais': profissionais,
            'profissional_selecionado': profissional_selecionado,
            'servicos': servicos,
            'servico_selecionado': servico_selecionado,
            'funcionamento_configurado': bool(funcionamentos),
        },
    )



@login_required
@agenda_empresa_configuracao_required
def horarios_lista(request, empresa):
    if request.method == 'POST' and request.POST.get('acao') == 'copiar_segunda':
        profissional = get_object_or_404(
            _profissionais(empresa).filter(ativo=True, empresa_usuario__ativo=True),
            pk=request.POST.get('profissional'),
        )
        destinos = {
            int(valor) for valor in request.POST.getlist('dias')
            if valor.isdigit() and 0 < int(valor) <= 6
        }
        origem = list(_disponibilidades_semanais(empresa).filter(
            profissional=profissional, dia_semana=0, ativo=True,
        ))
        if not origem:
            messages.error(request, 'Defina os horários de segunda-feira antes de copiar.')
        elif not destinos:
            messages.error(request, 'Escolha pelo menos um dia para receber os horários.')
        else:
            with transaction.atomic():
                _disponibilidades_semanais(empresa).filter(
                    profissional=profissional, dia_semana__in=destinos,
                ).delete()
                for dia in destinos:
                    for item in origem:
                        AgendaDisponibilidade.objects.create(
                            profissional=profissional,
                            dia_semana=dia,
                            hora_inicio=item.hora_inicio,
                            hora_fim=item.hora_fim,
                            ativo=True,
                        )
            messages.success(request, 'Horários de segunda-feira copiados.')
        return redirect('painel:agenda_horarios', uuid=empresa.uuid)
    return render(request, 'painel/agenda/horarios.html', {
        'empresa': empresa,
        'semanais': _disponibilidades_semanais(empresa).order_by(
            'profissional_id', 'dia_semana', 'hora_inicio',
        ),
        'excecoes': _disponibilidades(empresa).order_by('data', 'hora_inicio'),
        'profissionais': _profissionais(empresa).filter(
            ativo=True, empresa_usuario__ativo=True,
        ),
        'dias_copia': AgendaDisponibilidade.DiaSemana.choices[1:],
    })


disponibilidade_lista = horarios_lista


@login_required
@agenda_empresa_configuracao_required
def disponibilidade_semanal_form(request, empresa, pk=None):
    instance = (
        get_object_or_404(_disponibilidades_semanais(empresa), pk=pk)
        if pk else None
    )
    form = DisponibilidadeSemanalForm(
        request.POST or None, instance=instance, empresa=empresa,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Horário semanal salvo com sucesso.')
        return redirect('painel:agenda_horarios', uuid=empresa.uuid)
    return render(request, 'painel/agenda/form.html', {
        'empresa': empresa,
        'form': form,
        'titulo': 'Editar horário semanal' if instance else 'Novo horário semanal',
        'voltar_url': 'painel:agenda_horarios',
    })


@require_POST
@login_required
@agenda_empresa_configuracao_required
def disponibilidade_semanal_status(request, empresa, pk):
    objeto = get_object_or_404(_disponibilidades_semanais(empresa), pk=pk)
    return _alterar_ativo(
        request, objeto=objeto,
        ativo=request.POST.get('ativo') == '1',
        redirect_name='painel:agenda_horarios',
    )


@login_required
@agenda_empresa_configuracao_required
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
@agenda_empresa_configuracao_required
def disponibilidade_status(request, empresa, pk):
    objeto = get_object_or_404(_disponibilidades(empresa), pk=pk)
    return _alterar_ativo(
        request, objeto=objeto, ativo=request.POST.get('ativo') == '1',
        redirect_name='painel:agenda_disponibilidade_lista'
    )


@login_required
@agenda_empresa_configuracao_required
def bloqueio_lista(request, empresa):
    return render(request, 'painel/agenda/bloqueio_lista.html', {
        'empresa': empresa, 'itens': _bloqueios(empresa).order_by('-inicio')
    })


@login_required
@agenda_empresa_configuracao_required
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
@agenda_empresa_configuracao_required
def bloqueio_status(request, empresa, pk):
    objeto = get_object_or_404(_bloqueios(empresa), pk=pk)
    return _alterar_ativo(
        request, objeto=objeto, ativo=request.POST.get('ativo') == '1',
        redirect_name='painel:agenda_bloqueio_lista'
    )


@login_required
@agenda_empresa_required
def agendamento_lista(request, empresa):
    itens = _agendamentos(empresa).order_by('-inicio')
    termo = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    if termo:
        itens = itens.filter(
            Q(cliente__first_name__icontains=termo)
            | Q(cliente__last_name__icontains=termo)
            | Q(cliente__email__icontains=termo)
            | Q(profissional_servico__servico__titulo__icontains=termo)
        )
    if status in Agendamento.Status.values:
        itens = itens.filter(status=status)
    if request.GET.get('profissional'):
        profissional = get_object_or_404(
            _profissionais(empresa), pk=request.GET['profissional'],
        )
        itens = itens.filter(profissional_servico__profissional=profissional)
    if request.GET.get('servico'):
        servico = get_object_or_404(
            Servico.objects.filter(empresa=empresa), pk=request.GET['servico'],
        )
        itens = itens.filter(profissional_servico__servico=servico)
    if request.GET.get('data_inicio'):
        itens = itens.filter(inicio__date__gte=request.GET['data_inicio'])
    if request.GET.get('data_fim'):
        itens = itens.filter(inicio__date__lte=request.GET['data_fim'])
    pagina = Paginator(itens, 25).get_page(request.GET.get('page'))
    filtros = request.GET.copy()
    filtros.pop('page', None)
    return render(request, 'painel/agenda/agendamento_lista.html', {
        'empresa': empresa, 'itens': pagina, 'pagina': pagina,
        'profissionais': _profissionais(empresa).filter(ativo=True),
        'servicos': Servico.objects.filter(empresa=empresa).order_by('titulo'),
        'status_choices': Agendamento.Status,
        'filtros_query': filtros.urlencode(),
    })


@login_required
@agenda_empresa_required
def agendamento_criar(request, empresa):
    form = AgendamentoInternoForm(request.POST or None, empresa=empresa)
    if request.method == 'POST' and form.is_valid():
        cliente = get_user_model().objects.filter(
            email__iexact=form.cleaned_data['cliente_email'], is_active=True,
        ).first()
        if cliente is None:
            form.add_error('cliente_email', 'Cliente ativo não encontrado com este e-mail.')
    if request.method == 'POST' and form.is_valid():
        try:
            item = criar_agendamento_interno(
                empresa=empresa, vinculo_id=form.cleaned_data['vinculo'].pk,
                cliente=cliente, inicio=form.cleaned_data['inicio'],
                usuario=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        else:
            messages.success(request, 'Agendamento criado com sucesso.')
            return redirect('painel:agenda_agendamento_detalhe', uuid=empresa.uuid, pk=item.pk)
    return render(request, 'painel/agenda/agendamento_form.html', {
        'empresa': empresa, 'form': form, 'titulo': 'Novo agendamento',
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
        'historico': item.historico.select_related('realizado_por'),
    })


@login_required
@agenda_empresa_required
def agendamento_reagendar(request, empresa, pk):
    item = get_object_or_404(_agendamentos(empresa), pk=pk)
    form = AgendamentoOperacionalForm(
        request.POST or None, empresa=empresa,
        initial={'vinculo': item.profissional_servico_id,
                 'inicio': timezone.localtime(item.inicio).strftime('%Y-%m-%dT%H:%M')},
    )
    if request.method == 'POST' and form.is_valid():
        try:
            reagendar_agendamento(
                empresa=empresa, agendamento_id=item.pk,
                vinculo_id=form.cleaned_data['vinculo'].pk,
                inicio=form.cleaned_data['inicio'], usuario=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        else:
            messages.success(request, 'Agendamento reagendado com sucesso.')
            return redirect('painel:agenda_agendamento_detalhe', uuid=empresa.uuid, pk=item.pk)
    return render(request, 'painel/agenda/agendamento_form.html', {
        'empresa': empresa, 'form': form, 'titulo': 'Reagendar', 'item': item,
    })


@require_POST
@login_required
@agenda_empresa_required
def agendamento_status(request, empresa, pk):
    novo_status = request.POST.get('status', '')
    try:
        alterar_status_agendamento(
            empresa=empresa, agendamento_id=pk, novo_status=novo_status,
            usuario=request.user,
        )
    except Agendamento.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    else:
        messages.success(request, 'Status do agendamento atualizado.')
    return redirect('painel:agenda_agendamento_detalhe', uuid=empresa.uuid, pk=pk)
