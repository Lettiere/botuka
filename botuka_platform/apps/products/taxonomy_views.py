from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
import uuid as uuid_lib

from apps.accounts.authorization import pode
from apps.accounts.permissions import usuario_e_master
from apps.gestao.decorators import staff_required

from .models import CategoriaProduto, FamiliaProduto, Produto, SegmentoProduto, TipoProduto
from .taxonomy_forms import (
    CategoriaProdutoGestaoForm, FamiliaProdutoGestaoForm,
    SegmentoProdutoGestaoForm, TipoProdutoGestaoForm,
)

CONFIG = {
    'categorias': (CategoriaProduto, CategoriaProdutoGestaoForm, 'Categorias', 'categoria'),
    'familias': (FamiliaProduto, FamiliaProdutoGestaoForm, 'Famílias', 'familia'),
    'tipos': (TipoProduto, TipoProdutoGestaoForm, 'Tipos de produto', 'tipo'),
    'segmentos': (SegmentoProduto, SegmentoProdutoGestaoForm, 'Segmentos', 'segmento'),
}


def _authorize(request, action='visualizar', entity=None):
    code = f'products.taxonomy.{entity}.{action}' if entity else 'products.taxonomy.visualizar'
    if not (usuario_e_master(request.user) or pode(request.user, code)):
        raise PermissionDenied('Você não possui permissão para administrar esta taxonomia.')


@staff_required
def dashboard(request):
    _authorize(request)
    cards = [
        ('Categorias ativas', CategoriaProduto.objects.filter(ativo=True, removido_em__isnull=True).count(), 'gestao:taxonomia_categorias_lista'),
        ('Famílias ativas', FamiliaProduto.objects.filter(ativo=True, removido_em__isnull=True).count(), 'gestao:taxonomia_familias_lista'),
        ('Tipos ativos', TipoProduto.objects.filter(ativo=True, removido_em__isnull=True).count(), 'gestao:taxonomia_tipos_lista'),
        ('Segmentos ativos', SegmentoProduto.objects.filter(ativo=True, removido_em__isnull=True).count(), 'gestao:taxonomia_segmentos_lista'),
        ('Produtos cadastrados', Produto.objects.count(), 'painel:produtos_lista'),
        ('Produtos publicados', Produto.objects.filter(status=Produto.Status.PUBLICADO).count(), 'painel:produtos_lista'),
        ('Produtos pendentes', Produto.objects.filter(status=Produto.Status.EM_ANALISE).count(), 'painel:produtos_lista'),
    ]
    sem_taxonomia = Produto.objects.filter(
        Q(categoria_taxonomia__isnull=True) | Q(familia__isnull=True) | Q(tipo_produto__isnull=True)
    ).distinct().count()
    return render(request, 'gestao/taxonomia_produtos/dashboard.html', {
        'cards': cards, 'sem_taxonomia': sem_taxonomia, 'inconsistencias': sem_taxonomia,
        'title': 'Taxonomia de Produtos',
    })


@staff_required
def lista(request, kind):
    model, _form, title, entity = CONFIG[kind]
    _authorize(request, entity=entity)
    qs = model.objects.filter(removido_em__isnull=True)
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    if query:
        qs = qs.filter(Q(nome__icontains=query) | Q(slug__icontains=query))
    if status in {'ativo', 'inativo'}:
        qs = qs.filter(ativo=status == 'ativo')
    if kind == 'familias':
        qs = qs.select_related('categoria').annotate(total_relacoes=Count('tipos'))
    elif kind == 'tipos':
        qs = qs.select_related('familia__categoria').annotate(total_relacoes=Count('segmentos_relacionados', filter=Q(segmentos_relacionados__ativo=True)))
    elif kind == 'segmentos':
        qs = qs.annotate(total_relacoes=Count('tipos_relacionados', filter=Q(tipos_relacionados__ativo=True)))
    else:
        qs = qs.annotate(total_relacoes=Count('familias'))
    page = Paginator(qs.order_by('ordem', 'nome'), 20).get_page(request.GET.get('page'))
    return render(request, 'gestao/taxonomia_produtos/lista.html', {
        'page_obj': page, 'kind': kind, 'title': title, 'query': query, 'status': status,
        'entity': entity, 'create_url': f'gestao:taxonomia_{kind}_novo',
        'edit_url': f'gestao:taxonomia_{kind}_editar',
        'detail_url': f'gestao:taxonomia_{kind}_detalhe',
        'status_url': f'gestao:taxonomia_{kind}_status',
    })


