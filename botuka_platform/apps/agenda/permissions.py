from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from apps.organizations.models import Empresa
from apps.organizations.permissions import (
    empresas_disponiveis_para_usuario,
    usuario_pode_gerenciar_empresa,
)


def empresa_agenda_autorizada(usuario, empresa_uuid) -> Empresa:
    empresa = get_object_or_404(
        empresas_disponiveis_para_usuario(usuario), uuid=empresa_uuid
    )
    if not usuario_pode_gerenciar_empresa(usuario, empresa):
        raise PermissionDenied
    if not empresa.pode_aceitar_agendamentos:
        raise PermissionDenied
    return empresa


def agenda_empresa_required(view_func):
    @wraps(view_func)
    def wrapper(request, uuid, *args, **kwargs):
        empresa = empresa_agenda_autorizada(request.user, uuid)
        return view_func(request, empresa, *args, **kwargs)

    return wrapper
