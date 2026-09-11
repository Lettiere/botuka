from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.organizations.models import EmpresaImportacaoExecucao
from apps.organizations.services.botucatu_discovery import (
    MAXIMO_REGISTROS_POR_PAGINA,
    discover_batch,
)


FONTE = 'MINHA_RECEITA'


class SincronizacaoEmAndamento(RuntimeError):
    pass


def _adquirir_execucao(tipo_execucao, retomar_id=None):
    agora = timezone.now()
    limite = agora - timedelta(seconds=int(getattr(
        settings, 'EMPRESA_IMPORTACAO_LOCK_TIMEOUT', 7200,
    )))
    with transaction.atomic():
        ativa = EmpresaImportacaoExecucao.objects.select_for_update().filter(
            fonte=FONTE, status=EmpresaImportacaoExecucao.Status.EXECUTANDO,
        ).first()
        if ativa:
            if ativa.atualizado_em >= limite:
                raise SincronizacaoEmAndamento(
                    f'A sincronização #{ativa.pk} já está em execução.'
                )
            # Heartbeat vencido: retoma a mesma execução e seu checkpoint.
            ativa.ultima_mensagem = 'Execução retomada apó expiração do lock.'
            ativa.save(update_fields=('ultima_mensagem', 'atualizado_em'))
            return ativa

        if retomar_id is not None:
            execucao = EmpresaImportacaoExecucao.objects.select_for_update().get(
                pk=retomar_id, fonte=FONTE,
            )
            if execucao.status not in {
                EmpresaImportacaoExecucao.Status.ERRO,
                EmpresaImportacaoExecucao.Status.PENDENTE,
            }:
                raise ValueError('Somente execuções pendentes ou com erro podem ser retomadas.')
        else:
            execucao = EmpresaImportacaoExecucao(
                fonte=FONTE, tipo_execucao=tipo_execucao, cursor_atual='',
            )
        execucao.status = EmpresaImportacaoExecucao.Status.EXECUTANDO
        execucao.iniciada_em = execucao.iniciada_em or agora
        execucao.finalizada_em = None
        execucao.ultima_mensagem = 'Sincronização iniciada.'
        try:
            execucao.save()
        except IntegrityError as exc:
            raise SincronizacaoEmAndamento('Outra sincronização adquiriu o lock.') from exc
        return execucao


def sincronizar_empresas(*, tipo_execucao, retomar_id=None, client=None):
    """Percorre a fonte inteira; o cursor salvo sempre aponta para a próxima página."""
    execucao = _adquirir_execucao(tipo_execucao, retomar_id=retomar_id)
    cursor = execucao.cursor_atual or None
    cursores_processados = set()

    try:
        while True:
            if cursor is not None:
                if cursor in cursores_processados:
                    raise RuntimeError(
                        f'Cursor repetido retornado pela fonte: {cursor[:200]}'
                    )
                cursores_processados.add(cursor)
            pagina = discover_batch(
                limit=MAXIMO_REGISTROS_POR_PAGINA,
                cursor=cursor,
                dry_run=False,
                client=client,
                enriquecer=True,
            )
            erros_pagina = sum(item.resultado == 'ERRO' for item in pagina.itens)
            # Checkpoint somente depois de toda a página (inclusive imports isolados).
            execucao.paginas_processadas += 1
            execucao.registros_recebidos += pagina.recebidas
            execucao.registros_validos += pagina.ativas_validas
            execucao.importados += pagina.importadas
            execucao.ja_existentes += pagina.ja_existentes
            execucao.rejeitados += pagina.rejeitadas
            execucao.erros += erros_pagina
            cursor = pagina.proximo_cursor or None
            execucao.cursor_atual = cursor or ''
            execucao.ultima_mensagem = f'Página {execucao.paginas_processadas} processada.'
            execucao.save(update_fields=(
                'cursor_atual', 'paginas_processadas', 'registros_recebidos',
                'registros_validos', 'importados', 'ja_existentes', 'rejeitados',
                'erros', 'ultima_mensagem', 'atualizado_em',
            ))
            if cursor is None:
                break
        execucao.status = EmpresaImportacaoExecucao.Status.CONCLUIDA
        execucao.finalizada_em = timezone.now()
        execucao.ultima_mensagem = 'Fonte elegível percorrida integralmente.'
        execucao.save(update_fields=('status', 'finalizada_em', 'ultima_mensagem', 'atualizado_em'))
        return execucao
    except Exception as exc:
        execucao.status = EmpresaImportacaoExecucao.Status.ERRO
        execucao.finalizada_em = timezone.now()
        execucao.ultima_mensagem = str(exc)[:2000]
        execucao.save(update_fields=('status', 'finalizada_em', 'ultima_mensagem', 'atualizado_em'))
        raise
