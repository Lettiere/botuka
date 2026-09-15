from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.advertising.forms import PlanoPublicitarioForm, PosicionamentoForm
from apps.advertising.models import Campanha, PlanoPublicitario, Posicionamento
from apps.advertising.services import aprovar_campanha, moderar_campanha
from apps.gestao.decorators import master_required


FINANCEIRO_CHOICES = (
    ('PENDENTE', 'Pendente'),
    ('PAGO', 'Pago'),
    ('CANCELADO', 'Cancelado'),
    ('ESTORNADO', 'Estornado'),
    ('VENCIDO', 'Vencido'),
    ('RECUSADO', 'Recusado'),
)


@master_required
def campanha_lista(request):
    query = request.GET.get('q', '').strip()[:120]
    status = request.GET.get('status', '').strip()[:40]
    financeiro = request.GET.get('financeiro', '').strip()[:40]

    status_validos = {value for value, _label in Campanha.Status.choices}
    financeiro_validos = {value for value, _label in FINANCEIRO_CHOICES}

    if status not in status_validos:
        status = ''

    if financeiro not in financeiro_validos:
        financeiro = ''

    campanhas = (
        Campanha.objects
        .select_related(
            'empresa',
            'plano',
            'criado_por',
            'contratacao__cobranca',
        )
        .prefetch_related(
            'posicionamentos',
            'criativos',
        )
        .annotate(
            total_criativos=Count('criativos', distinct=True),
            criativos_aprovados=Count(
                'criativos',
                filter=Q(criativos__aprovado=True),
                distinct=True,
            ),
        )
    )

    if query:
        campanhas = campanhas.filter(
            Q(nome__icontains=query)
            | Q(empresa__nome_fantasia__icontains=query)
            | Q(plano__nome__icontains=query)
        )

    if status:
        campanhas = campanhas.filter(status=status)

    campanhas = campanhas.order_by('-atualizado_em', '-pk')

    # status_financeiro é propriedade do domínio.
    # Só materializamos o queryset quando esse filtro é solicitado.
    if financeiro:
        campanhas = [
            campanha
            for campanha in campanhas
            if campanha.status_financeiro == financeiro
        ]

    totais = Campanha.objects.aggregate(
        total=Count('pk'),
        rascunho=Count(
            'pk',
            filter=Q(status=Campanha.Status.RASCUNHO),
        ),
        aguardando=Count(
            'pk',
            filter=Q(status=Campanha.Status.AGUARDANDO_APROVACAO),
        ),
        ativas=Count(
            'pk',
            filter=Q(status=Campanha.Status.ATIVA),
        ),
        pausadas=Count(
            'pk',
            filter=Q(status=Campanha.Status.PAUSADA),
        ),
    )

    page_obj = Paginator(campanhas, 25).get_page(
        request.GET.get('page')
    )

    pagination_params = []
    if status:
        pagination_params.append(f'status={status}')
    if financeiro:
        pagination_params.append(f'financeiro={financeiro}')
    pagination_extra_query = '&'.join(pagination_params)

    return render(
        request,
        'gestao/publicidade/campanhas_lista.html',
        {
            'section': 'Publicidade',
            'page_obj': page_obj,
            'is_paginated': page_obj.paginator.num_pages > 1,
            'query': query,
            'status': status,
            'financeiro': financeiro,
            'status_choices': Campanha.Status.choices,
            'financeiro_choices': FINANCEIRO_CHOICES,
            'pagination_extra_query': pagination_extra_query,
            'totais': totais,
        },
    )


