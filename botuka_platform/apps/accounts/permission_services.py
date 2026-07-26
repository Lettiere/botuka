"""Serviço central de concessão e revogação de permissões individuais."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.permissions import usuario_e_master, usuario_tem_permissao
from apps.core.models import Permissao

from .models import AuditoriaPermissao, ConcessaoPermissao


def _ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '') if request else ''
    return (forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR')) if request else None


def pode_administrar_permissoes(ator):
    return (
        usuario_e_master(ator)
        or ator.tem_perfil('GESTOR')
        or usuario_tem_permissao(ator, 'usuarios.permissoes.gerenciar')
    )


def _validar(ator, beneficiado, permissao):
    if not pode_administrar_permissoes(ator):
        raise PermissionDenied('Usuário sem autoridade para administrar permissões.')
    if ator.pk == beneficiado.pk:
        raise PermissionDenied('Não é permitido alterar as próprias permissões.')
    if beneficiado.tem_perfil('MASTER') and not usuario_e_master(ator):
        raise PermissionDenied('Permissões de MASTER são protegidas.')
    if permissao.protegida and not usuario_e_master(ator):
        raise PermissionDenied('Apenas MASTER pode administrar esta permissão.')
    if not usuario_e_master(ator) and permissao.criticidade >= Permissao.Criticidade.PROTEGIDA:
        raise PermissionDenied('A permissão excede o nível de autoridade do gestor.')


@transaction.atomic
def conceder_permissao(*, ator, beneficiado, permissao, justificativa, request=None, valida_ate=None, observacao=''):
    _validar(ator, beneficiado, permissao)
    if not justificativa.strip():
        raise ValidationError('A justificativa é obrigatória.')
    anterior = {'ativa': beneficiado.tem_permissao(permissao.codigo)}
    concessao, criada = ConcessaoPermissao.objects.get_or_create(
        usuario=beneficiado, permissao=permissao, revogada_em__isnull=True,
        defaults={
            'concedida_por': ator, 'valida_ate': valida_ate,
            'justificativa': justificativa, 'observacao': observacao,
        },
    )
    if not criada:
        raise ValidationError('O usuário já possui uma concessão ativa.')
    AuditoriaPermissao.objects.create(
        usuario_beneficiado=beneficiado, permissao=permissao, ator=ator,
        acao=AuditoriaPermissao.Acao.CONCEDER, ip=_ip(request),
        justificativa=justificativa, estado_anterior=anterior,
        estado_posterior={'ativa': True, 'valida_ate': valida_ate.isoformat() if valida_ate else None},
    )
    return concessao


@transaction.atomic
def revogar_permissao(*, ator, concessao, justificativa, request=None):
    _validar(ator, concessao.usuario, concessao.permissao)
    if concessao.revogada_em:
        raise ValidationError('A concessão já foi revogada.')
    if not justificativa.strip():
        raise ValidationError('A justificativa é obrigatória.')
    concessao.revogada_em = timezone.now()
    concessao.revogada_por = ator
    concessao.save(update_fields=['revogada_em', 'revogada_por', 'atualizado_em'])
    AuditoriaPermissao.objects.create(
        usuario_beneficiado=concessao.usuario, permissao=concessao.permissao,
        ator=ator, acao=AuditoriaPermissao.Acao.REVOGAR, ip=_ip(request),
        justificativa=justificativa, estado_anterior={'ativa': True},
        estado_posterior={'ativa': False, 'revogada_em': concessao.revogada_em.isoformat()},
    )
