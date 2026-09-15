from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.organizations.permissions import empresas_gerenciaveis_para_usuario
from apps.accounts.permissions import usuario_e_master
from apps.payments.gateways import GatewayUnavailable
from apps.payments.services import processar_pagamento

from .forms import (CampanhaForm, CriativoForm, PlanoPublicitarioForm,
                    PosicionamentoForm, SegmentacaoForm)
from .models import (Campanha, CampanhaSegmentacao, EntregaPublicidade,
                     PlanoPublicitario, Posicionamento)
from .permissions import pode_gerenciar_campanha
from .services import (aprovar_campanha, calcular_preco, cancelar_campanha,
                       contratar_campanha, moderar_campanha, registrar_clique,
                       sincronizar_status_pagamento, url_destino_segura,
                       validar_disponibilidade)


@login_required
def campanha_lista(request):
    empresas = empresas_gerenciaveis_para_usuario(request.user)
    campanhas = (Campanha.objects.filter(empresa__in=empresas)
                 .select_related('empresa', 'plano', 'contratacao__cobranca')
                 .prefetch_related('posicionamentos', 'contratacao__cobranca__pagamentos'))
    return render(request, 'advertising/campanha_lista.html', {'campanhas': campanhas})


@login_required
def campanha_criar(request):
    form = CampanhaForm(request.POST or None, usuario=request.user)
    if request.method == 'POST' and form.is_valid():
        campanha = form.save()
        return redirect('advertising:campanha_detalhe', uuid=campanha.uuid)
    return render(request, 'advertising/campanha_form.html', {'form': form})


