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
PLATFORM_URL = config('PLATFORM_URL', default='http://127.0.0.1:7700')
SERVICES_URL = config('SERVICES_URL', default='http://127.0.0.1:7701')
PUBLIC_BASE_URL = config('PUBLIC_BASE_URL', default=PLATFORM_URL)
CNPJ_PROVIDER = config('CNPJ_PROVIDER', default='mock')
CNPJ_API_BASE_URL = config('CNPJ_API_BASE_URL', default='')
CNPJ_API_TOKEN = config('CNPJ_API_TOKEN', default='')
CNPJ_API_TIMEOUT = config('CNPJ_API_TIMEOUT', default=10, cast=int)
CNPJ_API_CACHE_HOURS = config('CNPJ_API_CACHE_HOURS', default=24, cast=int)


default_allowed_hosts = ['127.0.0.1', 'localhost']
if APP_ENV == 'production':
    default_allowed_hosts.extend(['botuka.com.br', 'www.botuka.com.br'])

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default=','.join(default_allowed_hosts),
    cast=Csv(),
)
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default=','.join(
        [
            PLATFORM_URL,
            PUBLIC_BASE_URL,
            'https://botuka.com.br',
            'https://www.botuka.com.br',
        ]
    ),
    cast=Csv(),
)

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

    # Terceiros
    'rest_framework',

    # Apps do projeto
    'apps.accounts.apps.AccountsConfig',
    'apps.core.apps.CoreConfig',
    'apps.locations.apps.LocationsConfig',
    'apps.organizations.apps.OrganizationsConfig',
    'apps.services.apps.ServicesConfig',
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
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.gestao.context_processors.public_urls',
                'apps.gestao.context_processors.publicar_options',
            ],
        },
    },
]

LOGIN_URL = 'home'
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

STATIC_URL = 'static/'

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
# Configurações Futuras
# =============================================================================

# Espaço reservado para configurações adicionais e integrações corporativas.
