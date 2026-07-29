"""Regras globais de acesso administrativo da plataforma."""

from __future__ import annotations

from typing import Any


MASTER_PROFILE_NAME = 'MASTER'


def usuario_tem_permissao(usuario: Any, codigo: str | None) -> bool:
    """Ponto público compatível, encaminhado à autorização central."""

    from apps.accounts.authorization import pode

    return pode(usuario, codigo)


def usuario_e_master(usuario: Any) -> bool:
    """Retorna se o usuário possui autoridade MASTER global.

    Superusuários são tratados como MASTER para manter compatibilidade com o
    backend nativo do Django Admin. Perfis inativos não concedem autoridade.
    """

    cached = getattr(usuario, '_botuka_master_cache', None)
    if cached is not None:
        return cached
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return False
    if getattr(usuario, 'is_superuser', False):
        usuario._botuka_master_cache = True
        return True

    perfil = getattr(usuario, 'perfil', None)
    if (
        perfil
        and perfil.ativo
        and perfil.removido_em is None
        and perfil.nome.upper() == MASTER_PROFILE_NAME
    ):
        usuario._botuka_master_cache = True
        return True

    if not getattr(usuario, 'pk', None):
        return False

    vinculos = getattr(usuario, 'usuario_perfis_adicionais', None)
    result = bool(
        vinculos
        and vinculos.filter(
            perfil__nome__iexact=MASTER_PROFILE_NAME,
            perfil__ativo=True,
            perfil__removido_em__isnull=True,
        ).exists()
    )
    usuario._botuka_master_cache = result
    return result
