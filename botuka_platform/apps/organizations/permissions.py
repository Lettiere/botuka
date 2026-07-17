"""Permissões reutilizáveis para empresas."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q, QuerySet

from apps.organizations.models import Empresa, EmpresaUsuario


def _usuario_admin_global(usuario) -> bool:
    return bool(
        usuario
        and usuario.is_authenticated
        and (usuario.is_superuser or usuario.is_staff)
    )


def empresas_disponiveis_para_usuario(usuario) -> QuerySet[Empresa]:
    """Retorna empresas que o usuário pode visualizar."""

    queryset = Empresa.objects.select_related(
        'usuario_proprietario',
        'categoria_empresa',
        'cidade',
        'estado',
    ).prefetch_related('usuarios_vinculados')

    if _usuario_admin_global(usuario):
        return queryset

    if not usuario or not usuario.is_authenticated:
        return Empresa.objects.none()

    return queryset.filter(
        Q(usuario_proprietario=usuario)
        | Q(usuarios_vinculados__usuario=usuario, usuarios_vinculados__ativo=True)
    ).distinct()


def _vinculo_ativo(usuario, empresa: Empresa) -> EmpresaUsuario | None:
    if not usuario or not usuario.is_authenticated:
        return None

    return (
        EmpresaUsuario.objects.filter(
            empresa=empresa,
            usuario=usuario,
            ativo=True,
        )
        .select_related('empresa', 'usuario')
        .first()
    )


def usuario_pode_visualizar_empresa(usuario, empresa: Empresa) -> bool:
    if _usuario_admin_global(usuario):
        return True

    return bool(
        empresa.usuario_proprietario_id == getattr(usuario, 'id', None)
        or _vinculo_ativo(usuario, empresa)
    )


def usuario_pode_editar_empresa(usuario, empresa: Empresa) -> bool:
    if _usuario_admin_global(usuario):
        return True

    if empresa.usuario_proprietario_id == getattr(usuario, 'id', None):
        return True

    vinculo = _vinculo_ativo(usuario, empresa)
    return bool(vinculo and (vinculo.proprietario or vinculo.administrador or vinculo.pode_editar))


def usuario_pode_gerenciar_empresa(usuario, empresa: Empresa) -> bool:
    if _usuario_admin_global(usuario):
        return True

    if empresa.usuario_proprietario_id == getattr(usuario, 'id', None):
        return True

    vinculo = _vinculo_ativo(usuario, empresa)
    return bool(vinculo and (vinculo.proprietario or vinculo.administrador))


def usuario_pode_gerenciar_equipe(usuario, empresa: Empresa) -> bool:
    if _usuario_admin_global(usuario):
        return True

    if empresa.usuario_proprietario_id == getattr(usuario, 'id', None):
        return True

    vinculo = _vinculo_ativo(usuario, empresa)
    return bool(
        vinculo
        and (
            vinculo.proprietario
            or vinculo.administrador
            or vinculo.pode_gerenciar_equipe
        )
    )


def usuario_pode_publicar_por_empresa(usuario, empresa: Empresa) -> bool:
    if _usuario_admin_global(usuario):
        return True

    if empresa.usuario_proprietario_id == getattr(usuario, 'id', None):
        return True

    vinculo = _vinculo_ativo(usuario, empresa)
    return bool(
        vinculo
        and (
            vinculo.proprietario
            or vinculo.administrador
            or vinculo.pode_publicar_servico
        )
    )


class EmpresaAcessoMixin(LoginRequiredMixin):
    """Mixin para views baseadas em classe que carregam empresa autorizada."""

    empresa_kwarg = 'pk'

    def get_empresa_queryset(self):
        return empresas_disponiveis_para_usuario(self.request.user)

    def get_empresa(self):
        pk = self.kwargs.get(self.empresa_kwarg)
        empresa = self.get_empresa_queryset().filter(pk=pk).first()
        if not empresa:
            raise PermissionDenied
        return empresa
