import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from django.conf import settings
from django.utils.html import strip_tags


SPACE_RE = re.compile(r'\s+')


def clean_text(value, limit=None):
    text = SPACE_RE.sub(' ', strip_tags(str(value or ''))).strip()
    if not limit or len(text) <= limit:
        return text
    shortened = text[: limit + 1].rsplit(' ', 1)[0].rstrip(' ,.;:-')
    return f'{shortened}…' if shortened else text[:limit]


def safe_absolute_url(request, value='', *, fallback_path='/'):
    raw = str(value or fallback_path).strip()
    parsed = urlsplit(raw)
    if parsed.scheme and parsed.scheme not in {'http', 'https'}:
        raw = fallback_path
        parsed = urlsplit(raw)
    if parsed.scheme in {'http', 'https'}:
        absolute = raw
    else:
        base = settings.SITE_URL.rstrip('/') + '/'
        absolute = urljoin(base, raw.lstrip('/'))
    parsed = urlsplit(absolute)
    scheme = 'https' if settings.IS_PRODUCTION else parsed.scheme
    return urlunsplit((scheme, parsed.netloc, parsed.path or '/', parsed.query, ''))


def canonical_url(request):
    path = request.path or '/'
    query = ''
    page = request.GET.get('page', '').strip()
    if page.isdigit() and int(page) > 1:
        query = f'page={int(page)}'
    base = safe_absolute_url(request, path)
    return f'{base}?{query}' if query else base


def image_url(request, value=None):
    candidate = value
    if candidate is not None and not isinstance(candidate, str):
        try:
            candidate = candidate.url
        except (ValueError, AttributeError):
            candidate = None
    return safe_absolute_url(
        request,
        candidate or settings.SITE_DEFAULT_IMAGE,
        fallback_path=settings.SITE_DEFAULT_IMAGE,
    )
