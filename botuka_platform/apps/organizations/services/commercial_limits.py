from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.permissions import usuario_e_master
from apps.core.audit_service import registrar_auditoria
from apps.organizations.models import UsuarioLimitePersonalizado


def _snapshot(obj):
    if not obj:
        return {}
    return {
        'ativo': obj.ativo,
        'empresas_ilimitadas': obj.empresas_ilimitadas,
        'servicos_ilimitados': obj.servicos_ilimitados,
        'limite_empresas': obj.limite_empresas,
        'limite_servicos': obj.limite_servicos,
        'inicio': obj.inicio.isoformat() if obj.inicio else None,
        'fim': obj.fim.isoformat() if obj.fim else None,
        'motivo': obj.motivo,
        'observacoes': obj.observacoes,
    }


def _exigir_master(*, executor, usuario, acao, request=None):
    if usuario_e_master(executor):
        return
    registrar_auditoria(
        executor=executor, acao=f'{acao}_NEGADO', entidade=usuario,
        sucesso=False, motivo='Somente MASTER gerencia limites comerciais.',
        origem='PAINEL_MASTER', request=request,
    )
    raise PermissionDenied('Somente MASTER gerencia limites comerciais.')


def salvar_limite_personalizado(*, executor, usuario, dados, request=None):
    _exigir_master(
        executor=executor, usuario=usuario,
        acao='LIMITE_PERSONALIZADO_SALVAR', request=request,
    )
    with transaction.atomic():
        existente = UsuarioLimitePersonalizado.objects.select_for_update().filter(
            usuario=usuario,
        ).first()
        anterior = _snapshot(existente)
        limite = existente or UsuarioLimitePersonalizado(usuario=usuario)
        for campo in (
            'ativo', 'empresas_ilimitadas', 'servicos_ilimitados',
            'limite_empresas', 'limite_servicos', 'inicio', 'fim',
            'motivo', 'observacoes',
        ):
            setattr(limite, campo, dados[campo])
        limite.concedido_por = executor
        limite.save()
        registrar_auditoria(
            executor=executor,
            acao='LIMITE_PERSONALIZADO_ALTERAR' if existente else 'LIMITE_PERSONALIZADO_CONCEDER',
            entidade=limite, anterior=anterior, novo=_snapshot(limite),
            motivo=limite.motivo, origem='PAINEL_MASTER', request=request,
        )
    return limite


def suspender_limite_personalizado(*, executor, usuario, motivo='', request=None):
    _exigir_master(
        executor=executor, usuario=usuario,
        acao='LIMITE_PERSONALIZADO_SUSPENDER', request=request,
    )
    with transaction.atomic():
        limite = UsuarioLimitePersonalizado.objects.select_for_update().get(usuario=usuario)
        anterior = _snapshot(limite)
        limite.ativo = False
        if motivo:
            limite.motivo = motivo
        limite.concedido_por = executor
        limite.save(update_fields=('ativo', 'motivo', 'concedido_por', 'atualizado_em'))
        registrar_auditoria(
            executor=executor, acao='LIMITE_PERSONALIZADO_SUSPENDER',
            entidade=limite, anterior=anterior, novo=_snapshot(limite),
            motivo=limite.motivo, origem='PAINEL_MASTER', request=request,
        )
    return limite


remover_limite_personalizado = suspender_limite_personalizado
