from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.models import Empresa
from apps.services.models import Servico

from .models import Agendamento
from .public_forms import ConfirmacaoAgendamentoForm
from .public_services import (
    cancelar_agendamento_cliente,
    criar_agendamento_publico,
    gerar_slots,
    interpretar_inicio,
    nome_publico_profissional,
    obter_vinculo_publico,
    servicos_agendaveis,
    vinculos_agendaveis,
)


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
        Servico.objects,
        slug=slug,
        empresa=empresa,
        ativo=True,
        status=Servico.Status.PUBLICADO,
        excluido_em__isnull=True,
    )


@require_GET
def agenda_empresa(request, empresa_slug):
    empresa = _empresa_publica(empresa_slug)
    servicos = servicos_agendaveis(empresa)
    return render(request, 'publico/agenda/empresa.html', {
        'empresa': empresa,
        'servicos': servicos,
        'agenda_habilitada': empresa.pode_aceitar_agendamentos,
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
        }
        for item in vinculos
    ]
    return render(request, 'publico/agenda/servico.html', {
        'empresa': empresa,
        'servico': servico,
        'profissionais': profissionais,
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
    return redirect('agenda_public:meu_agendamento', uuid=agendamento.uuid)


@login_required
@require_GET
def meus_agendamentos(request):
    itens = Agendamento.objects.filter(cliente=request.user).select_related(
        'profissional_servico__servico__empresa',
        'profissional_servico__profissional__empresa_usuario__usuario',
    ).order_by('-inicio')
    return render(request, 'publico/agenda/meus_agendamentos.html', {
        'agendamentos': itens,
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
