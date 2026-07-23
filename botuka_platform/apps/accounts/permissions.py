"""Regras globais de acesso administrativo da plataforma."""

from __future__ import annotations

from typing import Any


MASTER_PROFILE_NAME = 'MASTER'


def usuario_tem_permissao(usuario: Any, codigo: str | None) -> bool:
    """Consulta permissões sem presumir um model de usuário autenticado."""

    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return False
    metodo = getattr(usuario, 'tem_permissao', None)
    if not callable(metodo):
        return False
    return bool(metodo(codigo))


def usuario_e_master(usuario: Any) -> bool:
    """Retorna se o usuário possui autoridade MASTER global.

    Superusuários são tratados como MASTER para manter compatibilidade com o
    backend nativo do Django Admin. Perfis inativos não concedem autoridade.
    """

    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return False
    if getattr(usuario, 'is_superuser', False):
        return True

    perfil = getattr(usuario, 'perfil', None)
    if (
        perfil
        and perfil.ativo
        and perfil.removido_em is None
        and perfil.nome.upper() == MASTER_PROFILE_NAME
    ):
        return True

    if not getattr(usuario, 'pk', None):
        return False

    vinculos = getattr(usuario, 'usuario_perfis_adicionais', None)
    return bool(
        vinculos
        and vinculos.filter(
            perfil__nome__iexact=MASTER_PROFILE_NAME,
            perfil__ativo=True,
            perfil__removido_em__isnull=True,
        ).exists()
    )
