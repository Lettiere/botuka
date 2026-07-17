"""
Configurações Django para o projeto botuka_services.

Gerado por 'django-admin startproject' usando Django 6.0.5.

Veja mais informações sobre este arquivo:
https://docs.djangoproject.com/en/6.0/topics/settings/

Lista completa de configurações em:
https://docs.djangoproject.com/en/6.0/ref/settings/
"""

from pathlib import Path

from decouple import config

# Caminhos base do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# === Configurações básicas de segurança ===
# ATENÇÃO: mantenha a chave secreta em segredo em produção!
SECRET_KEY = config('SECRET_KEY', default='change-me')

# Não use DEBUG = True em produção!
DEBUG = True

# Hosts permitidos para desenvolvimento
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
]

# === Definição dos aplicativos instalados ===
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # App do projeto
    'apps.website',
]

# === Middlewares padrão do Django ===
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

# === Configuração de Templates globais ===
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],  # Diretório global de templates
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# === Banco de Dados (mantendo SQLite neste momento) ===
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# === Validação de senha ===
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# === Internacionalização ===
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Campo_Grande"

USE_I18N = True
USE_TZ = True

# === Configuração de arquivos estáticos ===
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# === Configuração de arquivos de mídia ===
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
