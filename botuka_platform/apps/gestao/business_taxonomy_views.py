"""Administração da taxonomia empresarial, isolada dos demais domínios."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.gestao.decorators import permission_required
from apps.gestao.forms import (
    CategoriaForm, CNAEGestaoForm, EmpresaCNAEGestaoForm,
    SubcategoriaCNAEGestaoForm, SubcategoriaForm,
)
from apps.organizations.models import CNAE, EmpresaCNAE, SubcategoriaCNAE
from apps.taxonomy.models import Categoria, Subcategoria

CONFIG = {
    'cnaes': (CNAE, CNAEGestaoForm, 'CNAEs'),
    'mapeamentos': (SubcategoriaCNAE, SubcategoriaCNAEGestaoForm, 'Mapeamentos Subcategoria ↔ CNAE'),
    'empresas-cnaes': (EmpresaCNAE, EmpresaCNAEGestaoForm, 'Classificações CNAE de empresas'),
}
CATEGORY_CONFIG = {
    'categorias': (Categoria, CategoriaForm, 'Categorias'),
    'subcategorias': (Subcategoria, SubcategoriaForm, 'Subcategorias'),
}


def _config(config, kind):
    from django.http import Http404
    if kind not in config:
        raise Http404
    return config[kind]


def _querystring(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


@permission_required('categorias.gerenciar')
def lista(request, kind):
    model, _form, title = _config(CONFIG, kind)
    queryset = model.objects.all()
    if kind == 'mapeamentos':
        queryset = queryset.select_related('subcategoria__categoria', 'cnae')
    elif kind == 'empresas-cnaes':
        queryset = queryset.select_related('empresa', 'cnae')
    query = request.GET.get('q', '').strip()[:120]
    values = {name: request.GET.get(name, '') for name in (
        'ativo', 'categoria', 'subcategoria', 'cnae', 'empresa',
        'principal', 'revisado', 'origem', 'secao',
    )}
    values['secao'] = values['secao'].strip()[:5]
    if query:
        lookups = {
            'cnaes': Q(codigo__icontains=query) | Q(descricao__icontains=query),
            'mapeamentos': Q(subcategoria__nome__icontains=query) | Q(cnae__codigo__icontains=query) | Q(cnae__descricao__icontains=query),
            'empresas-cnaes': Q(empresa__nome_fantasia__icontains=query) | Q(cnae__codigo__icontains=query) | Q(cnae__descricao__icontains=query),
        }
        queryset = queryset.filter(lookups[kind])
    if values['ativo'] in {'1', '0'}:
        queryset = queryset.filter(ativo=values['ativo'] == '1')
    if kind == 'cnaes' and values['secao']:
        queryset = queryset.filter(secao=values['secao'])
    elif kind == 'mapeamentos':
        if values['categoria'].isdigit():
            queryset = queryset.filter(subcategoria__categoria_id=values['categoria'])
        if values['subcategoria'].isdigit():
            queryset = queryset.filter(subcategoria_id=values['subcategoria'])
        if values['cnae'].strip():
            queryset = queryset.filter(cnae__codigo__icontains=values['cnae'].strip()[:20])
        if values['principal'] in {'1', '0'}:
            queryset = queryset.filter(principal=values['principal'] == '1')
        if values['revisado'] in {'1', '0'}:
            queryset = queryset.filter(revisado=values['revisado'] == '1')
    elif kind == 'empresas-cnaes':
        if values['empresa'].strip():
            queryset = queryset.filter(empresa__nome_fantasia__icontains=values['empresa'].strip()[:120])
        if values['cnae'].strip():
            queryset = queryset.filter(cnae__codigo__icontains=values['cnae'].strip()[:20])
        if values['principal'] in {'1', '0'}:
            queryset = queryset.filter(principal=values['principal'] == '1')
        if values['origem'] in EmpresaCNAE.Origem.values:
            queryset = queryset.filter(origem=values['origem'])
    ordering = {
        'cnaes': ('codigo',),
        'mapeamentos': ('subcategoria__categoria__nome', 'subcategoria__nome', '-relevancia', 'cnae__codigo'),
        'empresas-cnaes': ('empresa__nome_fantasia', '-principal', 'cnae__codigo'),
    }[kind]
    page_obj = Paginator(queryset.order_by(*ordering), 25).get_page(request.GET.get('page'))
    context = {
        'kind': kind, 'title': title, 'page_obj': page_obj, 'query': query,
        'is_paginated': page_obj.has_other_pages(),
        'categories': Categoria.all_objects.order_by('ordem', 'nome'),
        'subcategories': Subcategoria.all_objects.select_related('categoria').order_by('categoria__nome', 'ordem', 'nome'),
        'origin_choices': EmpresaCNAE.Origem.choices,
        'querystring': _querystring(request), 'section': 'Taxonomia empresarial',
    }
    context.update({f'{name}_filter': value for name, value in values.items()})
    return render(request, 'gestao/taxonomia_empresarial/lista.html', context)


@permission_required('categorias.gerenciar')
def detalhe(request, kind, pk):
    model, _form, title = _config(CONFIG, kind)
    queryset = model.objects.all()
    if kind == 'mapeamentos':
        queryset = queryset.select_related('subcategoria__categoria', 'cnae')
    elif kind == 'empresas-cnaes':
        queryset = queryset.select_related('empresa', 'cnae')
    obj = get_object_or_404(queryset, pk=pk)
    return render(request, 'gestao/taxonomia_empresarial/detalhe.html', {
        'object': obj, 'kind': kind, 'title': title,
        'mapped_subcategories': obj.subcategorias_mapeadas.select_related('subcategoria__categoria') if kind == 'cnaes' else (),
        'classified_companies': obj.empresas.select_related('empresa') if kind == 'cnaes' else (),
        'section': 'Taxonomia empresarial',
    })


@permission_required('categorias.gerenciar')
def formulario(request, kind, pk=None):
    model, form_class, title = _config(CONFIG, kind)
    instance = get_object_or_404(model, pk=pk) if pk else None
    form = form_class(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        messages.success(request, 'Classificação salva com sucesso.')
        return redirect('gestao:taxonomia_empresarial_detalhe', kind=kind, pk=saved.pk)
    return render(request, 'gestao/taxonomia_empresarial/form.html', {
        'form': form, 'kind': kind, 'title': title, 'section': 'Taxonomia empresarial',
    })


@permission_required('categorias.gerenciar')
@require_POST
def status(request, kind, pk):
    model, _form, _title = _config(CONFIG, kind)
    instance = get_object_or_404(model, pk=pk)
    conflict = kind == 'empresas-cnaes' and not instance.ativo and instance.principal and EmpresaCNAE.objects.filter(
        empresa=instance.empresa, principal=True, ativo=True,
    ).exclude(pk=instance.pk).exists()
    if conflict:
        messages.error(request, 'A empresa já possui outro CNAE principal ativo. Ajuste a classificação antes de reativar.')
    else:
        instance.ativo = not instance.ativo
        instance.save(update_fields=['ativo', 'atualizado_em'])
        messages.success(request, 'Status atualizado.')
    return redirect('gestao:taxonomia_empresarial_detalhe', kind=kind, pk=pk)


@permission_required('categorias.gerenciar')
def categoria_lista(request, kind):
    model, _form, title = _config(CATEGORY_CONFIG, kind)
    queryset = model.all_objects.all()
    if kind == 'subcategorias':
        queryset = queryset.select_related('categoria')
    query = request.GET.get('q', '').strip()[:120]
    active = request.GET.get('ativo', '')
    category = request.GET.get('categoria', '')
    if query:
        queryset = queryset.filter(Q(nome__icontains=query) | Q(slug__icontains=query))
    if active in {'1', '0'}:
        queryset = queryset.filter(ativo=active == '1')
    if kind == 'subcategorias' and category.isdigit():
        queryset = queryset.filter(categoria_id=category)
    page_obj = Paginator(queryset.order_by(*model._meta.ordering), 25).get_page(request.GET.get('page'))
    return render(request, 'gestao/taxonomia_empresarial/categorias_lista.html', {
        'kind': kind, 'title': title, 'page_obj': page_obj, 'query': query,
        'is_paginated': page_obj.has_other_pages(),
        'active_filter': active, 'category_filter': category,
        'categories': Categoria.all_objects.order_by('ordem', 'nome'),
        'querystring': _querystring(request), 'section': 'Taxonomia empresarial',
    })


@permission_required('categorias.gerenciar')
def categoria_detalhe(request, kind, pk):
    model, _form, _title = _config(CATEGORY_CONFIG, kind)
    queryset = model.all_objects.select_related('categoria') if kind == 'subcategorias' else model.all_objects
    obj = get_object_or_404(queryset, pk=pk)
    return render(request, 'gestao/taxonomia_empresarial/categoria_detalhe.html', {
        'object': obj, 'kind': kind,
        'subcategories': obj.subcategorias.all() if kind == 'categorias' else (),
        'mappings': obj.cnaes_mapeados.select_related('cnae') if kind == 'subcategorias' else (),
        'section': 'Taxonomia empresarial',
    })


@permission_required('categorias.gerenciar')
def categoria_form(request, kind, pk=None):
    model, form_class, title = _config(CATEGORY_CONFIG, kind)
    instance = get_object_or_404(model.all_objects, pk=pk) if pk else None
    form = form_class(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        messages.success(request, 'Classificação salva com sucesso.')
        return redirect(f'gestao:{kind}_detalhe', pk=saved.pk)
    return render(request, 'gestao/taxonomia_empresarial/form.html', {
        'form': form, 'kind': kind, 'title': title,
        'category_flow': True, 'section': 'Taxonomia empresarial',
    })


@permission_required('categorias.gerenciar')
@require_POST
def categoria_status(request, kind, pk):
    model, _form, _title = _config(CATEGORY_CONFIG, kind)
    instance = get_object_or_404(model.all_objects, pk=pk)
    instance.ativo = not instance.ativo
    instance.removido_em = None if instance.ativo else timezone.now()
    instance.save(update_fields=['ativo', 'removido_em', 'atualizado_em'])
    messages.success(request, 'Registro reativado.' if instance.ativo else 'Registro inativado sem exclusão física.')
    return redirect(f'gestao:{kind}_detalhe', pk=pk)
