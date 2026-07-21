import json
import re
from urllib.parse import unquote

from django.conf import settings

from .builders import build_seo


GTM_RE = re.compile(r'^GTM-[A-Z0-9]+$')
GA_RE = re.compile(r'^G-[A-Z0-9]+$')
PIXEL_RE = re.compile(r'^\d{5,30}$')
CLARITY_RE = re.compile(r'^[a-z0-9]{5,20}$')


def _consent(request):
    try:
        value = json.loads(unquote(request.COOKIES.get('botuka_consent', '{}')))
    except (TypeError, ValueError):
        value = {}
    return {
        'analytics': value.get('analytics') is True,
        'marketing': value.get('marketing') is True,
        'personalization': value.get('personalization') is True,
    }


def seo_context(request):
    private = request.path.startswith(('/admin/', '/painel/', '/gestao/', '/conta/', '/offline/'))
    default_seo = build_seo(
        request,
        title=settings.SITE_NAME,
        description=settings.SITE_DEFAULT_DESCRIPTION,
        robots='noindex,nofollow' if private else 'index,follow',
    )
    consent = _consent(request)
    integrations = {
        'gtm_id': settings.GOOGLE_TAG_MANAGER_ID if GTM_RE.fullmatch(settings.GOOGLE_TAG_MANAGER_ID) else '',
        'ga_id': settings.GOOGLE_ANALYTICS_ID if GA_RE.fullmatch(settings.GOOGLE_ANALYTICS_ID) else '',
        'meta_pixel_id': settings.META_PIXEL_ID if PIXEL_RE.fullmatch(settings.META_PIXEL_ID) else '',
        'clarity_id': settings.MICROSOFT_CLARITY_ID if CLARITY_RE.fullmatch(settings.MICROSOFT_CLARITY_ID) else '',
        'analytics_allowed': settings.ENABLE_ANALYTICS and consent['analytics'],
        'marketing_allowed': settings.ENABLE_MARKETING_TAGS and consent['marketing'],
    }
    public_config = {
        'google_site_verification': settings.GOOGLE_SITE_VERIFICATION,
        'bing_site_verification': settings.BING_SITE_VERIFICATION,
        'meta_domain_verification': settings.META_DOMAIN_VERIFICATION,
        'pinterest_domain_verification': settings.PINTEREST_DOMAIN_VERIFICATION,
        'twitter_site': settings.TWITTER_SITE,
    }
    return {
        'seo_default': default_seo,
        'tracking': integrations,
        'consent': consent,
        'seo_config': public_config,
    }
