"""
Configurações do projeto BOTUKA.

Gerado por 'django-admin startproject' usando Django 6.0.6.

Para mais informações, consulte:
https://docs.djangoproject.com/en/6.0/topics/settings/

Para a lista completa de configurações e seus valores:
https://docs.djangoproject.com/en/6.0/ref/settings/
"""

from pathlib import Path
from decouple import config, Csv
from django.core.exceptions import ImproperlyConfigured


def cast_debug(value: object) -> bool:
    """Converte valores corporativos de ambiente para booleano de DEBUG."""

    if isinstance(value, bool):
        return value

    normalized_value = str(value).strip().lower()
    false_values = {'0', 'false', 'no', 'off', 'release', 'prod', 'production'}
    true_values = {'1', 'true', 'yes', 'on', 'debug', 'dev', 'development'}

    if normalized_value in false_values:
        return False

    if normalized_value in true_values:
        return True

    raise ValueError(f'Valor inválido para DEBUG: {value}')


# =============================================================================
# Projeto
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# Segurança
# =============================================================================

SECRET_KEY = config('SECRET_KEY', default='change-me')
DEBUG = config('DEBUG', default=True, cast=cast_debug)
APP_ENV = config('APP_ENV', default='development')
IS_PRODUCTION = APP_ENV.strip().lower() in {'prod', 'production'}
if IS_PRODUCTION and DEBUG:
    raise ImproperlyConfigured('DEBUG deve ser False quando APP_ENV=production.')
PLATFORM_URL = config('PLATFORM_URL', default='http://127.0.0.1:7700')
SERVICES_URL = config('SERVICES_URL', default='http://127.0.0.1:7701')
PUBLIC_BASE_URL = config('PUBLIC_BASE_URL', default=PLATFORM_URL)
CNPJ_PROVIDER = config('CNPJ_PROVIDER', default='mock')
CNPJ_API_BASE_URL = config('CNPJ_API_BASE_URL', default='')
CNPJ_API_TOKEN = config('CNPJ_API_TOKEN', default='')
CNPJ_API_TIMEOUT = config('CNPJ_API_TIMEOUT', default=10, cast=int)
CNPJ_API_CACHE_HOURS = config('CNPJ_API_CACHE_HOURS', default=24, cast=int)


default_allowed_hosts = ['127.0.0.1', 'localhost']
if IS_PRODUCTION:
    default_allowed_hosts.extend(['botuka.com.br', 'www.botuka.com.br'])

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default=','.join(default_allowed_hosts),
    cast=Csv(),
)
if IS_PRODUCTION:
    production_hosts = {'botuka.com.br', 'www.botuka.com.br'}
    configured_hosts = set(ALLOWED_HOSTS)
    if '*' in configured_hosts or configured_hosts != production_hosts:
        raise ImproperlyConfigured(
            'Em produção, ALLOWED_HOSTS deve conter somente botuka.com.br e '
            'www.botuka.com.br.'
        )
default_csrf_trusted_origins = [
    'https://botuka.com.br',
    'https://www.botuka.com.br',
]
if not IS_PRODUCTION:
    default_csrf_trusted_origins.extend([
        'http://127.0.0.1:7700',
        'http://localhost:7700',
    ])

configured_csrf_trusted_origins = config(
    'CSRF_TRUSTED_ORIGINS',
    default=','.join(default_csrf_trusted_origins),
    cast=Csv(),
)
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([
    *configured_csrf_trusted_origins,
    *default_csrf_trusted_origins,
]))
CSRF_COOKIE_SECURE = config(
    'CSRF_COOKIE_SECURE', default=IS_PRODUCTION, cast=cast_debug,
)
SESSION_COOKIE_SECURE = config(
    'SESSION_COOKIE_SECURE', default=IS_PRODUCTION, cast=cast_debug,
)
CSRF_COOKIE_SAMESITE = config('CSRF_COOKIE_SAMESITE', default='Lax')
SESSION_COOKIE_SAMESITE = config('SESSION_COOKIE_SAMESITE', default='Lax')
CONSENT_POLICY_VERSION = '2026-07-25'
CONSENT_MAX_AGE_DAYS = 365
USE_X_FORWARDED_HOST = config(
    'USE_X_FORWARDED_HOST', default=IS_PRODUCTION, cast=cast_debug,
)
if config('USE_PROXY_SSL_HEADER', default=IS_PRODUCTION, cast=cast_debug):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if IS_PRODUCTION and (not CSRF_COOKIE_SECURE or not SESSION_COOKIE_SECURE):
    raise ImproperlyConfigured(
        'Cookies CSRF e de sessão devem ser Secure em produção.'
    )

CSRF_FAILURE_VIEW = 'apps.core.views.csrf_failure'

WEATHER_API_URL = config('WEATHER_API_URL', default='')
WEATHER_API_KEY = config('WEATHER_API_KEY', default='')
WEATHER_CITY = config('WEATHER_CITY', default='Botucatu')
WEATHER_LATITUDE = config('WEATHER_LATITUDE', default='-22.8858')
WEATHER_LONGITUDE = config('WEATHER_LONGITUDE', default='-48.4451')
WEATHER_CACHE_SECONDS = config('WEATHER_CACHE_SECONDS', default=1200, cast=int)
MAP_PROVIDER = config('MAP_PROVIDER', default='openstreetmap')