@login_required
def campanha_editar(request, uuid):
    campanha = get_object_or_404(Campanha, uuid=uuid, status=Campanha.Status.RASCUNHO)
    if not pode_gerenciar_campanha(request.user, campanha):
        raise PermissionDenied
    form = CampanhaForm(request.POST or None, instance=campanha, usuario=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('advertising:campanha_detalhe', uuid=uuid)
    return render(request, 'advertising/campanha_form.html', {'form': form, 'campanha': campanha})


@login_required
def campanha_detalhe(request, uuid):
    campanha = get_object_or_404(Campanha.objects.select_related(
        'empresa', 'plano', 'contratacao__cobranca'), uuid=uuid)
    if not pode_gerenciar_campanha(request.user, campanha):
        raise PermissionDenied
    metricas = campanha.entregas.aggregate(impressoes=Count('id'), cliques=Count('id', filter=Q(clicado_em__isnull=False)))
    resumo = None
    if campanha.status == Campanha.Status.RASCUNHO:
        dias, valor_diario, total = calcular_preco(campanha)
        try:
            validar_disponibilidade(campanha)
            disponibilidade = True
        except ValidationError as exc:
            disponibilidade = exc.messages
        resumo = {'dias': dias, 'valor_diario': valor_diario, 'total': total,
                  'disponibilidade': disponibilidade}
    return render(request, 'advertising/campanha_detalhe.html', {
        'campanha': campanha, 'metricas': metricas, 'resumo': resumo,
        'criativo_form': CriativoForm(campanha=campanha), 'segmentacao_form': SegmentacaoForm(),
        'usuario_master': usuario_e_master(request.user),
        'pagamento_local_disponivel': (
            settings.DEBUG and settings.PAYMENTS_USE_FAKE_GATEWAYS
        ),
    })


@login_required
@require_POST
def campanha_adicionar_criativo(request, uuid):
    campanha = get_object_or_404(Campanha, uuid=uuid, status=Campanha.Status.RASCUNHO)
    if not pode_gerenciar_campanha(request.user, campanha):
        raise PermissionDenied
    form = CriativoForm(request.POST, request.FILES, campanha=campanha)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
    criativo = form.save(commit=False)
    criativo.campanha = campanha
    criativo.full_clean()
    criativo.save()
    return redirect('advertising:campanha_detalhe', uuid=uuid)


@login_required
@require_POST
def campanha_segmentar(request, uuid):
    campanha = get_object_or_404(Campanha, uuid=uuid, status=Campanha.Status.RASCUNHO)
    if not pode_gerenciar_campanha(request.user, campanha):
        raise PermissionDenied
    segmentacao, _ = CampanhaSegmentacao.objects.get_or_create(campanha=campanha)
    form = SegmentacaoForm(request.POST, instance=segmentacao)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
    form.save()
    return redirect('advertising:campanha_detalhe', uuid=uuid)


@login_required
@require_POST
def campanha_contratar(request, uuid):
    campanha = get_object_or_404(Campanha, uuid=uuid)
    try:
        contratar_campanha(campanha_id=campanha.pk, usuario=request.user)
    except ValidationError as exc:
        return JsonResponse({'error': exc.messages}, status=400)
    return redirect('advertising:campanha_detalhe', uuid=uuid)


@login_required
@require_POST
def campanha_pagar_fake(request, uuid):
    if not settings.DEBUG or not settings.PAYMENTS_USE_FAKE_GATEWAYS:
        raise PermissionDenied
    campanha = get_object_or_404(Campanha.objects.select_related('contratacao__cobranca'), uuid=uuid)
    if not pode_gerenciar_campanha(request.user, campanha):
        raise PermissionDenied
    try:
        processar_pagamento(cobranca_id=campanha.contratacao.cobranca_id, idempotency_key=request.headers.get('Idempotency-Key', ''))
        sincronizar_status_pagamento(campanha_id=campanha.pk)
    except (ValidationError, GatewayUnavailable) as exc:
        return JsonResponse({'error': getattr(exc, 'messages', [str(exc)])}, status=400)
    return redirect('advertising:campanha_detalhe', uuid=uuid)


@login_required
@require_POST
def campanha_cancelar(request, uuid):
    campanha = get_object_or_404(Campanha, uuid=uuid)
    try:
        cancelar_campanha(campanha_id=campanha.pk, usuario=request.user,
                          motivo=request.POST.get('motivo', ''))
    except ValidationError as exc:
        return JsonResponse({'error': exc.messages}, status=400)
    return redirect('advertising:campanha_detalhe', uuid=uuid)


@login_required
@require_POST
def campanha_aprovar(request, uuid):
    campanha = get_object_or_404(Campanha, uuid=uuid)
    try:
        aprovar_campanha(campanha_id=campanha.pk, usuario=request.user)
    except ValidationError as exc:
        return JsonResponse({'error': exc.messages}, status=400)
    return redirect('advertising:campanha_detalhe', uuid=uuid)


@login_required
@require_POST
def campanha_moderar(request, uuid, acao):
    campanha = get_object_or_404(Campanha, uuid=uuid)
    try:
        moderar_campanha(campanha_id=campanha.pk, usuario=request.user,
                         acao=acao.upper(), motivo=request.POST.get('motivo', ''))
    except ValidationError as exc:
        return JsonResponse({'error': exc.messages}, status=400)
    return redirect('advertising:campanha_detalhe', uuid=uuid)


@login_required
def campanha_administracao(request):
    if not usuario_e_master(request.user):
        raise PermissionDenied
    campanhas = (Campanha.objects.exclude(status=Campanha.Status.RASCUNHO)
                 .select_related('empresa', 'plano', 'contratacao__cobranca')
                 .prefetch_related('posicionamentos', 'criativos', 'segmentacao__categorias',
                                   'segmentacao__subcategorias', 'segmentacao__cnaes')
                 .order_by('status', 'inicio'))
    return render(request, 'advertising/campanha_administracao.html', {'campanhas': campanhas})


def _exigir_master(request):
    if not usuario_e_master(request.user):
        raise PermissionDenied


@login_required
def configuracao_comercial(request):
    _exigir_master(request)
    return render(request, 'advertising/configuracao_comercial.html', {
        'planos': PlanoPublicitario.objects.order_by('nivel', 'nome'),
        'posicionamentos': Posicionamento.objects.order_by('contexto', 'nome'),
    })


@login_required
def plano_editar(request, pk=None):
    _exigir_master(request)
    plano = get_object_or_404(PlanoPublicitario, pk=pk) if pk else None
    form = PlanoPublicitarioForm(request.POST or None, instance=plano)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('advertising:configuracao_comercial')
    return render(request, 'advertising/configuracao_form.html', {
        'form': form, 'titulo': 'Plano publicitário',
    })


@login_required
def posicionamento_editar(request, pk=None):
    _exigir_master(request)
    posicionamento = get_object_or_404(Posicionamento, pk=pk) if pk else None
    form = PosicionamentoForm(request.POST or None, instance=posicionamento)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('advertising:configuracao_comercial')
    return render(request, 'advertising/configuracao_form.html', {
        'form': form, 'titulo': 'Posicionamento publicitário',
    })


def entrega_clique(request, uuid):
    entrega = get_object_or_404(
        EntregaPublicidade.objects.select_related('criativo', 'campanha', 'posicionamento'),
        uuid=uuid,
    )
    destino = url_destino_segura(entrega)
    if not destino:
        raise Http404
    registrar_clique(entrega_uuid=uuid, request=request)
    return redirect(destino)
