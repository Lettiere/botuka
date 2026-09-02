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
    return resolve_social_image(request, value)[0]


def image_metadata(request, value=None):
    return resolve_social_image(request, value)


def _image_candidates(values):
    for value in values:
        if isinstance(value, (list, tuple)):
            yield from _image_candidates(value)
        else:
            yield value


def _existing_image(value):
    """Return URL and dimensions without making external HTTP requests."""
    if value is None:
        return None
    if isinstance(value, str):
        candidate = value.strip()
        return (candidate, None, None) if candidate else None

    name = getattr(value, 'name', None)
    storage = getattr(value, 'storage', None)
    if name is not None and storage is not None:
        if not name:
            return None
        try:
            if not storage.exists(name):
                return None
        except (OSError, ValueError, AttributeError):
            return None

    try:
        candidate = value.url
    except (ValueError, AttributeError, OSError, FileNotFoundError):
        return None
    if not str(candidate or '').strip():
        return None

    try:
        width, height = value.width, value.height
    except (ValueError, AttributeError, OSError, FileNotFoundError):
        width = height = None
    return candidate, width, height


def resolve_social_image(request, *candidates):
    """Resolve the first usable social image and always provide a safe fallback."""
    selected = None
    for candidate in _image_candidates(candidates):
        selected = _existing_image(candidate)
        if selected:
            break

    is_default = selected is None
    raw_url, width, height = selected or (settings.SITE_DEFAULT_IMAGE, 1200, 630)
    url = safe_absolute_url(
        request,
        raw_url,
        fallback_path=settings.SITE_DEFAULT_IMAGE,
    )
    default_url = safe_absolute_url(
        request,
        settings.SITE_DEFAULT_IMAGE,
        fallback_path=settings.SITE_DEFAULT_IMAGE,
    )
    if is_default or url == default_url:
        width, height = 1200, 630
    path = urlsplit(url).path.lower()
    image_type = (
        'image/png' if path.endswith('.png') else
        'image/webp' if path.endswith('.webp') else
        'image/gif' if path.endswith('.gif') else
        'image/jpeg'
    )
    return url, image_type, width, height
