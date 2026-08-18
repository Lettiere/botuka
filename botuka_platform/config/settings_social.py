import os
from .settings import *  # noqa: F403

ROOT_URLCONF = 'config.urls_social'
BOTUKA_RUNTIME = 'social'
LOGIN_URL = f'{BOTUKA_PLATFORM_BASE_URL}/conta/login/'  # noqa: F405
LOGOUT_REDIRECT_URL = f'{BOTUKA_PLATFORM_BASE_URL}/'  # noqa: F405

if 'http://127.0.0.1:7800' not in CSRF_TRUSTED_ORIGINS:  # noqa: F405
    CSRF_TRUSTED_ORIGINS.append('http://127.0.0.1:7800')  # noqa: F405

SOCIAL_EXCLUDED_CONTEXT_PROCESSORS = {
    'apps.painel.navigation.painel_navigation',
    'apps.gestao.context_processors.publicar_options',
}

TEMPLATES[0]['OPTIONS']['context_processors'] = [  # noqa: F405
    processor for processor in TEMPLATES[0]['OPTIONS']['context_processors']  # noqa: F405
    if processor not in SOCIAL_EXCLUDED_CONTEXT_PROCESSORS
]

# ======================================================================
# BOTUKA SOCIAL REALTIME
# ======================================================================

ASGI_APPLICATION = "config.asgi.application"

REDIS_URL = os.getenv("REDIS_URL", "").strip()

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        },
    }
else:
    # Desenvolvimento local com um único processo.
    # Produção deve informar REDIS_URL.
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# ======================================================================
# BOTUKA SOCIAL DAPHNE
# ======================================================================

if "daphne" not in INSTALLED_APPS:
    INSTALLED_APPS = ["daphne", *INSTALLED_APPS]
