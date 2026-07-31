from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.permissions import usuario_e_master, usuario_tem_permissao
from apps.core.seo.page_builders import event_seo

from .forms import EventoForm
from .models import Evento, HistoricoEvento, InteresseEvento
from .permissions import eventos_do_usuario, pode_editar_evento


def _require(user, code):
    if not usuario_tem_permissao(user, code):
        raise PermissionDenied(f'Você não possui a permissão necessária: {code}.')


@login_required
def painel_lista(request):
    _require(request.user, 'events.acessar')
    eventos = list(eventos_do_usuario(request.user).annotate(
        total_interessados=Count('interesses', filter=Q(interesses__ativo=True)),
    ))
    for evento in eventos:
        evento.pode_editar_no_painel = pode_editar_evento(request.user, evento)
    return render(request, 'painel/eventos/lista.html', {
        'eventos': eventos, 'titulo': 'Eventos',
        'pode_criar': (
            usuario_tem_permissao(request.user, 'events.criar_proprio')
            or usuario_tem_permissao(request.user, 'events.criar_empresa')
        ),
    })


@login_required
def painel_criar(request):
    if not (usuario_tem_permissao(request.user, 'events.criar_proprio')
            or usuario_tem_permissao(request.user, 'events.criar_empresa')):
        raise PermissionDenied('Você não possui permissão para criar eventos.')
    form = EventoForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        evento = form.save(commit=False)
        evento.criador_registro = request.user
        if not (usuario_e_master(request.user) or usuario_tem_permissao(request.user, 'events.atribuir_responsavel')):
            evento.proprietario = evento.responsavel_edicao = request.user
        evento.save()
        HistoricoEvento.objects.create(evento=evento, usuario=request.user, acao=HistoricoEvento.Acao.CRIADO)
        messages.success(request, 'Evento criado como rascunho.')
        return redirect('painel:evento_detalhe', uuid=evento.uuid)
    return render(request, 'painel/eventos/form.html', {'form': form, 'titulo': 'Novo evento'})


@login_required
def painel_detalhe(request, uuid):
    _require(request.user, 'events.acessar')
    evento = get_object_or_404(eventos_do_usuario(request.user), uuid=uuid)
    hoje = timezone.localdate()
    ativos = evento.interesses.filter(ativo=True)
    metricas = {
        'total': ativos.count(),
        'hoje': ativos.filter(criado_em__date=hoje).count(),
        'sete_dias': ativos.filter(criado_em__date__gte=hoje - timedelta(days=6)).count(),
        'trinta_dias': ativos.filter(criado_em__date__gte=hoje - timedelta(days=29)).count(),
        'cancelados': evento.interesses.filter(ativo=False).count(),
        'dias_restantes': max(0, (evento.inicio.date() - hoje).days),
    }
    return render(request, 'painel/eventos/detalhe.html', {
        'evento': evento, 'metricas': metricas, 'pode_editar': pode_editar_evento(request.user, evento),
        'pode_ver_interessados': usuario_tem_permissao(request.user, 'events.gerenciar_interessados'),
        'pode_ver_metricas': usuario_tem_permissao(request.user, 'events.visualizar_metricas'),
        'acoes_status': [
            (status, label) for status, label, permission in (
                (Evento.Status.EM_ANALISE, 'Enviar para análise', 'events.enviar_analise'),
                (Evento.Status.APROVADO, 'Aprovar', 'events.aprovar'),
                (Evento.Status.PUBLICADO, 'Publicar', 'events.publicar'),
                (Evento.Status.REJEITADO, 'Rejeitar', 'events.rejeitar'),
                (Evento.Status.PAUSADO, 'Pausar', 'events.pausar'),
                (Evento.Status.ARQUIVADO, 'Arquivar', 'events.arquivar'),
                (Evento.Status.RASCUNHO, 'Restaurar como rascunho', 'events.restaurar'),
            ) if usuario_tem_permissao(request.user, permission)
        ],
    })


@login_required
def painel_editar(request, uuid):
    evento = get_object_or_404(eventos_do_usuario(request.user), uuid=uuid)
    if not pode_editar_evento(request.user, evento):
        raise PermissionDenied('Evento fora do seu escopo de edição.')
    original = (evento.empresa_promotora_id, evento.proprietario_id, evento.responsavel_edicao_id, evento.permitir_interesse)
    form = EventoForm(request.POST or None, request.FILES or None, instance=evento, user=request.user)
    if request.method == 'POST' and form.is_valid():
        evento = form.save()
        current = (evento.empresa_promotora_id, evento.proprietario_id, evento.responsavel_edicao_id, evento.permitir_interesse)
        HistoricoEvento.objects.create(
            evento=evento, usuario=request.user, acao=HistoricoEvento.Acao.ALTERADO,
            dados={'associacao_alterada': original != current},
        )
        messages.success(request, 'Evento atualizado.')
        return redirect('painel:evento_detalhe', uuid=evento.uuid)
    return render(request, 'painel/eventos/form.html', {'form': form, 'evento': evento, 'titulo': 'Editar evento'})


