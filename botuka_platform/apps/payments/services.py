from __future__ import annotations

from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .gateway_router import gateway_code_for
from .gateways import get_gateway
from .models import Cobranca, ChaveIdempotencia, ItemCobranca, Pagamento, Transacao, Webhook


@transaction.atomic
def criar_cobranca(*, empresa, usuario, itens, origem=Cobranca.Origem.COBRANCA_INSTITUCIONAL,
                   external_reference='', metadata=None, vencimento=None) -> Cobranca:
    external_reference = external_reference or f'charge:{uuid.uuid4()}'
    cobranca, created = Cobranca.objects.get_or_create(
        external_reference=external_reference,
        defaults={'empresa': empresa, 'criada_por': usuario, 'origem': origem,
                  'metadata': metadata or {}, 'vencimento': vencimento},
    )
    if not created:
        return cobranca
    for item in itens:
        ItemCobranca.objects.create(
            cobranca=cobranca, codigo=item['codigo'], descricao=item['descricao'],
            quantidade=int(item.get('quantidade', 1)), valor_unitario=Decimal(str(item['valor_unitario'])),
            metadata=item.get('metadata', {}), valor_total=Decimal('0.00'),
        )
    cobranca.refresh_from_db()
    if cobranca.valor_total <= 0:
        raise ValidationError('A cobrança deve possuir valor positivo.')
    return cobranca


@transaction.atomic
def processar_pagamento(*, cobranca_id, idempotency_key: str, gateway_code=None,
                        payment_method='pix', metadata=None) -> Pagamento:
    if not idempotency_key or len(idempotency_key) > 128:
        raise ValidationError('Chave de idempotência inválida.')
    chave, created = ChaveIdempotencia.objects.select_for_update().get_or_create(chave=idempotency_key, defaults={'operacao': 'PAGAMENTO'})
    if not created:
        if chave.operacao != 'PAGAMENTO':
            raise ValidationError('Chave de idempotência já usada em outra operação.')
        if chave.pagamento_id:
            return chave.pagamento
        raise ValidationError('Operação idempotente ainda em processamento.')
    cobranca = Cobranca.objects.select_for_update().get(pk=cobranca_id)
    routed_gateway = gateway_code_for(cobranca.origem)
    if gateway_code is not None and gateway_code != routed_gateway and gateway_code != 'fake':
        raise ValidationError('Gateway incompatível com a origem da cobrança.')
    gateway_code = gateway_code or routed_gateway
    if cobranca.status != Cobranca.Status.PENDENTE:
        raise ValidationError('Somente cobranças pendentes podem ser pagas.')
    if cobranca.vencimento and cobranca.vencimento < timezone.now():
        raise ValidationError('Cobrança vencida.')
    pagamento = Pagamento.objects.create(
        cobranca=cobranca, gateway=gateway_code, status=Pagamento.Status.PROCESSANDO,
        valor=cobranca.valor_total, external_reference=cobranca.external_reference,
        idempotency_key=idempotency_key, metadata=metadata or {},
    )
    gateway = get_gateway(gateway_code)
    result = gateway.charge(
        payment_id=str(pagamento.uuid), amount=cobranca.valor_total,
        idempotency_key=idempotency_key, external_reference=cobranca.external_reference,
        payment_method=payment_method, metadata=metadata or {},
    )
    pagamento.referencia_gateway = result.reference
    pagamento.gateway_status = result.status
    pagamento.metadata = {**pagamento.metadata, 'gateway_response': result.payment_data}
    if result.status in {'confirmed', 'approved', 'processed'}:
        pagamento.status = Pagamento.Status.CONFIRMADO
        pagamento.confirmado_em = timezone.now()
    elif result.status in {'failed', 'rejected', 'cancelled', 'canceled'}:
        pagamento.status = Pagamento.Status.FALHOU
    pagamento.full_clean()
    pagamento.save(update_fields=['referencia_gateway', 'gateway_status', 'metadata', 'status', 'confirmado_em', 'atualizado_em'])
    Transacao.objects.create(
        pagamento=pagamento, tipo=Transacao.Tipo.CAPTURA, valor=pagamento.valor,
        idempotency_key=idempotency_key, referencia_gateway=result.reference,
        payload=result.raw, sucesso=pagamento.status != Pagamento.Status.FALHOU,
    )
    if pagamento.status == Pagamento.Status.CONFIRMADO:
        cobranca.status = Cobranca.Status.PAGA
        cobranca.paga_em = pagamento.confirmado_em
        cobranca.full_clean()
        cobranca.save(update_fields=['status', 'paga_em', 'atualizado_em'])
    chave.pagamento = pagamento
    chave.save(update_fields=['pagamento'])
    return pagamento