@staff_required
def formulario(request, kind, uuid=None):
    model, form_class, title, entity = CONFIG[kind]
    action = 'editar' if uuid else 'criar'
    _authorize(request, action, entity)
    item = get_object_or_404(model, uuid=uuid) if uuid else None
    form = form_class(request.POST or None, instance=item)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        messages.success(request, f'{saved.nome} salvo com sucesso.')
        return redirect(f'gestao:taxonomia_{kind}_lista')
    return render(request, 'gestao/taxonomia_produtos/formulario.html', {
        'form': form, 'kind': kind, 'title': f'{"Editar" if item else "Novo"} — {title}',
        'list_url': f'gestao:taxonomia_{kind}_lista',
    })


@staff_required
def detalhe(request, kind, uuid):
    model, _form, title, entity = CONFIG[kind]
    _authorize(request, entity=entity)
    item = get_object_or_404(model, uuid=uuid)
    return render(request, 'gestao/taxonomia_produtos/detalhe.html', {
        'item': item, 'kind': kind, 'title': title,
        'edit_url': f'gestao:taxonomia_{kind}_editar',
        'list_url': f'gestao:taxonomia_{kind}_lista',
    })


@staff_required
@require_POST
def alternar_status(request, kind, uuid):
    model, _form, _title, entity = CONFIG[kind]
    _authorize(request, 'desativar', entity)
    item = get_object_or_404(model, uuid=uuid)
    item.ativo = not item.ativo
    item.save(update_fields=['ativo', 'atualizado_em'])
    messages.success(request, f'{item.nome} {"ativado" if item.ativo else "desativado"}.')
    return redirect(f'gestao:taxonomia_{kind}_lista')


def _api_allowed(request):
    if not request.user.is_authenticated:
        raise PermissionDenied
    if not (usuario_e_master(request.user) or pode(request.user, 'products.taxonomy.visualizar') or pode(request.user, 'products.acessar')):
        raise PermissionDenied


def _valid_id(model, value):
    if not value:
        return None
    try:
        return model.objects.only('pk').get(pk=int(value)).pk
    except (TypeError, ValueError):
        try:
            parsed = uuid_lib.UUID(str(value))
            return model.objects.only('pk').get(uuid=parsed).pk
        except (model.DoesNotExist, ValueError, TypeError):
            return None
    except model.DoesNotExist:
        return None


def api_familias(request):
    _api_allowed(request)
    raw = request.GET.get('categoria')
    category_id = _valid_id(CategoriaProduto, raw)
    if raw and not category_id:
        return JsonResponse({'results': [], 'error': 'Categoria inválida.'}, status=400)
    qs = FamiliaProduto.objects.filter(categoria_id=category_id, ativo=True, removido_em__isnull=True) if category_id else FamiliaProduto.objects.none()
    return JsonResponse({'results': list(qs.order_by('ordem', 'nome').values('id', 'uuid', 'nome'))})


def api_tipos(request):
    _api_allowed(request)
    raw = request.GET.get('familia')
    family_id = _valid_id(FamiliaProduto, raw)
    if raw and not family_id:
        return JsonResponse({'results': [], 'error': 'Família inválida.'}, status=400)
    qs = TipoProduto.objects.filter(familia_id=family_id, ativo=True, removido_em__isnull=True) if family_id else TipoProduto.objects.none()
    return JsonResponse({'results': list(qs.order_by('ordem', 'nome').values('id', 'uuid', 'nome', 'permite_segmento', 'exige_segmento'))})


def api_segmentos(request):
    _api_allowed(request)
    raw = request.GET.get('tipo')
    type_id = _valid_id(TipoProduto, raw)
    if raw and not type_id:
        return JsonResponse({'results': [], 'error': 'Tipo de produto inválido.'}, status=400)
    item = TipoProduto.objects.filter(pk=type_id, ativo=True, removido_em__isnull=True).first() if type_id else None
    qs = SegmentoProduto.objects.filter(
        tipos_relacionados__tipo_produto=item, tipos_relacionados__ativo=True,
        ativo=True, removido_em__isnull=True,
    ).distinct() if item else SegmentoProduto.objects.none()
    return JsonResponse({
        'permite_segmento': bool(item and item.permite_segmento),
        'exige_segmento': bool(item and item.exige_segmento),
        'results': list(qs.order_by('ordem', 'nome').values('id', 'uuid', 'nome')),
    })
