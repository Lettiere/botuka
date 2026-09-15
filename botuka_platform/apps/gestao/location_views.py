"""Administração da hierarquia operacional de apps.locations."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.gestao.decorators import permission_required
from apps.gestao.forms import BairroForm, CidadeForm, EstadoForm, PaisForm
from apps.locations.models import Bairro, Cidade, Estado, Pais


CONFIG = {
    'paises': (Pais, PaisForm, 'Países'),
    'estados': (Estado, EstadoForm, 'Estados'),
    'cidades': (Cidade, CidadeForm, 'Cidades'),
    'bairros': (Bairro, BairroForm, 'Bairros'),
}


def _config(kind):
    from django.http import Http404
    if kind not in CONFIG:
        raise Http404
    return CONFIG[kind]


def _querystring(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


@permission_required('localidades.gerenciar')
def lista(request, kind):
    model, _form, title = _config(kind)
    queryset = model.all_objects.all()
    if kind == 'estados':
        queryset = queryset.select_related('pais')
    elif kind == 'cidades':
        queryset = queryset.select_related('estado__pais')
    elif kind == 'bairros':
        queryset = queryset.select_related('cidade__estado__pais')
    query = request.GET.get('q', '').strip()[:120]
    active = request.GET.get('ativo', '')
    country = request.GET.get('pais', '')
    state = request.GET.get('estado', '')
    city = request.GET.get('cidade', '').strip()[:120]
    if query:
        filters = Q(nome__icontains=query)
        if kind == 'paises':
            filters |= Q(codigo_iso_2__icontains=query) | Q(codigo_iso_3__icontains=query)
        elif kind == 'estados':
            filters |= Q(sigla__icontains=query) | Q(codigo_ibge__icontains=query)
        elif kind == 'cidades':
            filters |= Q(codigo_ibge__icontains=query)
        queryset = queryset.filter(filters)
    if active in {'1', '0'}:
        queryset = queryset.filter(ativo=active == '1')
    if country.isdigit():
        lookup = 'pais_id' if kind == 'estados' else 'estado__pais_id' if kind == 'cidades' else 'cidade__estado__pais_id'
        if kind != 'paises':
            queryset = queryset.filter(**{lookup: country})
    if state.isdigit():
        if kind == 'cidades':
            queryset = queryset.filter(estado_id=state)
        elif kind == 'bairros':
            queryset = queryset.filter(cidade__estado_id=state)
    if kind == 'bairros' and city:
        queryset = queryset.filter(cidade__nome__icontains=city)
    page_obj = Paginator(queryset.order_by(*model._meta.ordering), 25).get_page(request.GET.get('page'))
    context = {
        'kind': kind, 'title': title, 'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(), 'query': query,
        'active_filter': active, 'country_filter': country,
        'state_filter': state, 'city_filter': city,
        'querystring': _querystring(request), 'section': 'Localidades',
    }
    if kind != 'paises':
        context['countries'] = Pais.all_objects.order_by('nome')
    if kind in {'cidades', 'bairros'}:
        context['states'] = Estado.all_objects.select_related('pais').order_by('pais__nome', 'nome')
    return render(request, 'gestao/localidades/lista.html', context)


@permission_required('localidades.gerenciar')
def detalhe(request, kind, pk):
    model, _form, title = _config(kind)
    queryset = model.all_objects.all()
    if kind == 'estados':
        queryset = queryset.select_related('pais')
    elif kind == 'cidades':
        queryset = queryset.select_related('estado__pais')
    elif kind == 'bairros':
        queryset = queryset.select_related('cidade__estado__pais')
    obj = get_object_or_404(queryset, pk=pk)
    related = {
        'paises': Estado.all_objects.filter(pais=obj) if kind == 'paises' else (),
        'estados': Cidade.all_objects.filter(estado=obj).select_related('estado') if kind == 'estados' else (),
        'cidades': Bairro.all_objects.filter(cidade=obj).select_related('cidade__estado') if kind == 'cidades' else (),
    }.get(kind, ())
    usage = []
    if kind == 'estados':
        usage = [('Empresas ativas', obj.empresas.count())]
    elif kind == 'cidades':
        usage = [('Empresas ativas', obj.empresas.count()), ('Endereços ativos', obj.enderecos.count())]
    elif kind == 'bairros':
        usage = [('Endereços ativos', obj.enderecos.count())]
    return render(request, 'gestao/localidades/detalhe.html', {
        'object': obj, 'kind': kind, 'title': title,
        'related': related, 'usage': usage, 'section': 'Localidades',
    })


@permission_required('localidades.gerenciar')
def formulario(request, kind, pk=None):
    model, form_class, title = _config(kind)
    instance = get_object_or_404(model.all_objects, pk=pk) if pk else None
    form = form_class(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        messages.success(request, 'Localidade salva com sucesso.')
        return redirect(f'gestao:{kind}_lista')
    return render(request, 'gestao/localidades/form.html', {
        'form': form, 'kind': kind, 'title': f'Editar {title}' if instance else f'Novo registro — {title}',
        'section': 'Localidades',
    })


@permission_required('localidades.gerenciar')
@require_POST
def status(request, kind, pk):
    model, _form, _title = _config(kind)
    instance = get_object_or_404(model.all_objects, pk=pk)
    parent = {
        'estados': getattr(instance, 'pais', None),
        'cidades': getattr(instance, 'estado', None),
        'bairros': getattr(instance, 'cidade', None),
    }.get(kind)
    if not instance.ativo and parent is not None and not parent.ativo:
        messages.error(request, 'Reative primeiro o registro pai desta localidade.')
        return redirect(f'gestao:{kind}_detalhe', pk=pk)
    instance.ativo = not instance.ativo
    instance.removido_em = None if instance.ativo else timezone.now()
    instance.save(update_fields=['ativo', 'removido_em', 'atualizado_em'])
    messages.success(request, 'Registro reativado.' if instance.ativo else 'Registro inativado sem exclusão física.')
    return redirect(f'gestao:{kind}_detalhe', pk=pk)
