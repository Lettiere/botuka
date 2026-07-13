"""Decorators e mixins de acesso do painel de gestão."""

from __future__ import annotations

from functools import wraps
from typing import Callable

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse


def usuario_pode_acessar_gestao(user: object) -> bool:
    """Valida acesso base ao painel interno."""

    if not getattr(user, 'is_authenticated', False):
        return False

    if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
        return True

    tem_perfil = getattr(user, 'tem_perfil', None)
    return bool(callable(tem_perfil) and tem_perfil('MASTER'))


def staff_required(view_func: Callable) -> Callable:
    """Exige usuário autenticado com acesso administrativo."""

    @login_required
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        if usuario_pode_acessar_gestao(request.user):
            return view_func(request, *args, **kwargs)

        messages.error(request, 'Você não tem permissão para acessar a gestão.')
        raise PermissionDenied

    return wrapper


def master_required(view_func: Callable) -> Callable:
    """Exige superusuário ou perfil MASTER."""

    @login_required
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        tem_perfil = getattr(request.user, 'tem_perfil', None)
        if request.user.is_superuser or (callable(tem_perfil) and tem_perfil('MASTER')):
            return view_func(request, *args, **kwargs)

        messages.error(request, 'Ação restrita ao perfil MASTER.')
        raise PermissionDenied

    return wrapper


def permission_required(codigo: str) -> Callable:
    """Exige permissão de domínio pelo código informado."""

    def decorator(view_func: Callable) -> Callable:
        @login_required
        @wraps(view_func)
        def wrapper(
            request: HttpRequest,
            *args: object,
            **kwargs: object,
        ) -> HttpResponse:
            tem_permissao = getattr(request.user, 'tem_permissao', None)
            if callable(tem_permissao) and tem_permissao(codigo):
                return view_func(request, *args, **kwargs)

            messages.error(request, 'Você não possui permissão para esta ação.')
            raise PermissionDenied

        return wrapper

    return decorator


class StaffRequiredMixin(LoginRequiredMixin):
    """Mixin base para views do painel interno."""

    def dispatch(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        if usuario_pode_acessar_gestao(request.user):
            return super().dispatch(request, *args, **kwargs)

        messages.error(request, 'Você não tem permissão para acessar a gestão.')
        raise PermissionDenied


class DomainPermissionRequiredMixin(StaffRequiredMixin):
    """Mixin para validar permissões de domínio em class-based views."""

    permission_code: str | None = None

    def dispatch(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        tem_permissao = getattr(request.user, 'tem_permissao', None)
        if self.permission_code and not (
            callable(tem_permissao) and tem_permissao(self.permission_code)
        ):
            messages.error(request, 'Você não possui permissão para esta ação.')
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)
