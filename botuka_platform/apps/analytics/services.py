import hashlib
import uuid
from urllib.parse import urlparse

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.organizations.models import Empresa

from .events import ALLOWED_EVENTS, ALLOWED_METADATA
from .models import AnalyticsDailyCompany, AnalyticsDailyCompanyTerm, AnalyticsEvent

EVENT_METRIC = {
    'company_impression': 'impressions', 'view_company': 'views',
    'view_service': 'service_views', 'view_item': 'product_views',
    'whatsapp_click': 'whatsapp_clicks', 'phone_click': 'phone_clicks',
    'website_click': 'website_clicks', 'directions_click': 'directions_clicks',
    'generate_lead': 'leads', 'job_application_complete': 'leads',
}


def is_bot(user_agent):
    value = (user_agent or '').casefold()
    return any(token in value for token in ('bot', 'crawler', 'spider', 'slurp', 'headless', 'healthcheck'))


def resolve_company(object_type, object_id):
    if not object_id:
        return None
    try:
        object_id = uuid.UUID(str(object_id))
    except (ValueError, TypeError, AttributeError):
        return None
    if object_type == 'company':
        return Empresa.objects.filter(uuid=object_id, ativo=True, excluido_em__isnull=True).first()
    mappings = {
        'service': ('apps.services.models', 'Servico', 'empresa'),
        'product': ('apps.products.models', 'Produto', 'empresa_proprietaria'),
        'event': ('apps.events.models', 'Evento', 'empresa_promotora'),
        'job': ('apps.recruitment.models', 'Vaga', 'empresa'),
    }
    config = mappings.get(object_type)
    if not config:
        return None
    module, model_name, company_field = config
    module_obj = __import__(module, fromlist=[model_name])
    model = getattr(module_obj, model_name)
    obj = model.objects.filter(uuid=object_id).select_related(company_field).first()
    return getattr(obj, company_field, None) if obj else None


def register_event(request, payload):
    event_name = str(payload.get('event_name', ''))[:48]
    if event_name not in ALLOWED_EVENTS or is_bot(request.META.get('HTTP_USER_AGENT')):
        return None
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return None
    visitor_id = str(payload.get('visitor_id', ''))[:64]
    session_id = str(payload.get('session_id', ''))[:64]
    if len(visitor_id) < 16 or len(session_id) < 16:
        return None
    object_type = str(payload.get('object_type', ''))[:32]
    object_id = payload.get('object_id') or None
    if object_id:
        try:
            object_id = uuid.UUID(str(object_id))
        except (ValueError, TypeError, AttributeError):
            return None
    empresa = resolve_company(object_type, object_id)
    if empresa and request.user.is_authenticated and empresa.usuario_proprietario_id == request.user.id:
        return None
    metadata = {
        key: value for key, value in (payload.get('metadata') or {}).items()
        if key in ALLOWED_METADATA and isinstance(value, (str, int, float, bool))
    }
    attribution = payload.get('attribution') or {}
    path = str(payload.get('path') or request.path)[:300]
    raw_dedupe = str(payload.get('dedupe_key', ''))[:128]
    dedupe_key = hashlib.sha256(raw_dedupe.encode()).hexdigest() if raw_dedupe else ''
    if not dedupe_key:
        return None
    referrer_host = urlparse(str(payload.get('referrer', ''))).hostname or ''
    try:
        with transaction.atomic():
            event = AnalyticsEvent.objects.create(
                event_name=event_name, visitor_id=visitor_id, session_id=session_id,
                user=request.user if request.user.is_authenticated else None,
                empresa=empresa, object_type=object_type, object_id=object_id,
                source=str(attribution.get('source', ''))[:64],
                medium=str(attribution.get('medium', ''))[:64],
                campaign=str(attribution.get('campaign', ''))[:120],
                term=str(attribution.get('term', ''))[:120],
                content=str(attribution.get('content', ''))[:120],
                first_source=str(attribution.get('first_source', ''))[:64],
                first_medium=str(attribution.get('first_medium', ''))[:64],
                first_campaign=str(attribution.get('first_campaign', ''))[:120],
                gclid=str(attribution.get('gclid', ''))[:180],
                gbraid=str(attribution.get('gbraid', ''))[:180],
                wbraid=str(attribution.get('wbraid', ''))[:180],
                referrer_host=referrer_host[:180],
                landing_path=str(attribution.get('landing_path', ''))[:300],
                path=path, device_type=str(payload.get('device_type', ''))[:16],
                metadata=metadata, dedupe_key=dedupe_key,
            )
            if empresa:
                _aggregate(event)
            return event
    except IntegrityError:
        return None


def _aggregate(event):
    metric = EVENT_METRIC.get(event.event_name)
    term = str(event.metadata.get('search_term', '')).strip().casefold()[:120]
    if not metric and not (term and event.event_name == 'select_search_result'):
        return
    day = timezone.localdate(event.created_at)
    daily, _ = AnalyticsDailyCompany.objects.get_or_create(date=day, empresa=event.empresa)
    increments = {}
    if metric:
        increments[metric] = F(metric) + 1
    if not AnalyticsEvent.objects.filter(
        empresa=event.empresa,
        visitor_id=event.visitor_id,
        created_at__date=day,
    ).exclude(pk=event.pk).exists():
        increments['visitors'] = F('visitors') + 1
    if term and event.event_name in {'select_search_result', 'view_company'}:
        increments['search_views'] = F('search_views') + 1
    if increments:
        AnalyticsDailyCompany.objects.filter(pk=daily.pk).update(**increments)
    if term and event.event_name in {'company_impression', 'select_search_result', 'view_company'}:
        term_row, _ = AnalyticsDailyCompanyTerm.objects.get_or_create(
            date=day, empresa=event.empresa, term=term,
        )
        field = 'impressions' if event.event_name == 'company_impression' else 'selections'
        AnalyticsDailyCompanyTerm.objects.filter(pk=term_row.pk).update(**{field: F(field) + 1})
