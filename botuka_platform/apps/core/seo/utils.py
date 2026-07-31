import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from django.conf import settings
from django.utils.html import strip_tags

from apps.core.services.public_urls import build_public_absolute_url


SPACE_RE = re.compile(r'\s+')
YOUTUBE_ID_RE = re.compile(r'^[A-Za-z0-9_-]{6,20}$')


def clean_text(value, limit=None):
    text = SPACE_RE.sub(' ', strip_tags(str(value or ''))).strip()
    if not limit or len(text) <= limit:
        return text
    shortened = text[: limit + 1].rsplit(' ', 1)[0].rstrip(' ,.;:-')
    return f'{shortened}…' if shortened else text[:limit]


def first_value(*values):
    """Return the first usable value without evaluating FieldFile storage."""
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value.strip()
        elif getattr(value, 'name', None):
            return value
    return None


def youtube_video_id(value):
    """Extract a YouTube id locally; no network request is performed."""
    raw = str(value or '').strip()
    if YOUTUBE_ID_RE.fullmatch(raw):
        return raw
    parsed = urlsplit(raw)
    host = parsed.netloc.lower().split(':', 1)[0]
    parts = [part for part in parsed.path.split('/') if part]
    candidate = ''
    if host in {'youtu.be', 'www.youtu.be'} and parts:
        candidate = parts[0]
    elif host in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com'}:
        if parsed.path == '/watch':
            from urllib.parse import parse_qs
            candidate = parse_qs(parsed.query).get('v', [''])[0]
        elif len(parts) >= 2 and parts[0] in {'embed', 'shorts', 'live'}:
            candidate = parts[1]
    return candidate if YOUTUBE_ID_RE.fullmatch(candidate) else ''


def youtube_thumbnail(value, *, quality='maxresdefault'):
    video_id = youtube_video_id(value)
    return f'https://img.youtube.com/vi/{video_id}/{quality}.jpg' if video_id else ''


def iso_duration(value):
    if not value:
        return None
    if isinstance(value, str) and value.startswith('P'):
        return value
    try:
        total = max(0, int(value.total_seconds()))
    except (AttributeError, TypeError, ValueError):
        return None
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'PT{hours}H{minutes}M{seconds}S'


def safe_absolute_url(request, value='', *, fallback_path='/'):
    raw = str(value or fallback_path).strip()
    parsed = urlsplit(raw)
    if parsed.scheme and parsed.scheme not in {'http', 'https'}:
        raw = fallback_path
        parsed = urlsplit(raw)
    if parsed.scheme in {'http', 'https'}:
        absolute = raw
    elif request is not None:
        absolute = build_public_absolute_url(request, raw)
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


def image_metadata(request, value=None):
    candidate = value
    width = height = None
    is_default = not candidate
    if candidate is not None and not isinstance(candidate, str):
        try:
            width, height = candidate.width, candidate.height
        except (ValueError, AttributeError, OSError, FileNotFoundError):
            width = height = None
    url = image_url(request, candidate)
    default_url = image_url(request)
    is_default = is_default or url == default_url
    if is_default:
        width, height = 1200, 630
    path = urlsplit(url).path.lower()
    image_type = (
        'image/png' if path.endswith('.png') else
        'image/webp' if path.endswith('.webp') else
        'image/gif' if path.endswith('.gif') else
        'image/jpeg'
    )
    return url, image_type, width, height
