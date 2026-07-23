"""Operações críticas institucionais, sempre autorizadas e auditadas."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.accounts.permissions import usuario_e_master, usuario_tem_permissao
from apps.core.audit_service import registrar_auditoria
from apps.core.models import Perfil
from apps.organizations.authorization import (
    MEMBER_PERMISSIONS, membro_possui_permissao, vinculo_organizacional,
)
from apps.organizations.models import (
    Capacidade, Empresa, EmpresaCapacidade, EmpresaUsuario,
    EmpresaUsuarioPermissao, StatusCapacidadeMixin,
)


def _pode_gerenciar_institucional(usuario) -> bool:
    return usuario_e_master(usuario) or bool(
        usuario and getattr(usuario, 'is_authenticated', False)
        and usuario_tem_permissao(usuario, 'institucional.gerenciar')
    )


def _pode_gerenciar_capacidades(usuario) -> bool:
    return usuario_e_master(usuario) or bool(
        usuario and getattr(usuario, 'is_authenticated', False)
        and usuario_tem_permissao(usuario, 'capacidades.gerenciar')
    )


def _negar(*, executor, acao, entidade, organizacao=None, motivo, request=None):
    registrar_auditoria(
        executor=executor, acao=acao, entidade=entidade, organizacao=organizacao,
        sucesso=False, motivo=motivo, origem='PAINEL', request=request,
    )
    raise PermissionDenied(motivo)


def atualizar_identidade_institucional(*, executor, empresa: Empresa, dados: dict, request=None):
    if not _pode_gerenciar_institucional(executor):
        _negar(executor=executor, acao='INSTITUCIONAL_ALTERAR_NEGADO', entidade=empresa, organizacao=empresa, motivo='Sem autorização institucional.', request=request)
    with transaction.atomic():
        campos = {
            'tipo_organizacao', 'status_institucional', 'institucional', 'oficial',
            'parceira_oficial', 'selo_oficial', 'verificada_institucionalmente',
            'observacao_institucional',
        }
        anterior = {campo: getattr(empresa, campo) for campo in campos}
        for campo in campos.intersection(dados):
            setattr(empresa, campo, dados[campo])
        empresa.autorizada_por = executor
        empresa.autorizada_em = timezone.now()
        empresa.save(update_fields=[*campos, 'autorizada_por', 'autorizada_em', 'atualizado_em'])
        novo = {campo: getattr(empresa, campo) for campo in campos}
        registrar_auditoria(executor=executor, acao='INSTITUCIONAL_ALTERAR', entidade=empresa, organizacao=empresa, anterior=anterior, novo=novo, request=request)
    return empresa


def conceder_capacidade(*, executor, empresa: Empresa, codigo: str, request=None):
    if not _pode_gerenciar_capacidades(executor):
        _negar(executor=executor, acao='CAPACIDADE_CONCEDER_NEGADO', entidade=empresa, organizacao=empresa, motivo='Sem autorização para conceder capacidade.', request=request)
    with transaction.atomic():
        capacidade = Capacidade.objects.get(codigo=codigo, ativo=True)
        vinculo, _ = EmpresaCapacidade.objects.update_or_create(
            empresa=empresa, capacidade=capacidade,
            defaults={'status': StatusCapacidadeMixin.Status.APROVADA, 'ativo': True, 'aprovado_por': executor, 'aprovado_em': timezone.now(), 'motivo_rejeicao': ''},
        )
        registrar_auditoria(executor=executor, acao='CAPACIDADE_CONCEDER', entidade=vinculo, organizacao=empresa, novo={'capacidade': codigo, 'status': vinculo.status}, request=request)
    return vinculo


def revogar_capacidade(*, executor, empresa: Empresa, codigo: str, motivo: str = '', request=None):
    if not _pode_gerenciar_capacidades(executor):
        _negar(executor=executor, acao='CAPACIDADE_REVOGAR_NEGADO', entidade=empresa, organizacao=empresa, motivo='Sem autorização para revogar capacidade.', request=request)
    with transaction.atomic():
        vinculo = EmpresaCapacidade.objects.select_related('capacidade').get(empresa=empresa, capacidade__codigo=codigo)
        anterior = {'status': vinculo.status, 'ativo': vinculo.ativo}
        vinculo.status = StatusCapacidadeMixin.Status.SUSPENSA
        vinculo.ativo = False
        vinculo.motivo_rejeicao = motivo
        vinculo.save(update_fields=['status', 'ativo', 'motivo_rejeicao', 'atualizado_em'])
        registrar_auditoria(executor=executor, acao='CAPACIDADE_REVOGAR', entidade=vinculo, organizacao=empresa, anterior=anterior, novo={'status': vinculo.status, 'ativo': False}, motivo=motivo, request=request)
    return vinculo


def atribuir_papel_global(*, executor, usuario, papel: str, request=None):
    papel = papel.upper()
    if not usuario_e_master(executor):
        _negar(executor=executor, acao='PAPEL_GLOBAL_CONCEDER_NEGADO', entidade=usuario, motivo='Somente MASTER concede papéis globais.', request=request)
    if executor.pk == usuario.pk:
        _negar(executor=executor, acao='AUTOELEVACAO_NEGADA', entidade=usuario, motivo='Autoelevação não é permitida.', request=request)
    if papel not in {'MASTER', 'ADMIN_GLOBAL', 'SUPORTE_GLOBAL', 'AUDITOR_GLOBAL'}:
        raise ValueError('Papel global inválido.')
    with transaction.atomic():
        perfil = Perfil.objects.get(nome=papel, ativo=True)
        usuario.perfil = perfil
        if papel == 'MASTER':
            usuario.is_active = True
            usuario.is_staff = True
            usuario.is_superuser = True
        usuario.save(update_fields=['perfil', 'is_active', 'is_staff', 'is_superuser', 'atualizado_em'])
        registrar_auditoria(executor=executor, acao='PAPEL_GLOBAL_CONCEDER', entidade=usuario, novo={'papel': papel}, request=request)
    return usuario


def revogar_papel_global(*, executor, usuario, request=None):
    if not usuario_e_master(executor):
        _negar(executor=executor, acao='PAPEL_GLOBAL_REVOGAR_NEGADO', entidade=usuario, motivo='Somente MASTER revoga papéis globais.', request=request)
    if executor.pk == usuario.pk:
        _negar(executor=executor, acao='AUTO_REVOGACAO_NEGADA', entidade=usuario, motivo='MASTER não pode remover o próprio papel.', request=request)
    anterior = {'papel': getattr(usuario.perfil, 'nome', None)}
    with transaction.atomic():
        usuario.perfil = None
        usuario.is_staff = False
        usuario.is_superuser = False
        usuario.save(update_fields=['perfil', 'is_staff', 'is_superuser', 'atualizado_em'])
        registrar_auditoria(executor=executor, acao='PAPEL_GLOBAL_REVOGAR', entidade=usuario, anterior=anterior, request=request)
    return usuario


def convidar_membro(*, executor, empresa, usuario, funcao, escopo=EmpresaUsuario.Escopo.ORGANIZACAO, request=None):
    ator = vinculo_organizacional(executor, empresa)
    permitido = usuario_e_master(executor) or (
        ator and membro_possui_permissao(ator, 'ORGANIZACAO_CONVIDAR_MEMBRO')
    )
    if not permitido:
        _negar(executor=executor, acao='MEMBRO_CONVIDAR_NEGADO', entidade=empresa, organizacao=empresa, motivo='Sem autorização para convidar membro.', request=request)
    if funcao == EmpresaUsuario.Funcao.ADMINISTRADOR_INSTITUCIONAL and not usuario_e_master(executor):
        _negar(executor=executor, acao='ADMIN_INSTITUCIONAL_CONVIDAR_NEGADO', entidade=empresa, organizacao=empresa, motivo='Somente MASTER nomeia administrador institucional.', request=request)
    if escopo == EmpresaUsuario.Escopo.GLOBAL and not usuario_e_master(executor):
        _negar(executor=executor, acao='ESCOPO_GLOBAL_NEGADO', entidade=empresa, organizacao=empresa, motivo='Escopo global é reservado a papéis globais.', request=request)
    with transaction.atomic():
        vinculo, _ = EmpresaUsuario.objects.update_or_create(
            empresa=empresa, usuario=usuario,
            defaults={'funcao': funcao, 'escopo': escopo, 'ativo': True, 'convidado_por': executor, 'autorizado_por': executor},
        )
        registrar_auditoria(executor=executor, acao='MEMBRO_CONVIDAR', entidade=vinculo, organizacao=empresa, novo={'funcao': funcao, 'escopo': escopo}, request=request)
    return vinculo


def definir_permissao_membro(*, executor, vinculo, codigo, permitido=True, request=None):
    codigo = codigo.upper()
    if codigo not in MEMBER_PERMISSIONS:
        raise ValueError('Permissão organizacional inválida.')
    ator = vinculo_organizacional(executor, vinculo.empresa)
    autorizado = usuario_e_master(executor) or (
        ator and membro_possui_permissao(ator, 'PERMISSAO_DELEGAR')
    )
    if not autorizado:
        _negar(executor=executor, acao='PERMISSAO_DELEGAR_NEGADO', entidade=vinculo, organizacao=vinculo.empresa, motivo='Sem autorização para delegar permissão.', request=request)
    with transaction.atomic():
        regra, _ = EmpresaUsuarioPermissao.objects.update_or_create(
            empresa_usuario=vinculo, codigo=codigo, defaults={'permitido': permitido},
        )
        registrar_auditoria(executor=executor, acao='PERMISSAO_DELEGAR', entidade=regra, organizacao=vinculo.empresa, novo={'codigo': codigo, 'permitido': permitido}, request=request)
    return regra
