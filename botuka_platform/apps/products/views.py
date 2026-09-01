import re
import uuid as uuid_lib

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.permissions import usuario_tem_permissao
from apps.organizations.permissions import empresas_gerenciaveis_para_usuario
from apps.organizations.models import Empresa
from apps.core.seo.page_builders import product_seo

from .forms import ProdutoForm, ProdutoImagemForm, ProdutoRapidoForm, ProdutoVideoFormSet
from .models import AuditoriaProduto, Conversa, DenunciaNegociacao, Produto, ProdutoImagem
from .permissions import pode_editar, produtos_do_usuario
from .public_catalog import produtos_publicos
from .services import (
    calcular_limite, gerar_codigo_interno, validar_documentos_publicacao,
    validar_nova_criacao, whatsapp_produto,
    validar_transicao_status,
    PRODUCT_STATUS_TRANSITIONS,
)
from .taxonomy_views import api_categorias, api_familias, api_setores, api_tipos


def _allowed(user, code):
    return usuario_tem_permissao(user, code)


STATUS_PERMISSIONS = {
    Produto.Status.EM_ANALISE: 'products.enviar_analise',
    Produto.Status.APROVADO: 'products.aprovar',
    Produto.Status.PUBLICADO: 'products.publicar',
    Produto.Status.REJEITADO: 'products.rejeitar',
    Produto.Status.PAUSADO: 'products.pausar',
    Produto.Status.ARQUIVADO: 'products.arquivar',
    Produto.Status.RASCUNHO: 'products.restaurar',
    Produto.Status.ESGOTADO: 'products.editar_proprios',
    Produto.Status.INDISPONIVEL: 'products.editar_proprios',
}


@login_required
def painel_lista(request):
    if not _allowed(request.user, 'products.acessar'):
        raise PermissionDenied
    produtos = produtos_do_usuario(request.user).select_related(
        'empresa_proprietaria', 'categoria_taxonomia', 'familia', 'tipo_produto', 'segmento',
    ).prefetch_related('imagens')
    scope = request.GET.get('escopo')
    if scope == 'pessoais':
        produtos = produtos.filter(empresa_proprietaria__isnull=True, proprietario=request.user)
    elif scope == 'empresas':
        produtos = produtos.filter(empresa_proprietaria__isnull=False)
    query = request.GET.get('q', '').strip()
    if query:
        produtos = produtos.filter(Q(nome__icontains=query) | Q(codigo_interno__icontains=query))
    status = request.GET.get('status', '')
    if status in Produto.Status.values:
        produtos = produtos.filter(status=status)
    relation_filters = {
        'empresa': 'empresa_proprietaria__uuid', 'categoria': 'categoria_taxonomia__uuid',
        'familia': 'familia__uuid', 'tipo': 'tipo_produto__uuid', 'segmento': 'segmento__uuid',
    }
    for parameter, field in relation_filters.items():
        if request.GET.get(parameter):
            produtos = produtos.filter(**{field: request.GET[parameter]})
    if request.GET.get('publicado') in {'sim', 'nao'}:
        if request.GET['publicado'] == 'sim':
            produtos = produtos.filter(status=Produto.Status.PUBLICADO)
        else:
            produtos = produtos.exclude(status=Produto.Status.PUBLICADO)
    if request.GET.get('destaque') in {'sim', 'nao'}:
        produtos = produtos.filter(destaque=request.GET['destaque'] == 'sim')
    if request.GET.get('estoque') == 'com':
        produtos = produtos.filter(estoque_informativo__gt=0)
    elif request.GET.get('estoque') == 'sem':
        produtos = produtos.filter(Q(estoque_informativo=0) | Q(estoque_informativo__isnull=True))
    page_obj = Paginator(produtos, 20).get_page(request.GET.get('page'))
    from .models import CategoriaProduto, FamiliaProduto, SegmentoProduto, TipoProduto
    return render(request, 'painel/produtos/lista.html', {
        'produtos': page_obj.object_list, 'page_obj': page_obj, 'titulo': 'Produtos',
        'limite_pessoal': calcular_limite(request.user, Produto.TitularTipo.PESSOA_FISICA),
        'empresas_filtro': empresas_gerenciaveis_para_usuario(request.user).filter(ativo=True),
        'categorias_filtro': CategoriaProduto.objects.filter(ativo=True),
        'familias_filtro': FamiliaProduto.objects.filter(ativo=True),
        'tipos_filtro': TipoProduto.objects.filter(ativo=True),
        'segmentos_filtro': SegmentoProduto.objects.filter(ativo=True),
        'produto_statuses': Produto.Status.choices,
    })


