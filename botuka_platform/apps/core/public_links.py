"""Validação e normalização de links públicos controlados pelo BOTUKA."""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from django.core.exceptions import ValidationError
from django.db import models


class TipoLink(models.TextChoices):
    SITE = 'SITE', 'Site'
    INSTAGRAM = 'INSTAGRAM', 'Instagram'
    FACEBOOK = 'FACEBOOK', 'Facebook'
    LINKEDIN = 'LINKEDIN', 'LinkedIn'
    TIKTOK = 'TIKTOK', 'TikTok'
    X = 'X', 'X'
    WHATSAPP = 'WHATSAPP', 'WhatsApp'
    TELEGRAM = 'TELEGRAM', 'Telegram'
    YOUTUBE = 'YOUTUBE', 'YouTube'
    OUTRO = 'OUTRO', 'Outro'


DOMINIOS_OFICIAIS = {
    TipoLink.INSTAGRAM: {'instagram.com', 'www.instagram.com'},
    TipoLink.FACEBOOK: {'facebook.com', 'www.facebook.com', 'fb.com', 'www.fb.com'},
    TipoLink.LINKEDIN: {'linkedin.com', 'www.linkedin.com'},
    TipoLink.TIKTOK: {'tiktok.com', 'www.tiktok.com'},
    TipoLink.X: {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'},
    TipoLink.WHATSAPP: {'wa.me', 'api.whatsapp.com', 'www.whatsapp.com'},
    TipoLink.TELEGRAM: {'t.me', 'telegram.me', 'www.telegram.me'},
    TipoLink.YOUTUBE: {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'},
}

PARAMETROS_RASTREAMENTO = {'fbclid', 'gclid', 'igshid', 'si'}


def normalizar_link_publico(tipo: str, valor: str) -> tuple[str, str]:
    """Retorna URL HTTPS normalizada e, quando aplicável, ID do vídeo YouTube."""

    valor = (valor or '').strip()
    if not valor or any(marcador in valor.lower() for marcador in ('<script', '<iframe', 'javascript:', 'data:', 'file:')):
        raise ValidationError('Informe somente uma URL pública segura, sem HTML ou scripts.')

    partes = urlsplit(valor)
    if partes.scheme.lower() != 'https' or not partes.hostname:
        raise ValidationError('A URL deve usar HTTPS e possuir um domínio válido.')
    if partes.username or partes.password:
        raise ValidationError('A URL não pode conter credenciais.')

    host = partes.hostname.lower().rstrip('.')
    dominios = DOMINIOS_OFICIAIS.get(tipo)
    if dominios and host not in dominios:
        raise ValidationError('Use o domínio oficial da rede social selecionada.')

    query = parse_qs(partes.query, keep_blank_values=False)
    query = {chave: valor for chave, valor in query.items() if chave.lower() not in PARAMETROS_RASTREAMENTO and not chave.lower().startswith('utm_')}
    normalizada = urlunsplit(('https', host, partes.path or '/', urlencode(query, doseq=True), ''))
    return normalizada, extrair_video_youtube(host, partes.path, query) if tipo == TipoLink.YOUTUBE else ''


def extrair_video_youtube(host: str, caminho: str, query: dict[str, list[str]]) -> str:
    """Extrai apenas IDs de vídeos/Shorts; canais e playlists permanecem sem ID."""

    candidato = ''
    if host == 'youtu.be':
        candidato = caminho.strip('/').split('/')[0]
    elif caminho == '/watch':
        candidato = (query.get('v') or [''])[0]
    elif caminho.startswith(('/shorts/', '/embed/')):
        partes = caminho.strip('/').split('/')
        candidato = partes[1] if len(partes) > 1 else ''
    if candidato and len(candidato) == 11 and all(char.isalnum() or char in '_-' for char in candidato):
        return candidato
    return ''


def url_embed_youtube(identificador: str) -> str:
    if len(identificador or '') != 11 or not all(char.isalnum() or char in '_-' for char in identificador):
        return ''
    return f'https://www.youtube-nocookie.com/embed/{identificador}'