@transaction.atomic
def cancelar_cobranca(*, cobranca_id) -> Cobranca:
    cobranca = Cobranca.objects.select_for_update().get(pk=cobranca_id)
    if cobranca.status != Cobranca.Status.PENDENTE:
        raise ValidationError('Somente cobranças pendentes podem ser canceladas.')
    pagamento = cobranca.pagamentos.exclude(referencia_gateway='').order_by('-criado_em').first()
    if pagamento:
        idempotency_key = f'cancel:{cobranca.uuid}'
        result = get_gateway(pagamento.gateway).cancel(
            reference=pagamento.referencia_gateway, idempotency_key=idempotency_key,
        )
        Transacao.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={'pagamento': pagamento, 'tipo': Transacao.Tipo.CANCELAMENTO,
                      'valor': pagamento.valor, 'referencia_gateway': result.reference,
                      'payload': result.raw, 'sucesso': True},
        )
        pagamento.status = Pagamento.Status.CANCELADO
        pagamento.gateway_status = result.status
        pagamento.save(update_fields=['status', 'gateway_status', 'atualizado_em'])
    cobranca.status = Cobranca.Status.CANCELADA
    cobranca.cancelada_em = timezone.now()
    cobranca.full_clean()
    cobranca.save(update_fields=['status', 'cancelada_em', 'atualizado_em'])
    return cobranca


@transaction.atomic
def estornar_pagamento(*, pagamento_id, idempotency_key: str) -> Pagamento:
    if not idempotency_key or len(idempotency_key) > 128:
        raise ValidationError('Chave de idempotência inválida.')
    chave, created = ChaveIdempotencia.objects.select_for_update().get_or_create(chave=idempotency_key, defaults={'operacao': 'ESTORNO'})
    if not created:
        if chave.operacao != 'ESTORNO' or not chave.pagamento_id:
            raise ValidationError('Chave de idempotência já usada ou em processamento.')
        return chave.pagamento
    pagamento = Pagamento.objects.select_for_update().select_related('cobranca').get(pk=pagamento_id)
    if pagamento.status != Pagamento.Status.CONFIRMADO:
        raise ValidationError('Somente pagamentos confirmados podem ser estornados.')
    result = get_gateway(pagamento.gateway).refund(reference=pagamento.referencia_gateway, amount=pagamento.valor, idempotency_key=idempotency_key)
    Transacao.objects.create(pagamento=pagamento, tipo=Transacao.Tipo.ESTORNO, valor=pagamento.valor, idempotency_key=idempotency_key, referencia_gateway=result.reference, payload=result.raw, sucesso=True)
    pagamento.status = Pagamento.Status.ESTORNADO
    pagamento.save(update_fields=['status', 'atualizado_em'])
    pagamento.cobranca.status = Cobranca.Status.ESTORNADA
    pagamento.cobranca.estornada_em = timezone.now()
    pagamento.cobranca.full_clean()
    pagamento.cobranca.save(update_fields=['status', 'estornada_em', 'atualizado_em'])
    chave.pagamento = pagamento
    chave.save(update_fields=['pagamento'])
    return pagamento


@transaction.atomic
def registrar_webhook(*, gateway_code, event_id, event_type, payload, raw_body: bytes,
                      headers=None, signature='') -> tuple[Webhook, bool]:
    gateway = get_gateway(gateway_code)
    normalized_headers = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
    if signature:
        normalized_headers.setdefault('x-botuka-signature', signature)
    valid = gateway.verify_webhook(raw_body, normalized_headers)
    webhook, created = Webhook.objects.get_or_create(
        gateway=gateway_code, event_id=event_id,
        defaults={'tipo': event_type, 'payload': payload, 'headers': normalized_headers,
                  'assinatura_valida': valid},
    )
    if not created:
        return webhook, False
    if not valid:
        webhook.erro = 'Assinatura inválida.'
        webhook.save(update_fields=['erro'])
        return webhook, True
    reference = gateway.parse_webhook(payload)[2]
    if reference:
        pagamento = Pagamento.objects.select_for_update().filter(
            gateway=gateway_code, referencia_gateway=reference,
        ).select_related('cobranca').first()
        if pagamento:
            gateway_status = str(payload.get('status', '')).lower()
            pagamento.gateway_status = gateway_status
            if gateway_status in {'confirmed', 'approved', 'processed'}:
                pagamento.status = Pagamento.Status.CONFIRMADO
                pagamento.confirmado_em = pagamento.confirmado_em or timezone.now()
                pagamento.cobranca.status = Cobranca.Status.PAGA
                pagamento.cobranca.paga_em = pagamento.confirmado_em
                pagamento.cobranca.save(update_fields=['status', 'paga_em', 'atualizado_em'])
            elif gateway_status in {'failed', 'rejected'}:
                pagamento.status = Pagamento.Status.FALHOU
            elif gateway_status in {'refunded', 'charged_back'}:
                pagamento.status = Pagamento.Status.ESTORNADO
                pagamento.cobranca.status = Cobranca.Status.ESTORNADA
                pagamento.cobranca.estornada_em = timezone.now()
                pagamento.cobranca.save(update_fields=['status', 'estornada_em', 'atualizado_em'])
            pagamento.save(update_fields=['gateway_status', 'status', 'confirmado_em', 'atualizado_em'])
    webhook.processado_em = timezone.now()
    webhook.save(update_fields=['processado_em'])
    return webhook, True
