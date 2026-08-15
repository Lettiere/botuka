import json

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.core.seo.context import _consent

from .services import register_event
from .dashboard import dashboard_data, resolve_period
from apps.organizations.permissions import empresas_disponiveis_para_usuario


@require_POST
def collect(request):
    if not _consent(request).get('analytics'):
        return JsonResponse({'accepted': False}, status=202)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'invalid_payload'}, status=400)
    event = register_event(request, payload)
    return JsonResponse({'accepted': bool(event)}, status=202)


@login_required
def company_dashboard(request, uuid):
    empresa = empresas_disponiveis_para_usuario(request.user).filter(
        uuid=uuid, excluido_em__isnull=True,
    ).first()
    if not empresa:
        raise PermissionDenied
    period, start, end, previous_start, previous_end = resolve_period(request.GET)
    context = dashboard_data(empresa, start, end, previous_start, previous_end)
    context.update({
        'empresa': empresa, 'period': period, 'start': start, 'end': end,
        'previous_start': previous_start, 'previous_end': previous_end,
    })
    return render(request, 'painel/analytics/company_dashboard.html', context)
