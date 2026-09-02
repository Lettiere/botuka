import hashlib
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template import loader
from django.templatetags.static import static

from apps.core.services.home import montar_contexto_home
from apps.core.seo.page_builders import home_seo
from apps.core.seo.builders import build_seo

logger = logging.getLogger('django.security.csrf')


def _pwa_cache_version():
    """Versão automática do app shell, sobrescrevível pelo identificador do deploy."""

    configured = str(settings.PWA_VERSION).strip()
    if configured:
        return configured

    digest = hashlib.sha256()
    paths = [
        settings.BASE_DIR / 'templates' / 'pwa' / 'service-worker.js',
        settings.BASE_DIR / 'templates' / 'pwa' / 'offline.html',
        settings.BASE_DIR / 'static' / 'css' / 'platform' / 'style.css',
        settings.BASE_DIR / 'static' / 'css' / 'platform' / 'public-shell.css',
        settings.BASE_DIR / 'static' / 'js' / 'platform' / 'pwa.js',
        settings.BASE_DIR / 'static' / 'img' / 'icons' / 'botuka-icon.svg',
        settings.BASE_DIR / 'static' / 'img' / 'icons' / 'botuka-icon-192.png',
        settings.BASE_DIR / 'static' / 'img' / 'icons' / 'botuka-icon-512.png',
    ]
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


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


def permission_denied(request, exception=None):
    seo = build_seo(request, title='Acesso não autorizado | BOTUKA', description='Você não tem permissão para acessar esta página.', robots='noindex,nofollow')
    return render(request, 'errors/403.html', {'seo': seo}, status=403)


def server_error(request):
    """Renderiza o erro sem executar context processors dependentes do banco."""

    try:
        seo = build_seo(request, title='Erro interno | BOTUKA', description='Não foi possível carregar esta página.', robots='noindex,nofollow')
        content = loader.get_template('errors/500.html').render({
            'csrf_token': 'NOTPROVIDED',
            'seo': seo,
            'seo_default': seo,
        })
    except Exception:
        # O handler nunca deve substituir a exceção original por uma falha de
        # template enquanto a requisição/transação já está comprometida.
        content = (
            '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            '<meta name="robots" content="noindex,nofollow">'
            '<title>Erro interno | BOTUKA</title></head><body>'
            '<main><h1>Não foi possível carregar esta página</h1>'
            '<p>Tente novamente em alguns instantes.</p></main></body></html>'
        )
    return HttpResponse(content, status=500)


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

    icon_192 = request.build_absolute_uri(static('img/icons/botuka-icon-192.png'))
    icon_512 = request.build_absolute_uri(static('img/icons/botuka-icon-512.png'))
    maskable_512 = request.build_absolute_uri(static('img/icons/botuka-maskable-512.png'))

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
                    'src': icon_192,
                    'sizes': '192x192',
                    'type': 'image/png',
                    'purpose': 'any',
                },
                {
                    'src': icon_512,
                    'sizes': '512x512',
                    'type': 'image/png',
                    'purpose': 'any',
                },
                {
                    'src': maskable_512,
                    'sizes': '512x512',
                    'type': 'image/png',
                    'purpose': 'maskable',
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
                            'src': icon_192,
                            'sizes': '192x192',
                            'type': 'image/png',
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
                            'src': icon_192,
                            'sizes': '192x192',
                            'type': 'image/png',
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
        {'pwa_cache_version': _pwa_cache_version()},
        content_type='application/javascript; charset=utf-8',
    )
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


def offline(request):
    return render(request, 'pwa/offline.html')
