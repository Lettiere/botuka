from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.models import Empresa
from apps.services.models import Servico

from .models import Agendamento, AgendaBloqueio, AgendaDisponibilidade, AgendaProfissional
from .public_forms import ConfirmacaoAgendamentoForm
from .public_services import (
    cancelar_agendamento_cliente,
    calendario_servico_publico,
    criar_agendamento_publico,
    empresas_agendaveis,
    gerar_slots,
    interpretar_inicio,
    nome_publico_profissional,
    obter_vinculo_publico,
    pesquisar_agenda_publica,
    sugestoes_agenda_publica,
    servicos_agendaveis,
    vinculos_agendaveis,
)


@require_GET
def agenda_home(request):
    resultados = pesquisar_agenda_publica(request.GET)
    return render(request, 'publico/agenda/home.html', {
        'empresas': empresas_agendaveis(),
        'resultados': resultados,
        'busca_ativa': any(request.GET.get(key) for key in (
            'q', 'localizacao', 'modalidade', 'data', 'horario',
            'horario_aproximado', 'periodo',
            'profissional', 'empresa',
        )),
        'filtros': request.GET,
    })


@require_GET
def autocomplete(request):
    return JsonResponse({'sugestoes': sugestoes_agenda_publica(request.GET.get('q'))})


def _empresa_publica(slug):
    return get_object_or_404(
        Empresa.objects,
        slug=slug,
        ativo=True,
        perfil_publico=True,
        status=Empresa.Status.ATIVA,
        excluido_em__isnull=True,
    )


def _servico_publico(empresa, slug):
    return get_object_or_404(
        Servico.objects.publicamente_visiveis(),
        slug=slug,
        empresa=empresa,
    )


@require_GET
def agenda_empresa(request, empresa_slug):
    empresa = _empresa_publica(empresa_slug)
    servicos = servicos_agendaveis(empresa)
    vinculos = vinculos_agendaveis(empresa=empresa)
    profissionais = {}
    for vinculo in vinculos:
        item = profissionais.setdefault(vinculo.profissional_id, {
            'item': vinculo.profissional,
            'nome': nome_publico_profissional(vinculo.profissional),
            'servicos': [],
        })
        item['servicos'].append(vinculo.servico)
    return render(request, 'publico/agenda/empresa.html', {
        'empresa': empresa,
        'servicos': servicos,
        'profissionais': list(profissionais.values()),
        'agenda_habilitada': empresa.pode_aceitar_agendamentos,
    })


@require_GET
def agenda_profissional(request, empresa_slug, profissional_uuid):
    empresa = _empresa_publica(empresa_slug)
    vinculos = [item for item in vinculos_agendaveis(empresa=empresa)
                if str(item.profissional.uuid) == str(profissional_uuid)]
    if not vinculos:
        raise Http404
    profissional = vinculos[0].profissional
    hoje = timezone.localdate()
    calendarios = [
        {'vinculo': item, 'servico': item.servico,
         'calendario': calendario_servico_publico(
             servico=item.servico, inicio=hoje, vinculo_uuid=item.uuid,
         )}
        for item in vinculos
    ]
    return render(request, 'publico/agenda/perfil_profissional.html', {
        'empresa': empresa,
        'profissional': profissional,
        'profissional_nome': nome_publico_profissional(profissional),
        'calendarios': calendarios,
    })


@require_GET
def agenda_servico(request, empresa_slug, servico_slug):
    empresa = _empresa_publica(empresa_slug)
    servico = _servico_publico(empresa, servico_slug)
    vinculos = vinculos_agendaveis(empresa=empresa, servico=servico)
    profissionais = [
        {
            'uuid': item.uuid,
            'nome': nome_publico_profissional(item.profissional),
            'duracao': item.duracao_minutos,
            'item': item.profissional,
        }
        for item in vinculos
    ]
    hoje = timezone.localdate()
    try:
        inicio = date.fromisoformat(request.GET.get('inicio', ''))
    except ValueError:
        inicio = hoje
    inicio = max(inicio, hoje)
    profissional_uuid = request.GET.get('profissional') or None
    calendario = calendario_servico_publico(
        servico=servico, inicio=inicio, vinculo_uuid=profissional_uuid,
    )
    return render(request, 'publico/agenda/servico.html', {
        'empresa': empresa,
        'servico': servico,
        'profissionais': profissionais,
        'profissional_selecionado': profissional_uuid or 'qualquer',
        'calendario': calendario,
        'inicio_calendario': inicio,
        'semana_anterior': max(hoje, inicio - timedelta(days=7)),
        'proxima_semana': inicio + timedelta(days=7),
    })


@require_GET
def slots(request, vinculo_uuid):
    try:
        vinculo = obter_vinculo_publico(vinculo_uuid)
    except ValidationError as exc:
        raise Http404 from exc
    try:
        data = date.fromisoformat(request.GET.get('data', ''))
        horarios = gerar_slots(vinculo, data)
    except (ValidationError, ValueError):
        return JsonResponse({'erro': 'Data inválida.'}, status=400)
    return JsonResponse({
        'data': data.isoformat(),
        'slots': [
            {
                'horario': item.strftime('%H:%M'),
                'inicio': item.isoformat(),
            }
            for item in horarios
        ],
    })