# =============================================================================
# Aplicações
# =============================================================================

INSTALLED_APPS = [
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',

    # Terceiros
    'rest_framework',

    # Apps do projeto
    'apps.accounts.apps.AccountsConfig',
    'apps.core.apps.CoreConfig',
    'apps.locations.apps.LocationsConfig',
    'apps.organizations.apps.OrganizationsConfig',
    'apps.services.apps.ServicesConfig',
    'apps.recruitment.apps.RecruitmentConfig',
    'apps.tourism.apps.TourismConfig',
    'apps.sports.apps.SportsConfig',
    'apps.media.apps.MediaConfig',
    'apps.news.apps.NewsConfig',
    'apps.government.apps.GovernmentConfig',
    'apps.taxonomy.apps.TaxonomyConfig',
    'apps.gestao.apps.GestaoConfig',
    'apps.painel.apps.PainelConfig',
]

AUTH_USER_MODEL = 'accounts.Usuario'

# =============================================================================
# Middleware
# =============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# =============================================================================
# Templates
# =============================================================================

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'libraries': {
                'botuka_admin': 'apps.core.templatetags.botuka_admin',
            },
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.gestao.context_processors.public_urls',
                'apps.gestao.context_processors.publicar_options',
                'apps.painel.navigation.painel_navigation',
                'apps.core.context_processors.seo.seo_context',
                'apps.core.context_processors.weather.weather',
            ],
        },
    },
]

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'botuka-local',
    }
}

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = 'gestao:dashboard'
LOGOUT_REDIRECT_URL = 'home'

WSGI_APPLICATION = 'config.wsgi.application'

# =============================================================================
# Banco de Dados
# =============================================================================

# Por padrão, utiliza SQLite. Preparado para PostgreSQL via python-decouple.
DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.sqlite3'),
        'NAME': config('DB_NAME', default=BASE_DIR / 'db.sqlite3'),
        'USER': config('DB_USER', default=''),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default=''),
        'PORT': config('DB_PORT', default=''),
    }
}

# =============================================================================
# Validação de Senhas
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'UserAttributeSimilarityValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'MinimumLengthValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'CommonPasswordValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'NumericPasswordValidator'
        ),
    },
]

# =============================================================================
# Internacionalização
# =============================================================================

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True

# =============================================================================
# Arquivos Estáticos
# =============================================================================

# Deve ser absoluto: caminhos relativos quebram CSS/JS em rotas aninhadas,
# como /empresas/, /servicos/ e páginas de detalhe.
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

# =============================================================================
# Media
# =============================================================================

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# =============================================================================
# SEO, indexação e integrações opcionais
# =============================================================================

SITE_NAME = config('SITE_NAME', default='BOTUKA')
SITE_URL = config('SITE_URL', default=PUBLIC_BASE_URL).rstrip('/')
SITE_DEFAULT_DESCRIPTION = config(
    'SITE_DEFAULT_DESCRIPTION',
    default='Empresas, serviços, eventos, vagas e notícias de Botucatu em um só lugar.',
)
SITE_DEFAULT_IMAGE = config(
    'SITE_DEFAULT_IMAGE', default='/static/img/seo/botuka-default-1200x630.png',
)
SITE_DEFAULT_LOCALE = config('SITE_DEFAULT_LOCALE', default='pt_BR')
GOOGLE_TAG_MANAGER_ID = config('GOOGLE_TAG_MANAGER_ID', default='').strip()
GOOGLE_ANALYTICS_ID = config('GOOGLE_ANALYTICS_ID', default='').strip()
GOOGLE_SITE_VERIFICATION = config('GOOGLE_SITE_VERIFICATION', default='').strip()
GOOGLE_ADS_ID = config('GOOGLE_ADS_ID', default='').strip()
GOOGLE_ADS_CONVERSION_ID = config('GOOGLE_ADS_CONVERSION_ID', default='').strip()
GOOGLE_ADS_CONVERSION_LABEL = config('GOOGLE_ADS_CONVERSION_LABEL', default='').strip()
META_PIXEL_ID = config('META_PIXEL_ID', default='').strip()
META_DOMAIN_VERIFICATION = config('META_DOMAIN_VERIFICATION', default='').strip()
MICROSOFT_CLARITY_ID = config('MICROSOFT_CLARITY_ID', default='').strip()
BING_SITE_VERIFICATION = config('BING_SITE_VERIFICATION', default='').strip()
PINTEREST_DOMAIN_VERIFICATION = config('PINTEREST_DOMAIN_VERIFICATION', default='').strip()
TWITTER_SITE = config('TWITTER_SITE', default='').strip()
TWITTER_CREATOR = config('TWITTER_CREATOR', default='').strip()
ENABLE_ANALYTICS = config('ENABLE_ANALYTICS', default=False, cast=cast_debug)
ENABLE_MARKETING_TAGS = config('ENABLE_MARKETING_TAGS', default=False, cast=cast_debug)

# =============================================================================
# Configurações Futuras
# =============================================================================

# Espaço reservado para configurações adicionais e integrações corporativas.
