"""Páginas públicas e redirecionamentos curtos de serviços e empresas."""

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.organizations.models import Empresa
from apps.services.models import Servico


def servico_publico(request, slug):
    servico = get_object_or_404(
        Servico.objects.select_related('empresa', 'usuario_responsavel').prefetch_related('links'),
        slug=slug,
        ativo=True,
        status=Servico.Status.PUBLICADO,
        excluido_em__isnull=True,
    )
    if servico.empresa_id and not servico.empresa.pode_publicar_servico:
        raise Http404
    links = servico.links.filter(ativo=True, excluido_em__isnull=True).order_by('-destaque', 'ordem')
    return render(request, 'publico/servicos/detalhe.html', {'servico': servico, 'links': links, 'videos': [link for link in links if link.url_embed][:6]})


def empresa_publica(request, slug):
    empresa = get_object_or_404(
        Empresa.objects.prefetch_related('links'),
        slug=slug,
        ativo=True,
        perfil_publico=True,
        status=Empresa.Status.ATIVA,
    )
    links = empresa.links.filter(ativo=True, excluido_em__isnull=True).order_by('-destaque', 'ordem')
    return render(request, 'publico/empresas/detalhe.html', {'empresa': empresa, 'links': links, 'videos': [link for link in links if link.url_embed][:6]})


def qrcode_servico_redirect(request, token):
    servico = get_object_or_404(Servico, qr_token=token, qr_ativo=True, ativo=True, status=Servico.Status.PUBLICADO, excluido_em__isnull=True)
    if servico.empresa_id and not servico.empresa.pode_publicar_servico:
        raise Http404
    return redirect('publico:servico', slug=servico.slug, permanent=False)


def qrcode_empresa_redirect(request, token):
    empresa = get_object_or_404(Empresa, qr_token=token, qr_ativo=True, ativo=True, perfil_publico=True, status=Empresa.Status.ATIVA)
    return redirect('publico:empresa', slug=empresa.slug, permanent=False)
