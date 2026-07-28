"""Páginas públicas e redirecionamentos curtos de serviços e empresas."""

from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.organizations.models import Empresa
from apps.services.models import Servico, ServicoImagem, Setor
from apps.core.seo.page_builders import empresa_seo, listing_seo, servico_seo


def empresas_publicas(request):
    queryset = Empresa.objects.filter(ativo=True, perfil_publico=True, status=Empresa.Status.ATIVA, excluido_em__isnull=True).select_related('categoria_empresa', 'cidade', 'estado')
    q = request.GET.get('q', '').strip()[:100]
    if q:
        queryset = queryset.filter(Q(nome_fantasia__icontains=q) | Q(razao_social__icontains=q) | Q(descricao_curta__icontains=q) | Q(categoria_empresa__nome__icontains=q) | Q(bairro__icontains=q))
    if request.GET.get('categoria'): queryset = queryset.filter(categoria_empresa__slug=request.GET['categoria'][:100])
    if request.GET.get('bairro'): queryset = queryset.filter(bairro__iexact=request.GET['bairro'][:100])
    if request.GET.get('verificada') == '1': queryset = queryset.filter(verificada=True)
    queryset = queryset.order_by('nome_fantasia' if request.GET.get('ordem') == 'az' else '-atualizado_em')
    page = Paginator(queryset, 12).get_page(request.GET.get('page'))
    categorias = Empresa.objects.filter(ativo=True, perfil_publico=True, status=Empresa.Status.ATIVA, categoria_empresa__isnull=False).values('categoria_empresa__slug', 'categoria_empresa__nome').distinct().order_by('categoria_empresa__nome')
    seo = listing_seo(request, 'Empresas em Botucatu | BOTUKA', 'Encontre empresas, negócios e organizações com perfil público em Botucatu.')
    return render(request, 'publico/empresas/lista.html', {'page_obj': page, 'empresas': page.object_list, 'categorias': categorias, 'total': page.paginator.count, 'seo': seo})


def servicos_publicos(request):
    queryset = Servico.objects.filter(ativo=True, status=Servico.Status.PUBLICADO, excluido_em__isnull=True, publicado_em__isnull=False).filter(Q(empresa__isnull=True) | Q(empresa__ativo=True, empresa__perfil_publico=True, empresa__status=Empresa.Status.ATIVA, empresa__excluido_em__isnull=True)).select_related('empresa', 'setor', 'profissao', 'tipo_servico').prefetch_related(Prefetch('imagens', queryset=ServicoImagem.objects.filter(ativo=True, excluido_em__isnull=True).order_by('-principal', 'ordem')))
    q = request.GET.get('q', '').strip()[:100]
    if q:
        queryset = queryset.filter(Q(titulo__icontains=q) | Q(descricao_curta__icontains=q) | Q(descricao_completa__icontains=q) | Q(setor__nome__icontains=q) | Q(profissao__nome__icontains=q) | Q(empresa__nome_fantasia__icontains=q))
    if request.GET.get('categoria'): queryset = queryset.filter(setor__slug=request.GET['categoria'][:100])
    if request.GET.get('prestador') in Servico.PrestadorTipo.values: queryset = queryset.filter(prestador_tipo=request.GET['prestador'])
    if request.GET.get('remoto') == '1': queryset = queryset.filter(atendimento_remoto=True)
    if request.GET.get('presencial') == '1': queryset = queryset.filter(atendimento_presencial=True)
    queryset = queryset.order_by('titulo' if request.GET.get('ordem') == 'az' else '-publicado_em')
    page = Paginator(queryset, 12).get_page(request.GET.get('page'))
    seo = listing_seo(request, 'Serviços em Botucatu | BOTUKA', 'Encontre serviços, profissionais e empresas prestadoras em Botucatu.')
    return render(request, 'publico/servicos/lista.html', {'page_obj': page, 'servicos': page.object_list, 'categorias': Setor.objects.filter(ativo=True), 'total': page.paginator.count, 'seo': seo})


def servico_publico(request, slug):
    servico = get_object_or_404(
        Servico.objects.select_related('empresa', 'usuario_responsavel', 'tipo_servico').prefetch_related('links', Prefetch('imagens', queryset=ServicoImagem.objects.filter(ativo=True, excluido_em__isnull=True).order_by('-principal', 'ordem'))),
        slug=slug,
        ativo=True,
        status=Servico.Status.PUBLICADO,
        excluido_em__isnull=True,
    )
    if servico.empresa_id and not servico.empresa.pode_publicar_servico:
        raise Http404
    links = servico.links.filter(ativo=True, excluido_em__isnull=True).order_by('-destaque', 'ordem')
    return render(request, 'publico/servicos/detalhe.html', {'servico': servico, 'share_object': servico, 'share_type': 'servico', 'links': links, 'videos': [link for link in links if link.url_embed][:6], 'seo': servico_seo(request, servico)})


def empresa_publica(request, slug):
    empresa = get_object_or_404(
        Empresa.objects.prefetch_related('links'),
        slug=slug,
        ativo=True,
        perfil_publico=True,
        status=Empresa.Status.ATIVA,
    )
    links = empresa.links.filter(ativo=True, excluido_em__isnull=True).order_by('-destaque', 'ordem')
    return render(request, 'publico/empresas/detalhe.html', {'empresa': empresa, 'share_object': empresa, 'share_type': 'empresa', 'links': links, 'videos': [link for link in links if link.url_embed][:6], 'seo': empresa_seo(request, empresa)})


def qrcode_servico_redirect(request, token):
    servico = get_object_or_404(Servico, qr_token=token, qr_ativo=True, ativo=True, status=Servico.Status.PUBLICADO, excluido_em__isnull=True)
    if servico.empresa_id and not servico.empresa.pode_publicar_servico:
        raise Http404
    return redirect('publico:servico', slug=servico.slug, permanent=False)


def qrcode_empresa_redirect(request, token):
    empresa = get_object_or_404(Empresa, qr_token=token, qr_ativo=True, ativo=True, perfil_publico=True, status=Empresa.Status.ATIVA)
    return redirect('publico:empresa', slug=empresa.slug, permanent=False)
