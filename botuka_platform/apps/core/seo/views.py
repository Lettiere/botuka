from django.conf import settings
from django.http import HttpResponse


def robots_txt(request):
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin/',
        'Disallow: /painel/',
        'Disallow: /gestao/',
        'Disallow: /conta/',
        'Disallow: /q/',
        'Disallow: /offline/',
        f'Sitemap: {settings.SITE_URL.rstrip("/")}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain; charset=utf-8')
