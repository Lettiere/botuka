"""Regra central de autorização por identidade, organização e escopo."""

from __future__ import annotations

from dataclasses import dataclass

from apps.accounts.permissions import usuario_e_master, usuario_tem_permissao
from apps.organizations.models import (
    Empresa, EmpresaCapacidade, EmpresaUsuario, EmpresaUsuarioPermissao,
    StatusCapacidadeMixin,
)


GLOBAL_ROLES = frozenset({'MASTER', 'ADMIN_GLOBAL', 'SUPORTE_GLOBAL', 'AUDITOR_GLOBAL'})
MEMBER_PERMISSIONS = frozenset({
    'ORGANIZACAO_VISUALIZAR', 'ORGANIZACAO_EDITAR',
    'ORGANIZACAO_GERENCIAR_EQUIPE', 'ORGANIZACAO_CONVIDAR_MEMBRO',
    'ORGANIZACAO_REMOVER_MEMBRO', 'CONTEUDO_CRIAR',
    'CONTEUDO_EDITAR_PROPRIO', 'CONTEUDO_EDITAR_EQUIPE',
    'CONTEUDO_REVISAR', 'CONTEUDO_APROVAR', 'CONTEUDO_PUBLICAR',
    'CONTEUDO_DESPUBLICAR', 'CONTEUDO_ARQUIVAR', 'CONTEUDO_EXCLUIR',
    'EVENTO_CRIAR', 'EVENTO_EDITAR', 'EVENTO_PUBLICAR', 'VAGA_CRIAR',
    'VAGA_EDITAR', 'VAGA_PUBLICAR', 'ATLETA_GERENCIAR',
    'CLUBE_GERENCIAR', 'CAMPEONATO_CRIAR', 'CAMPEONATO_EDITAR',
    'CAMPEONATO_PUBLICAR', 'JOGO_REGISTRAR', 'RESULTADO_REGISTRAR',
    'RESULTADO_HOMOLOGAR', 'YTV_CRIAR', 'YTV_EDITAR', 'YTV_PUBLICAR',
    'PERMISSAO_DELEGAR',
})
GLOBAL_SCOPE = EmpresaUsuario.Escopo.GLOBAL


@dataclass(frozen=True)
class AuthorizationContext:
    usuario: object
    organizacao: Empresa
    vinculo: EmpresaUsuario | None
    capacidade: str | None = None
    permissao: str | None = None


def usuario_tem_papel_global(usuario, papel: str) -> bool:
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return False
    if papel.upper() == 'MASTER':
        return usuario_e_master(usuario)
    return usuario.tem_perfil(papel.upper())


def vinculo_organizacional(usuario, organizacao: Empresa) -> EmpresaUsuario | None:
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return None
    return EmpresaUsuario.objects.filter(
        empresa=organizacao, usuario=usuario, ativo=True,
    ).select_related('empresa', 'usuario').first()


def organizacao_possui_capacidade(organizacao: Empresa, codigo: str) -> bool:
    return EmpresaCapacidade.objects.filter(
        empresa=organizacao,
        capacidade__codigo=codigo,
        capacidade__ativo=True,
        status=StatusCapacidadeMixin.Status.APROVADA,
        ativo=True,
    ).exists()


def membro_possui_permissao(vinculo: EmpresaUsuario, codigo: str) -> bool:
    permissao = EmpresaUsuarioPermissao.objects.filter(
        empresa_usuario=vinculo, codigo=codigo,
    ).first()
    if permissao is not None:
        return permissao.permitido

    if vinculo.proprietario or vinculo.funcao == EmpresaUsuario.Funcao.PROPRIETARIO:
        return codigo in {
            'ORGANIZACAO_VISUALIZAR', 'ORGANIZACAO_EDITAR',
            'ORGANIZACAO_GERENCIAR_EQUIPE', 'ORGANIZACAO_CONVIDAR_MEMBRO',
            'ORGANIZACAO_REMOVER_MEMBRO', 'CONTEUDO_CRIAR',
            'CONTEUDO_EDITAR_PROPRIO', 'CONTEUDO_EDITAR_EQUIPE',
            'VAGA_CRIAR', 'VAGA_EDITAR', 'VAGA_PUBLICAR',
        }
    legacy = {
        'ORGANIZACAO_VISUALIZAR': True,
        'ORGANIZACAO_EDITAR': vinculo.pode_editar,
        'ORGANIZACAO_GERENCIAR_EQUIPE': vinculo.pode_gerenciar_equipe,
        'CONTEUDO_PUBLICAR': vinculo.pode_publicar_servico,
    }
    return bool(legacy.get(codigo, False))


def acao_autorizada(
    usuario,
    organizacao: Empresa,
    *,
    capacidade: str | None = None,
    permissao: str | None = None,
    autor_id: int | None = None,
) -> bool:
    """Aplica a equação central de autorização do BOTUKA."""

    if usuario_e_master(usuario):
        return True
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return False

    # Papéis globais não recebem poder implícito: exigem permissão de domínio.
    if usuario_tem_papel_global(usuario, 'ADMIN_GLOBAL') and permissao:
        if usuario_tem_permissao(usuario, f'organizacao.{permissao.lower()}'):
            return not capacidade or usuario_tem_permissao(usuario, f'capacidade.{capacidade.lower()}')

    vinculo = vinculo_organizacional(usuario, organizacao)
    if not vinculo:
        return False
    if vinculo.escopo == EmpresaUsuario.Escopo.PROPRIO and autor_id not in {None, usuario.id}:
        return False
    if vinculo.escopo == EmpresaUsuario.Escopo.GLOBAL:
        return False
    if capacidade and not organizacao_possui_capacidade(organizacao, capacidade):
        return False
    if permissao and not membro_possui_permissao(vinculo, permissao):
        return False
    return True


def organizacoes_no_escopo(usuario):
    if usuario_e_master(usuario):
        return Empresa.objects.all()
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return Empresa.objects.none()
    return Empresa.objects.filter(
        usuarios_vinculados__usuario=usuario,
        usuarios_vinculados__ativo=True,
    ).distinct()
