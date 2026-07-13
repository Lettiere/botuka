"""Serviços de conta e autenticação."""

from __future__ import annotations

from django.urls import reverse


def obter_url_pos_login(usuario: object) -> str:
    """Retorna a URL adequada após login conforme perfil e vínculos."""

    tem_perfil = getattr(usuario, 'tem_perfil', None)

    if getattr(usuario, 'is_superuser', False) or (
        callable(tem_perfil) and tem_perfil('MASTER')
    ):
        return reverse('gestao:dashboard')

    if callable(tem_perfil):
        if tem_perfil('PRESTADOR'):
            return reverse('painel:servicos_lista')
        if tem_perfil('EMPRESA'):
            return reverse('painel:empresas_lista')
        if tem_perfil('CANDIDATO'):
            return reverse('painel:curriculo')

    possui_empresa = False
    if getattr(usuario, 'is_authenticated', False):
        possui_empresa = (
            usuario.organizacoes.exists()
            or usuario.organizacoes_proprietario.exists()
        )

    if possui_empresa:
        return reverse('painel:dashboard')

    return reverse('painel:dashboard')
