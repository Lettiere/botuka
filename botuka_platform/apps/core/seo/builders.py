from django.conf import settings

from .schemas import breadcrumb_schema, compact, organization, webpage, website
from .utils import canonical_url, clean_text, image_url, safe_absolute_url


def breadcrumb(request, name, url):
    return {'name': clean_text(name, 80), 'url': safe_absolute_url(request, url)}


def build_seo(
    request,
    *,
    title=None,
    description=None,
    image=None,
    image_alt=None,
    robots='index,follow',
    content_type='website',
    published_time=None,
    modified_time=None,
    author=None,
    section=None,
    tags=None,
    breadcrumbs=None,
    schemas=None,
    page_type='WebPage',
):
    canonical = canonical_url(request)
    final_title = clean_text(title or settings.SITE_NAME, 70)
    final_description = clean_text(description or settings.SITE_DEFAULT_DESCRIPTION, 160)
    final_image = image_url(request, image)
    crumbs = breadcrumbs or []
    site_url = settings.SITE_URL.rstrip('/')
    organization_schema = organization(site_url, image_url(request))
    graph = [
        organization_schema,
        website(site_url, settings.SITE_DEFAULT_DESCRIPTION, organization_schema['@id']),
        webpage(canonical, final_title, final_description, final_image, page_type=page_type),
    ]
    if crumbs:
        graph.append(breadcrumb_schema(crumbs))
    graph.extend(schemas or [])
    return {
        'title': final_title,
        'description': final_description,
        'canonical_url': canonical,
        'robots': robots,
        'image_url': final_image,
        'image_alt': clean_text(image_alt or final_title, 150),
        'image_width': 1200,
        'image_height': 630,
        'image_type': 'image/png' if final_image.lower().endswith('.png') else 'image/jpeg',
        'content_type': content_type,
        'published_time': published_time,
        'modified_time': modified_time,
        'author': clean_text(author, 100),
        'section': clean_text(section, 100),
        'tags': [clean_text(tag, 60) for tag in (tags or []) if clean_text(tag, 60)],
        'breadcrumbs': crumbs,
        'schema': {'@context': 'https://schema.org', '@graph': compact(graph)},
    }
