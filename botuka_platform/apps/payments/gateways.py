from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class GatewayUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class GatewayResult:
    reference: str
    status: str
    raw: dict
    payment_data: dict = field(default_factory=dict)


class PaymentGateway(ABC):
    code: str

    @abstractmethod
    def charge(self, *, payment_id: str, amount: Decimal, idempotency_key: str,
               external_reference: str = '', payment_method: str = 'pix', metadata=None) -> GatewayResult:
        raise NotImplementedError

    @abstractmethod
    def consult(self, *, reference: str) -> GatewayResult:
        raise NotImplementedError

    @abstractmethod
    def cancel(self, *, reference: str, idempotency_key: str) -> GatewayResult:
        raise NotImplementedError

    @abstractmethod
    def refund(self, *, reference: str, amount: Decimal, idempotency_key: str) -> GatewayResult:
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(self, payload: bytes, headers: dict[str, str]) -> bool:
        raise NotImplementedError

    def parse_webhook(self, payload: dict) -> tuple[str, str, str]:
        return (str(payload.get('event_id') or payload.get('id') or ''),
                str(payload.get('type') or ''),
                str(payload.get('reference') or payload.get('data', {}).get('id') or ''))


class GatewayFake(PaymentGateway):
    code = 'fake'

    def __init__(self, secret: str = 'local-only', *, code: str | None = None):
        self.secret = secret.encode()
        self.code = code or self.code

    def _reference(self, *parts) -> str:
        return hashlib.sha256(':'.join(map(str, parts)).encode()).hexdigest()[:32]

    def charge(self, *, payment_id, amount, idempotency_key, external_reference='', payment_method='pix', metadata=None):
        reference = self._reference(self.code, payment_id, idempotency_key)
        status = (metadata or {}).get('fake_status', 'confirmed')
        return GatewayResult(reference, status, {
            'amount': str(amount), 'external_reference': external_reference,
            'payment_method': payment_method,
        }, {'qr_code': f'FAKE-{reference}'} if payment_method == 'pix' else {})

    def consult(self, *, reference):
        return GatewayResult(reference, 'confirmed', {'id': reference})

    def cancel(self, *, reference, idempotency_key):
        return GatewayResult(reference, 'cancelled', {'id': reference})

    def refund(self, *, reference, amount, idempotency_key):
        refund_reference = self._reference(reference, idempotency_key)
        return GatewayResult(refund_reference, 'refunded', {'amount': str(amount)})

    def sign(self, payload: bytes) -> str:
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def verify_webhook(self, payload: bytes, headers) -> bool:
        return hmac.compare_digest(self.sign(payload), headers.get('x-botuka-signature', ''))


FakeGateway = GatewayFake


class GatewayMercadoPago(PaymentGateway):
    code = 'mercado_pago'
    base_url = 'https://api.mercadopago.com'

    def __init__(self, access_token=None, webhook_secret=None):
        self.access_token = access_token or settings.MERCADO_PAGO_ACCESS_TOKEN
        self.webhook_secret = webhook_secret or settings.MERCADO_PAGO_WEBHOOK_SECRET

    def _request(self, method, path, *, body=None, idempotency_key=''):
        if not self.access_token:
            raise GatewayUnavailable('Mercado Pago não configurado.')
        headers = {'Authorization': f'Bearer {self.access_token}', 'Content-Type': 'application/json'}
        if idempotency_key:
            headers['X-Idempotency-Key'] = idempotency_key
        request = Request(f'{self.base_url}{path}', method=method, headers=headers,
                          data=json.dumps(body).encode() if body is not None else None)
        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read())
        except (HTTPError, URLError, TimeoutError) as exc:
            raise GatewayUnavailable('Mercado Pago indisponível.') from exc

    def charge(self, *, payment_id, amount, idempotency_key, external_reference='', payment_method='pix', metadata=None):
        metadata = metadata or {}
        method_types = {'pix': 'bank_transfer', 'boleto': 'ticket', 'card': 'credit_card'}
        if payment_method not in method_types:
            raise ValueError('Meio de pagamento Mercado Pago não suportado.')
        method = {'id': payment_method, 'type': method_types[payment_method]}
        if payment_method == 'card':
            method.update(token=metadata.get('card_token', ''), installments=int(metadata.get('installments', 1)))
        body = {'type': 'online', 'total_amount': str(amount),
                'external_reference': external_reference or payment_id, 'processing_mode': 'automatic',
                'transactions': {'payments': [{'amount': str(amount), 'payment_method': method}]},
                'payer': {'email': metadata.get('payer_email', '')}}
        raw = self._request('POST', '/v1/orders', body=body, idempotency_key=idempotency_key)
        transaction = (raw.get('transactions', {}).get('payments') or [{}])[0]
        return GatewayResult(str(raw['id']), str(raw.get('status', 'processing')), raw, {
            key: transaction.get(key) for key in ('ticket_url', 'qr_code', 'qr_code_base64') if transaction.get(key)
        })

    def consult(self, *, reference):
        raw = self._request('GET', f'/v1/orders/{reference}')
        return GatewayResult(reference, str(raw.get('status', 'processing')), raw)

    def cancel(self, *, reference, idempotency_key):
        raw = self._request('POST', f'/v1/orders/{reference}/cancel', body={}, idempotency_key=idempotency_key)
        return GatewayResult(reference, str(raw.get('status', 'cancelled')), raw)

    def refund(self, *, reference, amount, idempotency_key):
        raw = self._request('POST', f'/v1/orders/{reference}/refund', body={}, idempotency_key=idempotency_key)
        return GatewayResult(str(raw.get('id', reference)), str(raw.get('status', 'refunded')), raw)

    def verify_webhook(self, payload: bytes, headers) -> bool:
        if not self.webhook_secret:
            return False
        signature = headers.get('x-signature', '')
        candidates = dict(part.split('=', 1) for part in signature.split(',') if '=' in part)
        try:
            data_id = str(json.loads(payload).get('data', {}).get('id', '')).lower()
        except (TypeError, ValueError):
            return False
        manifest = ''.join((
            f'id:{data_id};' if data_id else '',
            f"request-id:{headers.get('x-request-id')};" if headers.get('x-request-id') else '',
            f"ts:{candidates.get('ts')};" if candidates.get('ts') else '',
        ))
        digest = hmac.new(self.webhook_secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(candidates.get('v1', ''), digest)


class GatewayC6(PaymentGateway):
    code = 'c6'

    def _pending(self):
        raise GatewayUnavailable('Gateway C6 aguarda documentação técnica oficial e credenciais de homologação.')

    def charge(self, **kwargs): return self._pending()
    def consult(self, **kwargs): return self._pending()
    def cancel(self, **kwargs): return self._pending()
    def refund(self, **kwargs): return self._pending()
    def verify_webhook(self, payload: bytes, headers) -> bool: return False


def get_gateway(code: str = 'fake') -> PaymentGateway:
    if code not in {'fake', 'mercado_pago', 'c6'}:
        raise ValueError('Gateway não configurado.')
    if code == 'fake':
        return GatewayFake()
    if settings.PAYMENTS_USE_FAKE_GATEWAYS:
        return GatewayFake(code=code)
    return GatewayMercadoPago() if code == 'mercado_pago' else GatewayC6()