@master_required
def campanha_detalhe(request, uuid):
    campanha = get_object_or_404(
        Campanha.objects.select_related(
            'empresa',
            'plano',
            'criado_por',
            'aprovada_por',
            'contratacao__cobranca',
        ).prefetch_related(
            'posicionamentos',
            'criativos__posicionamento',
            'segmentacao__categorias',
            'segmentacao__subcategorias',
            'segmentacao__cnaes',
            'auditoria__usuario',
        ),
        uuid=uuid,
    )

    metricas = campanha.entregas.aggregate(
        impressoes=Count('pk'),
        cliques=Count(
            'pk',
            filter=Q(clicado_em__isnull=False),
        ),
    )

    segmentacao = getattr(campanha, 'segmentacao', None)
    contratacao = getattr(campanha, 'contratacao', None)

    return render(
        request,
        'gestao/publicidade/campanha_detalhe.html',
        {
            'section': 'Publicidade',
            'campanha': campanha,
            'segmentacao': segmentacao,
            'contratacao': contratacao,
            'metricas': metricas,
        },
    )


@master_required
@require_POST
def campanha_aprovar(request, uuid):
    campanha = get_object_or_404(Campanha, uuid=uuid)

    try:
        aprovar_campanha(
            campanha_id=campanha.pk,
            usuario=request.user,
        )
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    else:
        messages.success(request, 'Campanha aprovada com sucesso.')

    return redirect(
        'gestao:publicidade_campanha_detalhe',
        uuid=uuid,
    )


@master_required
@require_POST
def campanha_moderar(request, uuid, acao):
    campanha = get_object_or_404(Campanha, uuid=uuid)

    acao = acao.upper()

    if acao not in {'REJEITAR', 'PAUSAR', 'REATIVAR'}:
        messages.error(request, 'Ação de moderação inválida.')
        return redirect(
            'gestao:publicidade_campanha_detalhe',
            uuid=uuid,
        )

    try:
        moderar_campanha(
            campanha_id=campanha.pk,
            usuario=request.user,
            acao=acao,
            motivo=request.POST.get('motivo', ''),
        )
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    else:
        mensagens = {
            'REJEITAR': 'Campanha rejeitada.',
            'PAUSAR': 'Campanha pausada.',
            'REATIVAR': 'Campanha reativada.',
        }
        messages.success(request, mensagens[acao])

    return redirect(
        'gestao:publicidade_campanha_detalhe',
        uuid=uuid,
    )


@master_required
def configuracao_comercial(request):
    planos = PlanoPublicitario.objects.order_by('nivel', 'nome')
    posicionamentos = Posicionamento.objects.order_by('contexto', 'nome')

    return render(
        request,
        'gestao/publicidade/configuracao_comercial.html',
        {
            'section': 'Publicidade',
            'planos': planos,
            'posicionamentos': posicionamentos,
        },
    )


@master_required
def plano_form(request, pk=None):
    plano = get_object_or_404(PlanoPublicitario, pk=pk) if pk else None
    form = PlanoPublicitarioForm(request.POST or None, instance=plano)

    if request.method == 'POST' and form.is_valid():
        plano = form.save()
        messages.success(
            request,
            'Plano publicitário atualizado com sucesso.'
            if pk else
            'Plano publicitário criado com sucesso.',
        )
        return redirect('gestao:publicidade_configuracao')

    return render(
        request,
        'gestao/publicidade/configuracao_form.html',
        {
            'section': 'Publicidade',
            'form': form,
            'titulo': (
                'Editar plano publicitário'
                if plano else
                'Novo plano publicitário'
            ),
            'tipo': 'plano',
            'objeto': plano,
        },
    )


@master_required
def posicionamento_form(request, pk=None):
    posicionamento = (
        get_object_or_404(Posicionamento, pk=pk)
        if pk else None
    )
    form = PosicionamentoForm(
        request.POST or None,
        instance=posicionamento,
    )

    if request.method == 'POST' and form.is_valid():
        posicionamento = form.save()
        messages.success(
            request,
            'Posicionamento atualizado com sucesso.'
            if pk else
            'Posicionamento criado com sucesso.',
        )
        return redirect('gestao:publicidade_configuracao')

    return render(
        request,
        'gestao/publicidade/configuracao_form.html',
        {
            'section': 'Publicidade',
            'form': form,
            'titulo': (
                'Editar posicionamento'
                if posicionamento else
                'Novo posicionamento'
            ),
            'tipo': 'posicionamento',
            'objeto': posicionamento,
        },
    )
