from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.organizations.permissions import usuario_pode_publicar_por_empresa
from apps.services.models import Servico


def _usuario_admin_global(usuario) -> bool:
    return bool(
        usuario
        and usuario.is_authenticated
        and (usuario.is_staff or usuario.is_superuser)
    )


def servicos_disponiveis_para_usuario(usuario) -> QuerySet[Servico]:
    queryset = Servico.objects.select_related(
        'usuario_responsavel',
        'empresa',
        'setor',
        'profissao',
        'tipo_servico',
        'forma_cobranca',
    )

    if _usuario_admin_global(usuario):
        return queryset

    if not usuario or not usuario.is_authenticated:
        return Servico.objects.none()

    return queryset.filter(
        Q(usuario_responsavel=usuario)
        | Q(empresa__usuario_proprietario=usuario)
        | Q(
            empresa__usuarios_vinculados__usuario=usuario,
            empresa__usuarios_vinculados__ativo=True,
            empresa__usuarios_vinculados__administrador=True,
        )
        | Q(
            empresa__usuarios_vinculados__usuario=usuario,
            empresa__usuarios_vinculados__ativo=True,
            empresa__usuarios_vinculados__proprietario=True,
        )
        | Q(
            empresa__usuarios_vinculados__usuario=usuario,
            empresa__usuarios_vinculados__ativo=True,
            empresa__usuarios_vinculados__pode_editar=True,
        )
    ).distinct()


def usuario_pode_visualizar_servico(usuario, servico: Servico) -> bool:
    if _usuario_admin_global(usuario):
        return True
    if servico.usuario_responsavel_id == getattr(usuario, 'id', None):
        return True
    return bool(servico.empresa_id and usuario_pode_publicar_por_empresa(usuario, servico.empresa))


def usuario_pode_editar_servico(usuario, servico: Servico) -> bool:
    return usuario_pode_visualizar_servico(usuario, servico)


def usuario_pode_publicar_servico(usuario, servico: Servico) -> bool:
    if _usuario_admin_global(usuario):
        return True
    if servico.prestador_tipo == Servico.PrestadorTipo.PESSOA_FISICA:
        return servico.usuario_responsavel_id == getattr(usuario, 'id', None)
    return bool(servico.empresa_id and usuario_pode_publicar_por_empresa(usuario, servico.empresa))


def usuario_pode_responder_avaliacao(usuario, servico: Servico) -> bool:
    return usuario_pode_editar_servico(usuario, servico)
