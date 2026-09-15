import json
import hashlib
import hmac
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.organizations.models import Empresa

from .gateway_router import gateway_code_for
from .gateways import FakeGateway, GatewayC6, GatewayMercadoPago, GatewayUnavailable, get_gateway
from .models import Cobranca, Pagamento, Transacao, Webhook
from .permissions import pode_gerenciar_financeiro
from .services import cancelar_cobranca, criar_cobranca, estornar_pagamento, processar_pagamento


class PaymentsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('pay-owner', password='x')
        cls.other = get_user_model().objects.create_user('pay-other', password='x')
        cls.empresa = Empresa.objects.create(nome_fantasia='Pagadora', usuario_proprietario=cls.owner)

    def nova_cobranca(self, valor='10.25'):
        return criar_cobranca(empresa=self.empresa, usuario=self.owner, itens=[
            {'codigo': 'ITEM', 'descricao': 'Item', 'quantidade': 2, 'valor_unitario': valor},
        ])

    def test_total_e_calculado_no_backend_com_decimal(self):
        cobranca = self.nova_cobranca()
        self.assertEqual(cobranca.valor_total, Decimal('20.50'))
        self.assertIsInstance(cobranca.valor_total, Decimal)

    def test_pagamento_idempotente_nao_duplica_transacao(self):
        cobranca = self.nova_cobranca()
        primeiro = processar_pagamento(cobranca_id=cobranca.pk, idempotency_key='charge-1')
        segundo = processar_pagamento(cobranca_id=cobranca.pk, idempotency_key='charge-1')
        self.assertEqual(primeiro.pk, segundo.pk)
        self.assertEqual(Transacao.objects.filter(pagamento=primeiro).count(), 1)
        cobranca.refresh_from_db()
        self.assertEqual(cobranca.status, Cobranca.Status.PAGA)

    def test_valor_adulterado_e_rejeitado(self):
        cobranca = self.nova_cobranca()
        pagamento = Pagamento(cobranca=cobranca, gateway='fake', valor=Decimal('0.01'))
        with self.assertRaises(ValidationError):
            pagamento.full_clean()

    def test_cobranca_cancelada_nao_pode_ser_paga(self):
        cobranca = cancelar_cobranca(cobranca_id=self.nova_cobranca().pk)
        with self.assertRaises(ValidationError):
            processar_pagamento(cobranca_id=cobranca.pk, idempotency_key='cancelada')

    def test_estorno_e_idempotente(self):
        pagamento = processar_pagamento(cobranca_id=self.nova_cobranca().pk, idempotency_key='charge-refund')
        primeiro = estornar_pagamento(pagamento_id=pagamento.pk, idempotency_key='refund-1')
        segundo = estornar_pagamento(pagamento_id=pagamento.pk, idempotency_key='refund-1')
        self.assertEqual(primeiro.pk, segundo.pk)
        self.assertEqual(Transacao.objects.filter(pagamento=pagamento, tipo=Transacao.Tipo.ESTORNO).count(), 1)

    def test_escopo_financeiro_por_empresa(self):
        self.assertTrue(pode_gerenciar_financeiro(self.owner, self.empresa))
        self.assertFalse(pode_gerenciar_financeiro(self.other, self.empresa))

    def test_webhook_assinado_e_idempotente(self):
        payload = json.dumps({'event_id': 'evt-1', 'type': 'payment.test'}).encode()
        signature = FakeGateway().sign(payload)
        url = reverse('payments:webhook', args=['fake'])
        first = self.client.post(url, data=payload, content_type='application/json', HTTP_X_BOTUKA_SIGNATURE=signature)
        second = self.client.post(url, data=payload, content_type='application/json', HTTP_X_BOTUKA_SIGNATURE=signature)
        self.assertEqual(first.status_code, 200)
        self.assertFalse(second.json()['created'])
        self.assertEqual(Webhook.objects.count(), 1)

    def test_webhook_com_assinatura_invalida(self):
        payload = json.dumps({'event_id': 'evt-bad', 'type': 'payment.test'}).encode()
        response = self.client.post(reverse('payments:webhook', args=['fake']), data=payload, content_type='application/json', HTTP_X_BOTUKA_SIGNATURE='bad')
        self.assertEqual(response.status_code, 401)


class MultiGatewayTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('router-owner', password='x')
        cls.empresa = Empresa.objects.create(nome_fantasia='Router', usuario_proprietario=cls.user)

    def charge(self, origem, key, **kwargs):
        cobranca = criar_cobranca(
            empresa=self.empresa, usuario=self.user, origem=origem,
            external_reference=f'{origem.lower()}:{key}',
            itens=[{'codigo': key, 'descricao': key, 'valor_unitario': '10.00'}],
        )
        return processar_pagamento(cobranca_id=cobranca.pk, idempotency_key=key, **kwargs)

    def test_router_c6(self):
        for origem in (Cobranca.Origem.PUBLICIDADE, Cobranca.Origem.MENSALIDADE,
                       Cobranca.Origem.PLANO, Cobranca.Origem.ASSINATURA,
                       Cobranca.Origem.COBRANCA_INSTITUCIONAL):
            self.assertEqual(gateway_code_for(origem), 'c6')

    def test_router_mercado_pago(self):
        for origem in (Cobranca.Origem.PRODUTO, Cobranca.Origem.SERVICO,
                       Cobranca.Origem.PRESTACAO_SERVICO):
            self.assertEqual(gateway_code_for(origem), 'mercado_pago')

    def test_gateway_desconhecido(self):
        with self.assertRaises(ValueError):
            gateway_code_for('DESCONHECIDO')
        with self.assertRaises(ValueError):
            get_gateway('desconhecido')

    @override_settings(PAYMENTS_USE_FAKE_GATEWAYS=False)
    def test_c6_indisponivel_sem_documentacao_nao_inventa_chamada(self):
        with self.assertRaises(GatewayUnavailable):
            self.charge(Cobranca.Origem.PUBLICIDADE, 'c6-unavailable')
        self.assertIsInstance(get_gateway('c6'), GatewayC6)

    def test_referencia_externa_idempotencia_e_confirmacao(self):
        first = self.charge(Cobranca.Origem.PRODUTO, 'product-confirmed')
        second = processar_pagamento(cobranca_id=first.cobranca_id,
                                     idempotency_key='product-confirmed')
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.gateway, 'mercado_pago')
        self.assertEqual(first.external_reference, 'produto:product-confirmed')
        self.assertEqual(first.status, Pagamento.Status.CONFIRMADO)

    def test_pagamento_recusado_e_cancelamento_idempotente(self):
        payment = self.charge(Cobranca.Origem.SERVICO, 'service-rejected',
                              metadata={'fake_status': 'rejected'})
        self.assertEqual(payment.status, Pagamento.Status.FALHOU)
        charge = cancelar_cobranca(cobranca_id=payment.cobranca_id)
        self.assertEqual(charge.status, Cobranca.Status.CANCELADA)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Pagamento.Status.CANCELADO)

    def test_webhook_c6_duplicado_nao_duplica_efeito(self):
        payment = self.charge(Cobranca.Origem.PUBLICIDADE, 'c6-webhook',
                              metadata={'fake_status': 'processing'})
        payload = json.dumps({'event_id': 'c6-evt-1', 'type': 'charge.updated',
                              'reference': payment.referencia_gateway,
                              'status': 'confirmed'}).encode()
        signature = FakeGateway(code='c6').sign(payload)
        url = reverse('payments_api:c6_webhook')
        responses = [self.client.post(url, data=payload, content_type='application/json',
                                      HTTP_X_BOTUKA_SIGNATURE=signature) for _ in range(2)]
        self.assertEqual([response.status_code for response in responses], [200, 200])
        self.assertFalse(responses[1].json()['created'])
        self.assertEqual(Webhook.objects.filter(gateway='c6').count(), 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Pagamento.Status.CONFIRMADO)

    def test_advertising_produtos_e_servicos_nao_importam_adapters(self):
        base = Path(__file__).resolve().parents[1]
        for package in ('advertising', 'products', 'services'):
            for source in (base / package).rglob('*.py'):
                text = source.read_text(encoding='utf-8')
                self.assertNotIn('GatewayC6', text, source)
                self.assertNotIn('GatewayMercadoPago', text, source)

    def test_adapter_mercado_pago_orders_pix_cartao_boleto_consulta_cancelamento_reembolso(self):
        gateway = GatewayMercadoPago(access_token='test-token', webhook_secret='test-secret')
        responses = [
            {'id': 'order-1', 'status': 'action_required', 'transactions': {'payments': [{'qr_code': 'pix'}]}},
            {'id': 'order-1', 'status': 'processed'}, {'id': 'order-1', 'status': 'cancelled'},
            {'id': 'refund-1', 'status': 'refunded'},
        ]
        with patch.object(gateway, '_request', side_effect=responses) as request:
            result = gateway.charge(payment_id='p1', amount=Decimal('10'), idempotency_key='mp-1',
                                    external_reference='produto:1', payment_method='pix',
                                    metadata={'payer_email': 'buyer@example.com'})
            gateway.consult(reference=result.reference)
            gateway.cancel(reference=result.reference, idempotency_key='mp-cancel')
            gateway.refund(reference=result.reference, amount=Decimal('10'), idempotency_key='mp-refund')
        self.assertEqual(result.payment_data['qr_code'], 'pix')
        self.assertEqual(request.call_args_list[0].args[:2], ('POST', '/v1/orders'))
        self.assertEqual(request.call_args_list[1].args[:2], ('GET', '/v1/orders/order-1'))

        webhook_payload = json.dumps({'id': 10, 'type': 'order', 'data': {'id': 'ORDER-1'}}).encode()
        manifest = 'id:order-1;request-id:req-1;ts:123;'
        digest = hmac.new(b'test-secret', manifest.encode(), hashlib.sha256).hexdigest()
        self.assertTrue(gateway.verify_webhook(webhook_payload, {
            'x-request-id': 'req-1', 'x-signature': f'ts=123,v1={digest}',
        }))
