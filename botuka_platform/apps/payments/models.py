from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def default_external_reference():
    return f'charge:{uuid.uuid4()}'


def default_idempotency_key():
    return f'legacy:{uuid.uuid4()}'


class Cobranca(models.Model):
    class Origem(models.TextChoices):
        PUBLICIDADE = 'PUBLICIDADE', 'Publicidade'
        MENSALIDADE = 'MENSALIDADE', 'Mensalidade'
        PLANO = 'PLANO', 'Plano'
        ASSINATURA = 'ASSINATURA', 'Assinatura'
        COBRANCA_INSTITUCIONAL = 'COBRANCA_INSTITUCIONAL', 'Cobrança institucional'
        PRODUTO = 'PRODUTO', 'Produto'
        SERVICO = 'SERVICO', 'Serviço'
        PRESTACAO_SERVICO = 'PRESTACAO_SERVICO', 'Prestação de serviço'
    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        PAGA = 'PAGA', 'Paga'
        CANCELADA = 'CANCELADA', 'Cancelada'
        ESTORNADA = 'ESTORNADA', 'Estornada'

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    empresa = models.ForeignKey('organizations.Empresa', on_delete=models.PROTECT, related_name='cobrancas')
    criada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='cobrancas_criadas')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDENTE)
    origem = models.CharField(
        max_length=32, choices=Origem.choices, default=Origem.COBRANCA_INSTITUCIONAL,
    )
    external_reference = models.CharField(max_length=128, unique=True, default=default_external_reference)
    metadata = models.JSONField(default=dict, blank=True)
    moeda = models.CharField(max_length=3, default='BRL', editable=False)
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), editable=False)
    vencimento = models.DateTimeField(null=True, blank=True)
    paga_em = models.DateTimeField(null=True, blank=True, editable=False)
    cancelada_em = models.DateTimeField(null=True, blank=True, editable=False)
    estornada_em = models.DateTimeField(null=True, blank=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"payments"."payments_cobranca_tb"'
        indexes = [models.Index(fields=['empresa', 'status'], name='pay_cobranca_emp_status_idx')]
        constraints = [models.CheckConstraint(condition=models.Q(valor_total__gte=0), name='pay_cobranca_total_nn_ck')]

    def clean(self):
        if self.moeda != 'BRL':
            raise ValidationError({'moeda': 'Somente BRL é aceito.'})
        timestamps = {
            self.Status.PAGA: self.paga_em,
            self.Status.CANCELADA: self.cancelada_em,
            self.Status.ESTORNADA: self.estornada_em,
        }
        if self.status in timestamps and not timestamps[self.status]:
            raise ValidationError({'status': 'O status exige seu registro temporal de auditoria.'})

    def recalcular_total(self):
        total = self.itens.aggregate(total=models.Sum('valor_total'))['total'] or Decimal('0.00')
        self.valor_total = total.quantize(Decimal('0.01'))
        self.save(update_fields=['valor_total', 'atualizado_em'])
        return self.valor_total

    def __str__(self):
        return f'Cobrança {self.uuid} - {self.valor_total}'


class ItemCobranca(models.Model):
    cobranca = models.ForeignKey(Cobranca, on_delete=models.CASCADE, related_name='itens')
    codigo = models.CharField(max_length=64)
    descricao = models.CharField(max_length=255)
    quantidade = models.PositiveIntegerField(default=1)
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = '"payments"."payments_item_cobranca_tb"'
        constraints = [
            models.UniqueConstraint(fields=['cobranca', 'codigo'], name='pay_item_cobranca_codigo_uk'),
            models.CheckConstraint(condition=models.Q(quantidade__gte=1), name='pay_item_quantidade_ck'),
            models.CheckConstraint(condition=models.Q(valor_unitario__gte=0), name='pay_item_valor_ck'),
        ]

    def clean(self):
        if self.cobranca_id and self.cobranca.status != Cobranca.Status.PENDENTE:
            raise ValidationError('Itens só podem ser alterados em cobranças pendentes.')
        self.valor_total = (Decimal(self.valor_unitario) * self.quantidade).quantize(Decimal('0.01'))

    def save(self, *args, **kwargs):
        self.full_clean()
        result = super().save(*args, **kwargs)
        self.cobranca.recalcular_total()
        return result


class Pagamento(models.Model):
    class Status(models.TextChoices):
        CRIADO = 'CRIADO', 'Criado'
        PROCESSANDO = 'PROCESSANDO', 'Processando'
        CONFIRMADO = 'CONFIRMADO', 'Confirmado'
        FALHOU = 'FALHOU', 'Falhou'
        CANCELADO = 'CANCELADO', 'Cancelado'
        ESTORNADO = 'ESTORNADO', 'Estornado'

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    cobranca = models.ForeignKey(Cobranca, on_delete=models.PROTECT, related_name='pagamentos')
    gateway = models.CharField(max_length=32)
    gateway_status = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CRIADO)
    valor = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    referencia_gateway = models.CharField(max_length=128, blank=True)
    external_reference = models.CharField(max_length=128, default=default_external_reference)
    idempotency_key = models.CharField(max_length=128, unique=True, default=default_idempotency_key)
    metadata = models.JSONField(default=dict, blank=True)
    confirmado_em = models.DateTimeField(null=True, blank=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"payments"."payments_pagamento_tb"'
        constraints = [
            models.UniqueConstraint(fields=['gateway', 'referencia_gateway'], condition=~models.Q(referencia_gateway=''), name='pay_gateway_referencia_uk'),
            models.CheckConstraint(condition=models.Q(valor__gt=0), name='pay_pagamento_valor_ck'),
        ]

    def clean(self):
        if self.cobranca_id and self.valor != self.cobranca.valor_total:
            raise ValidationError({'valor': 'O valor deve ser calculado a partir da cobrança.'})


class ChaveIdempotencia(models.Model):
    chave = models.CharField(max_length=128, unique=True)
    operacao = models.CharField(max_length=32)
    pagamento = models.ForeignKey(Pagamento, null=True, blank=True, on_delete=models.PROTECT, related_name='chaves_idempotencia')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"payments"."payments_idempotencia_tb"'


class Transacao(models.Model):
    class Tipo(models.TextChoices):
        AUTORIZACAO = 'AUTORIZACAO', 'Autorização'
        CAPTURA = 'CAPTURA', 'Captura'
        CANCELAMENTO = 'CANCELAMENTO', 'Cancelamento'
        ESTORNO = 'ESTORNO', 'Estorno'

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    pagamento = models.ForeignKey(Pagamento, on_delete=models.PROTECT, related_name='transacoes')
    tipo = models.CharField(max_length=16, choices=Tipo.choices)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    idempotency_key = models.CharField(max_length=128, unique=True)
    referencia_gateway = models.CharField(max_length=128, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    sucesso = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"payments"."payments_transacao_tb"'
        constraints = [models.CheckConstraint(condition=models.Q(valor__gt=0), name='pay_transacao_valor_ck')]


class Webhook(models.Model):
    gateway = models.CharField(max_length=32)
    event_id = models.CharField(max_length=128)
    tipo = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    headers = models.JSONField(default=dict, blank=True)
    assinatura_valida = models.BooleanField(default=False)
    processado_em = models.DateTimeField(null=True, blank=True)
    erro = models.TextField(blank=True)
    recebido_em = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = '"payments"."payments_webhook_tb"'
        constraints = [models.UniqueConstraint(fields=['gateway', 'event_id'], name='pay_webhook_event_uk')]
