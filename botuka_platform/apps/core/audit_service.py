"""Registro uniforme de ações críticas e tentativas proibidas."""

from __future__ import annotations

from apps.core.models import Auditoria


def registrar_auditoria(
    *, executor, acao: str, entidade, organizacao=None, anterior=None, novo=None,
    sucesso: bool = True, motivo: str = '', origem: str = 'PAINEL', request=None,
):
    return Auditoria.objects.create(
        usuario=executor if getattr(executor, 'is_authenticated', False) else None,
        acao=acao,
        entidade=entidade._meta.label if hasattr(entidade, '_meta') else str(entidade),
        registro_id=str(getattr(entidade, 'uuid', getattr(entidade, 'pk', ''))),
        organizacao_uuid=getattr(organizacao, 'uuid', None),
        dados_antes_json=anterior or {},
        dados_depois_json=novo or {},
        motivo=motivo,
        ip=request.META.get('REMOTE_ADDR') if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000] if request else '',
        sucesso=sucesso,
        origem=origem,
    )
