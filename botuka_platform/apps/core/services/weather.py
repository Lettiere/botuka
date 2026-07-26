"""Clima atual com cache e falha segura."""
import json
import logging
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)
CACHE_KEY = 'weather:botucatu:current'
LAST_VALID_KEY = 'weather:botucatu:last-valid'


def _fetch():
    if not settings.WEATHER_API_URL:
        return None
    query = urlencode({
        'latitude': settings.WEATHER_LATITUDE,
        'longitude': settings.WEATHER_LONGITUDE,
        'current': 'temperature_2m,weather_code',
        'timezone': 'America/Sao_Paulo',
        **({'apikey': settings.WEATHER_API_KEY} if settings.WEATHER_API_KEY else {}),
    })
    separator = '&' if '?' in settings.WEATHER_API_URL else '?'
    with urlopen(f'{settings.WEATHER_API_URL}{separator}{query}', timeout=1.2) as response:
        payload = json.load(response)
    current = payload.get('current', payload)
    value = current.get('temperature_2m', current.get('temperature'))
    if value is None:
        return None
    return {
        'disponivel': True, 'cidade': settings.WEATHER_CITY,
        'temperatura': round(float(value)), 'condicao': current.get('condition', ''),
        'icone': 'partly-cloudy', 'atualizado_em': timezone.now(),
        'desatualizado': False,
    }


def clima_atual():
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached
    try:
        result = _fetch()
    except Exception:
        logger.warning('Serviço meteorológico indisponível.', exc_info=True)
        result = None
    if result:
        cache.set(CACHE_KEY, result, settings.WEATHER_CACHE_SECONDS)
        cache.set(LAST_VALID_KEY, result, 86400)
        return result
    fallback = cache.get(LAST_VALID_KEY)
    if fallback:
        return {**fallback, 'desatualizado': True}
    unavailable = {'disponivel': False, 'cidade': settings.WEATHER_CITY}
    cache.set(CACHE_KEY, unavailable, min(settings.WEATHER_CACHE_SECONDS, 300))
    return unavailable