@login_required
@require_POST
def painel_status(request, uuid):
    evento = get_object_or_404(eventos_do_usuario(request.user), uuid=uuid)
    novo = request.POST.get('status')
    permission = {
        Evento.Status.EM_ANALISE: 'events.enviar_analise',
        Evento.Status.APROVADO: 'events.aprovar',
        Evento.Status.PUBLICADO: 'events.publicar',
        Evento.Status.REJEITADO: 'events.rejeitar',
        Evento.Status.PAUSADO: 'events.pausar',
        Evento.Status.ARQUIVADO: 'events.arquivar',
        Evento.Status.RASCUNHO: 'events.restaurar',
    }.get(novo)
    if not permission or not usuario_tem_permissao(request.user, permission):
        raise PermissionDenied
    anterior = evento.status
    evento.status = novo
    evento.save(update_fields=['status', 'publicado_em', 'atualizado_em'])
    HistoricoEvento.objects.create(evento=evento, usuario=request.user, acao=HistoricoEvento.Acao.STATUS,
                                   dados={'anterior': anterior, 'novo': novo})
    return redirect('painel:evento_detalhe', uuid=evento.uuid)


@login_required
def painel_interessados(request, uuid):
    _require(request.user, 'events.gerenciar_interessados')
    evento = get_object_or_404(eventos_do_usuario(request.user), uuid=uuid)
    itens = evento.interesses.select_related('usuario')
    termo = request.GET.get('q', '').strip()[:100]
    periodo = request.GET.get('periodo', '')
    if termo:
        itens = itens.filter(Q(usuario__first_name__icontains=termo) | Q(usuario__nome_exibicao__icontains=termo))
    if periodo in {'7', '30'}:
        itens = itens.filter(criado_em__gte=timezone.now() - timedelta(days=int(periodo)))
    page = Paginator(itens, 25).get_page(request.GET.get('page'))
    return render(request, 'painel/eventos/interessados.html', {'evento': evento, 'page_obj': page})


@login_required
def painel_metricas(request, uuid):
    _require(request.user, 'events.visualizar_metricas')
    evento = get_object_or_404(eventos_do_usuario(request.user), uuid=uuid)
    rows = evento.interesses.values('origem', 'ativo').annotate(total=Count('id')).order_by()
    created = evento.interesses.annotate(data=TruncDate('criado_em')).values('data').annotate(total=Count('id')).order_by('data')
    cancelled = evento.interesses.filter(cancelado_em__isnull=False).annotate(
        data=TruncDate('cancelado_em'),
    ).values('data').annotate(total=Count('id')).order_by('data')
    grouped = defaultdict(lambda: {'novos': 0, 'cancelamentos': 0, 'acumulado': 0})
    for row in created:
        grouped[row['data']]['novos'] = row['total']
    for row in cancelled:
        grouped[row['data']]['cancelamentos'] = row['total']
    running = 0
    for data in sorted(grouped):
        running += grouped[data]['novos'] - grouped[data]['cancelamentos']
        grouped[data]['acumulado'] = running
    return render(request, 'painel/eventos/metricas.html', {'evento': evento, 'origens': rows, 'evolucao': dict(grouped)})


def publico_detalhe(request, slug):
    evento = get_object_or_404(Evento.objects, slug=slug, status=Evento.Status.PUBLICADO, publico=True)
    interesse = None
    if request.user.is_authenticated:
        interesse = evento.interesses.filter(usuario=request.user, ativo=True).first()
    return render(request, 'publico/eventos/detalhe.html', {
        'evento': evento, 'interesse_ativo': bool(interesse),
        'total_interessados': evento.interesses.filter(ativo=True).count(),
        'seo': event_seo(request, evento),
    })


@login_required
@require_POST
def alternar_interesse(request, slug):
    with transaction.atomic():
        evento = get_object_or_404(
            Evento.objects.select_for_update(), slug=slug,
            status=Evento.Status.PUBLICADO, publico=True,
        )
        if not evento.aceita_novos_interesses:
            raise PermissionDenied('Este evento não aceita novos interesses.')
        item, created = InteresseEvento.objects.select_for_update().get_or_create(
            evento=evento, usuario=request.user,
            defaults={'ativo': True, 'origem': InteresseEvento.Origem.WEB},
        )
        if not created:
            item.ativo = not item.ativo
            item.cancelado_em = None if item.ativo else timezone.now()
            item.save(update_fields=['ativo', 'cancelado_em', 'atualizado_em'])
        HistoricoEvento.objects.create(
            evento=evento, usuario=request.user,
            acao=HistoricoEvento.Acao.INTERESSE if item.ativo else HistoricoEvento.Acao.INTERESSE_REMOVIDO,
            origem='WEB',
        )
        total = evento.interesses.filter(ativo=True).count()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'interesse_ativo': item.ativo, 'total_interessados': total})
    return redirect(evento.get_absolute_url())
