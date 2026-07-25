from django.db.models import Q

from apps.accounts.permissions import usuario_e_master
from apps.organizations.permissions import (
    empresas_disponiveis_para_usuario,
    usuario_pode_publicar_por_empresa,
)


def vagas_administraveis(usuario):
    from .models import Vaga

    if not usuario or not usuario.is_authenticated:
        return Vaga.objects.none()
    if usuario_e_master(usuario):
        return Vaga.objects.all()
    return Vaga.objects.filter(
        Q(empresa__in=empresas_disponiveis_para_usuario(usuario))
        | Q(perfil_pessoa_fisica=usuario)
    ).distinct()


def pode_administrar_vaga(usuario, vaga):
    if usuario_e_master(usuario):
        return True
    if vaga.empresa_id:
        return usuario_pode_publicar_por_empresa(usuario, vaga.empresa)
    return vaga.perfil_pessoa_fisica_id == getattr(usuario, 'id', None)


def pode_publicar_vaga(usuario, vaga):
    return pode_administrar_vaga(usuario, vaga)
