import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .gateways import get_gateway
from .services import registrar_webhook


@require_POST
def webhook(request, gateway_code):
    try:
        gateway = get_gateway(gateway_code)
    except ValueError:
        return JsonResponse({'error': 'Gateway inválido.'}, status=404)
    try:
        payload = json.loads(request.body)
        event_id, event_type, _reference = gateway.parse_webhook(payload)
        event_id = event_id[:128]
        event_type = event_type[:64]
        if not event_id or not event_type:
            raise KeyError
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'error': 'Payload inválido.'}, status=400)
    try:
        row, created = registrar_webhook(
            gateway_code=gateway_code, event_id=event_id, event_type=event_type,
            payload=payload, raw_body=request.body,
            headers={name: request.headers.get(name, '') for name in (
                'X-Botuka-Signature', 'X-Signature', 'X-Request-Id', 'Content-Type',
            )},
        )
    except ValueError:
        return JsonResponse({'error': 'Gateway inválido.'}, status=404)
    if not row.assinatura_valida:
        return JsonResponse({'error': 'Assinatura inválida.'}, status=401)
    return JsonResponse({'ok': True, 'created': created})


def mercado_pago_webhook(request):
    return webhook(request, 'mercado_pago')


def c6_webhook(request):
    return webhook(request, 'c6')