@login_required
def painel_criar(request, empresa_uuid=None):
    if not (_allowed(request.user, 'products.criar_proprio') or _allowed(request.user, 'products.criar_empresa')):
        raise PermissionDenied
    fixed_company = None
    if empresa_uuid:
        fixed_company = get_object_or_404(
            empresas_gerenciaveis_para_usuario(request.user).filter(
                ativo=True, status=Empresa.Status.ATIVA,
            ),
            uuid=empresa_uuid,
        )
        if not fixed_company.pode_criar_rascunho_produto:
            raise PermissionDenied('A atuação da empresa não permite cadastrar produtos.')
    form = ProdutoRapidoForm(
        request.POST or None, request.FILES or None, user=request.user,
        fixed_company=fixed_company,
    )
    if request.method == 'POST' and form.is_valid():
        company = form.cleaned_data.get('empresa_proprietaria')
        needed = 'products.criar_empresa' if company else 'products.criar_proprio'
        if not _allowed(request.user, needed):
            raise PermissionDenied
        validar_nova_criacao(request.user, form.cleaned_data['titular_tipo'], company)
        with transaction.atomic():
            item = form.prepare_instance()
            item.criador_registro = item.proprietario = item.responsavel = request.user
            item.save()
            item.codigo_interno = gerar_codigo_interno(item)
            item.save(update_fields=['codigo_interno', 'atualizado_em'])
            form.save_main_image(item)
            AuditoriaProduto.objects.create(
                produto=item, usuario=request.user,
                acao='CRIADO_EMPRESA' if company else 'CRIADO_PESSOAL',
                dados={'empresa_id': company.pk if company else None, 'origem_empresa': bool(fixed_company)},
            )
        messages.success(request, 'Produto criado como rascunho.')
        if request.POST.get('acao') == 'continuar':
            return redirect('painel:produto_editar', uuid=item.uuid)
        return redirect('painel:produto_detalhe', uuid=item.uuid)
    return render(request, 'painel/produtos/novo.html', {
        'form': form, 'titulo': 'Cadastrar produto', 'fixed_company': fixed_company,
    })

@login_required
def painel_detalhe(request, uuid):
    item = get_object_or_404(produtos_do_usuario(request.user), uuid=uuid)
    limite = calcular_limite(request.user, item.titular_tipo, item.empresa_proprietaria)
    return render(request, 'painel/produtos/detalhe.html', {
        'produto': item, 'limite': limite, 'pode_editar': pode_editar(request.user, item),
        'status_opcoes': [
            choice for choice in Produto.Status.choices
            if choice[0] in PRODUCT_STATUS_TRANSITIONS.get(item.status, set())
            and _allowed(request.user, STATUS_PERMISSIONS[choice[0]])
        ],
        'url_publica_vendas': f"{settings.VENDAS_URL}/produtos/{item.slug}/",
    })


@login_required
def painel_editar(request, uuid):
    item = get_object_or_404(produtos_do_usuario(request.user), uuid=uuid)
    if not pode_editar(request.user, item):
        raise PermissionDenied
    original = (item.titular_tipo, item.empresa_proprietaria_id)
    form = ProdutoForm(request.POST or None, request.FILES or None, instance=item, user=request.user)
    video_formset = ProdutoVideoFormSet(request.POST or None, instance=item, prefix='videos')
    form_valid = form.is_valid() if request.method == 'POST' else False
    if form_valid:
        form_valid = form.validate_image_limit()
    if request.method == 'POST' and form_valid and video_formset.is_valid():
        target = (form.cleaned_data['titular_tipo'], getattr(form.cleaned_data.get('empresa_proprietaria'), 'pk', None))
        if target != original:
            validar_nova_criacao(request.user, target[0], form.cleaned_data.get('empresa_proprietaria'))
        with transaction.atomic():
            form.save()
            form.save_attributes(item)
            form.save_media(item)
            for image in item.imagens.filter(uuid__in=request.POST.getlist('remove_images')):
                image.delete()
            video_formset.save()
            AuditoriaProduto.objects.create(
                produto=item, usuario=request.user, acao='ALTERADO',
                dados={
                    'titular_anterior': original[0], 'empresa_anterior': original[1],
                    'titular_novo': target[0], 'empresa_nova': target[1],
                },
            )
        messages.success(request, 'Produto atualizado.')
        return redirect('painel:produto_detalhe', uuid=item.uuid)
    return render(request, 'painel/produtos/form.html', {
        'form': form, 'video_formset': video_formset, 'produto': item, 'titulo': 'Editar produto',
    })


