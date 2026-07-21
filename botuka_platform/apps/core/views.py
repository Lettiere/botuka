import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static

from apps.core.services.home import montar_contexto_home
from apps.core.seo.page_builders import home_seo
from apps.core.seo.builders import build_seo

logger = logging.getLogger('django.security.csrf')


def csrf_failure(request, reason=''):
    """Exibe uma falha segura sem incluir token, payload ou detalhe interno."""

    logger.warning(
        'CSRF rejeitado em %s %s (host=%s, user_authenticated=%s)',
        request.method,
        request.path,
        request.get_host(),
        bool(getattr(request, 'user', None) and request.user.is_authenticated),
    )
    return render(request, 'errors/csrf_failure.html', status=403)


def not_found(request, exception):
    seo = build_seo(request, title='Página não encontrada | BOTUKA', description='O endereço solicitado não foi encontrado.', robots='noindex,nofollow')
    return render(request, 'errors/404.html', {'seo': seo}, status=404)


def server_error(request):
    seo = build_seo(request, title='Erro interno | BOTUKA', description='Não foi possível carregar esta página.', robots='noindex,nofollow')
    return render(request, 'errors/500.html', {'seo': seo}, status=500)


def home(request):
    context = montar_contexto_home(getattr(request, "user", None))
    context['seo'] = home_seo(request)
    return render(
        request,
        "home/home.html",
        context,
    )


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