def confirmar(request, vinculo_uuid):
    try:
        vinculo = obter_vinculo_publico(vinculo_uuid)
    except ValidationError as exc:
        raise Http404 from exc
    try:
        inicio_valor = request.POST.get('inicio') or request.GET.get('inicio')
        inicio = interpretar_inicio(inicio_valor)
    except ValidationError as exc:
        return render(request, 'publico/agenda/erro.html', {
            'mensagem': '; '.join(exc.messages)
        }, status=400)
    form = ConfirmacaoAgendamentoForm(
        request.POST or {'inicio': inicio.isoformat()}
    )
    contexto = {
        'empresa': vinculo.servico.empresa,
        'servico': vinculo.servico,
        'vinculo': vinculo,
        'profissional_nome': nome_publico_profissional(vinculo.profissional),
        'inicio': inicio,
        'form': form,
        'next_url': request.get_full_path(),
    }
    if request.method == 'GET':
        if inicio not in gerar_slots(vinculo, inicio.date()):
            contexto['erro'] = 'Este horário não está mais disponível.'
        return render(request, 'publico/agenda/confirmar.html', contexto)
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido.'}, status=405)
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
    if not form.is_valid():
        contexto['erro'] = 'Horário inválido.'
        return render(request, 'publico/agenda/confirmar.html', contexto, status=400)
    try:
        agendamento = criar_agendamento_publico(
            vinculo_uuid=vinculo_uuid,
            cliente=request.user,
            inicio=form.cleaned_data['inicio'],
        )
    except ValidationError as exc:
        contexto['erro'] = '; '.join(exc.messages)
        return render(request, 'publico/agenda/confirmar.html', contexto, status=409)
    messages.success(request, 'Agendamento solicitado com sucesso.')
    url = reverse('agenda_public:meu_agendamento', kwargs={'uuid': agendamento.uuid})
    return redirect(f'{url}?criado=1')


@login_required
@require_GET
def meus_agendamentos(request):
    itens = list(Agendamento.objects.filter(cliente=request.user).select_related(
        'profissional_servico__servico__empresa',
        'profissional_servico__profissional__empresa_usuario__usuario',
    ).order_by('-inicio'))
    agora = timezone.now()
    return render(request, 'publico/agenda/meus_agendamentos.html', {
        'agendamentos': itens,
        'proximos': [item for item in itens if item.inicio >= agora and item.status not in (Agendamento.Status.CANCELADO, Agendamento.Status.CONCLUIDO, Agendamento.Status.FALTOU)],
        'passados': [item for item in itens if item.status in (Agendamento.Status.CONCLUIDO, Agendamento.Status.FALTOU) or (item.inicio < agora and item.status != Agendamento.Status.CANCELADO)],
        'cancelados': [item for item in itens if item.status == Agendamento.Status.CANCELADO],
    })


@login_required
@require_GET
def minha_agenda_profissional(request):
    profissionais = AgendaProfissional.objects.filter(
        models.Q(usuario_autonomo=request.user)
        | models.Q(empresa_usuario__usuario=request.user),
        ativo=True,
    ).select_related('empresa_usuario__empresa')
    agendamentos = Agendamento.objects.filter(
        profissional_servico__profissional__in=profissionais,
    ).select_related(
        'cliente', 'profissional_servico__servico',
        'profissional_servico__profissional',
    ).order_by('inicio')
    hoje = timezone.localdate()
    return render(request, 'publico/agenda/profissional.html', {
        'profissionais': profissionais,
        'hoje': [item for item in agendamentos if timezone.localdate(item.inicio) == hoje],
        'proximos': [item for item in agendamentos if item.inicio >= timezone.now()][:20],
        'disponibilidades': AgendaDisponibilidade.objects.filter(
            profissional__in=profissionais, ativo=True,
        ).select_related('profissional'),
        'bloqueios': AgendaBloqueio.objects.filter(
            profissional__in=profissionais, ativo=True, fim__gte=timezone.now(),
        ).select_related('profissional').order_by('inicio')[:10],
    })


@login_required
@require_GET
def meu_agendamento(request, uuid):
    item = get_object_or_404(
        Agendamento.objects.select_related(
            'profissional_servico__servico__empresa',
            'profissional_servico__profissional__empresa_usuario__usuario',
        ),
        uuid=uuid,
        cliente=request.user,
    )
    return render(request, 'publico/agenda/detalhe.html', {
        'item': item,
        'profissional_nome': nome_publico_profissional(item.profissional),
        'pode_cancelar': item.status in (
            Agendamento.Status.PENDENTE,
            Agendamento.Status.CONFIRMADO,
        ),
    })


@require_POST
@login_required
def cancelar(request, uuid):
    get_object_or_404(Agendamento, uuid=uuid, cliente=request.user)
    try:
        cancelar_agendamento_cliente(
            agendamento_uuid=uuid,
            cliente=request.user,
        )
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    else:
        messages.success(request, 'Agendamento cancelado.')
    return redirect('agenda_public:meu_agendamento', uuid=uuid)