@login_required
@require_POST
def painel_status(request, uuid):
    item = get_object_or_404(produtos_do_usuario(request.user), uuid=uuid)
    target = request.POST.get('status')
    permission = STATUS_PERMISSIONS.get(target)
    if not permission or not _allowed(request.user, permission):
        raise PermissionDenied
    rejection_reason = request.POST.get('motivo_rejeicao', '').strip()
    try:
        validar_transicao_status(item, target, rejection_reason)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('painel:produto_detalhe', uuid=item.uuid)
    if target == Produto.Status.PUBLICADO:
        try:
            validar_documentos_publicacao(item)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect('painel:produto_detalhe', uuid=item.uuid)
        item.publicado_em = timezone.now()
        item.publicado_por = request.user
    if target == Produto.Status.APROVADO:
        item.aprovado_em = timezone.now()
        item.aprovado_por = request.user
    if target == Produto.Status.REJEITADO:
        item.motivo_rejeicao = rejection_reason
    elif target in {Produto.Status.EM_ANALISE, Produto.Status.APROVADO}:
        item.motivo_rejeicao = ''
    old = item.status
    with transaction.atomic():
        item.status = target
        item.save()
        AuditoriaProduto.objects.create(
            produto=item, usuario=request.user, acao='STATUS',
            dados={'anterior': old, 'novo': target, 'motivo': rejection_reason},
        )
    return redirect('painel:produto_detalhe', uuid=item.uuid)


@login_required
def painel_imagens(request, uuid):
    item = get_object_or_404(produtos_do_usuario(request.user), uuid=uuid)
    if not pode_editar(request.user, item) or not _allowed(request.user, 'products.gerenciar_imagens'):
        raise PermissionDenied
    form = ProdutoImagemForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        image = form.save(commit=False)
        image.produto = item
        image.save()
        if image.principal:
            item.imagens.exclude(pk=image.pk).update(principal=False)
        return redirect('painel:produto_imagens', uuid=item.uuid)
    return render(request, 'painel/produtos/imagens.html', {'produto': item, 'form': form, 'imagens': item.imagens.all()})


@login_required
@require_POST
def painel_excluir_imagem(request, uuid, image_uuid):
    item = get_object_or_404(produtos_do_usuario(request.user), uuid=uuid)
    if not pode_editar(request.user, item):
        raise PermissionDenied
    image = get_object_or_404(ProdutoImagem.objects, uuid=image_uuid, produto=item)
    image.delete()
    return redirect('painel:produto_imagens', uuid=item.uuid)


@login_required
@require_POST
def painel_excluir(request, uuid):
    item = get_object_or_404(produtos_do_usuario(request.user), uuid=uuid)
    if not _allowed(request.user, 'products.excluir'):
        raise PermissionDenied
    AuditoriaProduto.objects.create(produto=item, usuario=request.user, acao='EXCLUIDO')
    item.delete()
    messages.success(request, 'Produto removido com segurança.')
    return redirect('painel:produtos_lista')


def publico_detalhe(request, slug):
    item = get_object_or_404(
        produtos_publicos().prefetch_related('videos'),
        slug=slug,
    )
    whatsapp = whatsapp_produto(item)
    return render(request, 'publico/produtos/detalhe.html', {
        'produto': item, 'whatsapp_numero': whatsapp['numero'],
        'whatsapp_url': whatsapp['url'], 'seo': product_seo(request, item),
    })


