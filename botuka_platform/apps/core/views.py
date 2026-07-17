from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static


def home(request):
    return render(request, "home/home.html")


def pwa_manifest(request):
    """Manifesto PWA da plataforma BOTUKA."""

    icon_url = request.build_absolute_uri(static('img/icons/botuka-icon.svg'))

    return JsonResponse(
        {
            'name': 'BOTUKA',
            'short_name': 'BOTUKA',
            'description': (
                'BOTUKA conecta serviços, vagas, eventos, comércios, turismo '
                'e avisos da região em um só lugar.'
            ),
            'id': '/',
            'start_url': '/',
            'scope': '/',
            'display': 'standalone',
            'display_override': ['window-controls-overlay', 'standalone', 'browser'],
            'orientation': 'any',
            'background_color': '#f4f7fb',
            'theme_color': '#111827',
            'categories': ['business', 'productivity', 'social', 'travel'],
            'lang': 'pt-BR',
            'dir': 'ltr',
            'icons': [
                {
                    'src': icon_url,
                    'sizes': 'any',
                    'type': 'image/svg+xml',
                    'purpose': 'any maskable',
                },
            ],
            'shortcuts': [
                {
                    'name': 'Painel',
                    'short_name': 'Painel',
                    'description': 'Acessar o painel BOTUKA.',
                    'url': '/painel/',
                    'icons': [
                        {
                            'src': icon_url,
                            'sizes': 'any',
                            'type': 'image/svg+xml',
                        },
                    ],
                },
                {
                    'name': 'Empresas',
                    'short_name': 'Empresas',
                    'description': 'Gerenciar empresas vinculadas.',
                    'url': '/painel/empresas/',
                    'icons': [
                        {
                            'src': icon_url,
                            'sizes': 'any',
                            'type': 'image/svg+xml',
                        },
                    ],
                },
            ],
        },
        content_type='application/manifest+json',
    )


def service_worker(request):
    """Service worker com escopo raiz para mobile, tablet e desktop."""

    response = render(
        request,
        'pwa/service-worker.js',
        content_type='application/javascript; charset=utf-8',
    )
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


def offline(request):
    return render(request, 'pwa/offline.html')