def loja(request):
    products = produtos_publicos()
    query = request.GET.get('q', '').strip()[:120]
    filters = {
        'categoria': request.GET.get('categoria', ''),
        'familia': request.GET.get('familia', ''),
        'tipo': request.GET.get('tipo', ''),
        'segmento': request.GET.get('segmento', ''),
        'empresa': request.GET.get('empresa', ''),
        'disponibilidade': request.GET.get('disponibilidade', ''),
    }
    if query:
        products = products.filter(
            Q(nome__icontains=query) | Q(descricao_curta__icontains=query)
            | Q(empresa_proprietaria__nome_fantasia__icontains=query)
        )
    field_map = {
        'categoria': 'categoria_taxonomia__uuid', 'familia': 'familia__uuid',
        'tipo': 'tipo_produto__uuid', 'segmento': 'segmento__uuid',
        'empresa': 'empresa_proprietaria__uuid', 'disponibilidade': 'disponibilidade',
    }
    for key, value in filters.items():
        if value:
            if key != 'disponibilidade':
                try:
                    value = uuid_lib.UUID(value)
                except (ValueError, TypeError):
                    products = products.none()
                    continue
            products = products.filter(**{field_map[key]: value})
    minimum = request.GET.get('preco_min', '').replace(',', '.')
    maximum = request.GET.get('preco_max', '').replace(',', '.')
    try:
        if minimum:
            products = products.filter(preco__gte=minimum)
        if maximum:
            products = products.filter(preco__lte=maximum)
    except (TypeError, ValueError):
        pass
    ordering = request.GET.get('ordem', 'recentes')
    products = products.order_by(
        'preco' if ordering == 'menor_preco' else '-preco' if ordering == 'maior_preco' else '-destaque',
        '-publicado_em',
    )
    base = produtos_publicos()
    from .models import CategoriaProduto, FamiliaProduto, SegmentoProduto, TipoProduto
    categories = CategoriaProduto.objects.filter(ativo=True, produtos__in=base).distinct().order_by('ordem', 'nome')
    families = FamiliaProduto.objects.filter(ativo=True, produtos__in=base).select_related('categoria').distinct().order_by('ordem', 'nome')
    types = TipoProduto.objects.filter(ativo=True, produtos__in=base).select_related('familia').distinct().order_by('ordem', 'nome')
    segments = SegmentoProduto.objects.filter(ativo=True, produtos__in=base).prefetch_related('tipos').distinct().order_by('ordem', 'nome')
    companies = Empresa.objects.filter(ativo=True, produtos__in=base).distinct().order_by('nome_fantasia')
    page = Paginator(products, 12).get_page(request.GET.get('page'))
    return render(request, 'publico/produtos/loja.html', {
        'produtos': page.object_list, 'page_obj': page, 'categorias': categories,
        'familias': families, 'tipos': types, 'segmentos': segments, 'empresas': companies,
        'filtros': filters, 'query': query, 'disponibilidades': Produto.Disponibilidade.choices,
    })


@login_required
def painel_empresa_produtos(request, empresa_uuid):
    if not _allowed(request.user, 'products.visualizar'):
        raise PermissionDenied
    company = get_object_or_404(empresas_gerenciaveis_para_usuario(request.user), uuid=empresa_uuid)
    products = produtos_do_usuario(request.user).filter(empresa_proprietaria=company)
    status = request.GET.get('status', '')
    if status in Produto.Status.values:
        products = products.filter(status=status)
    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(nome__icontains=query)
    page_obj = Paginator(products, 20).get_page(request.GET.get('page'))
    return render(request, 'painel/empresas/produtos.html', {
        'empresa': company, 'produtos': page_obj.object_list, 'page_obj': page_obj,
        'limite': calcular_limite(request.user, Produto.TitularTipo.EMPRESA, company),
        'publicados': products.filter(status=Produto.Status.PUBLICADO).count(),
        'rascunhos': products.filter(status=Produto.Status.RASCUNHO).count(),
        'em_analise': products.filter(status=Produto.Status.EM_ANALISE).count(),
        'pausados': products.filter(status=Produto.Status.PAUSADO).count(),
        'arquivados': products.filter(status=Produto.Status.ARQUIVADO).count(),
        'produto_statuses': Produto.Status.choices,
    })


@login_required
def painel_conversas(request):
    if not _allowed(request.user, 'products.acessar_conversas'):
        raise PermissionDenied
    conversations = Conversa.objects.filter(
        Q(comprador=request.user) | Q(vendedor=request.user), ativo=True,
    ).select_related('produto', 'comprador', 'vendedor')
    return render(request, 'painel/produtos/conversas.html', {'conversas': conversations})


@login_required
def painel_denuncias(request):
    if not _allowed(request.user, 'products.visualizar_denuncias'):
        raise PermissionDenied
    reports = DenunciaNegociacao.objects.select_related('produto', 'denunciante', 'denunciado')
    return render(request, 'painel/produtos/denuncias.html', {'denuncias': reports})
