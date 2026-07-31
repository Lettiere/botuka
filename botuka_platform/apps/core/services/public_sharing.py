"""QR Code, compartilhamento e impressão para tipos públicos permitidos."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from urllib.parse import quote, urljoin, urlparse

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from .public_urls import build_public_absolute_url


@dataclass(frozen=True)
class PublicType:
    model_path: str
    route: str
    title_field: str
    kind_label: str
    published: callable
    owner_fields: tuple[str, ...] = ()


def _active(obj):
    return bool(getattr(obj, 'ativo', True)) and getattr(obj, 'excluido_em', None) is None


def _company(obj):
    return _active(obj) and getattr(obj, 'perfil_publico', False) and getattr(obj, 'status', '') == 'ATIVA'


def _service(obj):
    return _active(obj) and getattr(obj, 'status', '') == 'PUBLICADO' and getattr(obj, 'publicado_em', None) is not None


def _job(obj):
    return _active(obj) and getattr(obj, 'status', '') == 'PUBLICADA' and getattr(obj, 'publicado_em', None) is not None and (not getattr(obj, 'encerramento', None) or obj.encerramento >= timezone.localdate())


def _published(obj):
    return _active(obj) and getattr(obj, 'status', '') in {'PUBLICADO', 'PUBLICADA'} and getattr(obj, 'publicado_em', None) is not None


def _tourism(obj):
    return _active(obj) and getattr(obj, 'status', '') == 'PUBLICADO'


def _championship(obj):
    return _active(obj) and getattr(obj, 'status', '') in {'INSCRICOES', 'AGENDADO', 'EM_ANDAMENTO', 'FINALIZADO'} and getattr(getattr(obj, 'organizacao', None), 'verificado', False)


PUBLIC_TYPES = {
    'empresa': PublicType('apps.organizations.models.Empresa', 'publico:empresa', 'nome_fantasia', 'empresa', _company, ('usuario_proprietario_id',)),
    'servico': PublicType('apps.services.models.Servico', 'publico:servico', 'titulo', 'serviço', _service, ('usuario_responsavel_id',)),
    'vaga': PublicType('apps.recruitment.models.Vaga', 'recruitment_public:vaga', 'titulo', 'vaga', _job, ('criado_por_id', 'empresa.usuario_proprietario_id')),
    'noticia': PublicType('apps.news.models.Artigo', 'news_public:artigo', 'titulo', 'notícia', _published, ('autor_id', 'autor_editorial.usuario_id')),
    'turismo': PublicType('apps.tourism.models.LocalTuristico', 'tourism_public:local', 'nome', 'local turístico', _tourism, ('criado_por_id',)),
    'video': PublicType('apps.media.models.Video', 'media_public:video', 'titulo', 'vídeo', _published, ('autor_id', 'canal.proprietario_id')),
    'episodio': PublicType('apps.media.models.Episodio', 'media_public:episodio', 'titulo', 'episódio', _published, ('responsavel_id',)),
    'campeonato': PublicType('apps.sports.models.Campeonato', 'sports_public:campeonato', 'nome', 'campeonato', _championship, ('organizacao.usuario_responsavel_id',)),
}


def _import_model(path):
    module, name = path.rsplit('.', 1)
    return getattr(__import__(module, fromlist=[name]), name)


def obter_objeto_publico(tipo, uuid):
    config = PUBLIC_TYPES.get(tipo)
    if not config:
        raise PermissionDenied('Tipo de conteúdo não permitido.')
    model = _import_model(config.model_path)
    manager = getattr(model, 'all_objects', model.objects)
    obj = manager.filter(uuid=uuid).first()
    if not obj or not config.published(obj):
        raise PermissionDenied('Este conteúdo não possui divulgação pública.')
    return obj


def _path_for(objeto):
    for config in PUBLIC_TYPES.values():
        if isinstance(objeto, _import_model(config.model_path)):
            value = getattr(objeto, 'slug', None) or getattr(objeto, 'uuid', None)
            if not value:
                raise ValueError('O conteúdo não possui identificador público.')
            return reverse(config.route, args=[value]), config
    getter = getattr(objeto, 'get_absolute_url', None)
    if callable(getter):
        return getter(), None
    raise ValueError('Tipo sem rota pública registrada.')


def obter_url_publica(objeto, request=None):
    path, config = _path_for(objeto)
    if config and not config.published(objeto):
        raise PermissionDenied('Conteúdo não publicado.')
    if request is not None:
        return build_public_absolute_url(request, path)
    base = settings.PUBLIC_BASE_URL.rstrip('/') + '/'
    url = urljoin(base, path.lstrip('/'))
    allowed = urlparse(settings.PUBLIC_BASE_URL).hostname
    host = urlparse(url).hostname
    if host != allowed:
        raise PermissionDenied('Host público não permitido.')
    return url


def obter_dados_compartilhamento(objeto, request=None):
    url = obter_url_publica(objeto, request)
    _, config = _path_for(objeto)
    title = strip_tags(str(getattr(objeto, config.title_field, objeto)))[:180]
    if config.kind_label == 'vaga':
        company = strip_tags(str(getattr(objeto, 'empresa', '')))
        city = strip_tags(str(getattr(objeto, 'cidade', '') or getattr(getattr(objeto, 'empresa', None), 'cidade', '')))
        text = f'Confira esta oportunidade: {title}. {company}'
        if city:
            text += f' — {city}'
        text += f'. Veja os detalhes e candidate-se: {url}'
    elif config.kind_label == 'serviço':
        provider = strip_tags(str(getattr(objeto, 'empresa', '') or getattr(objeto, 'usuario_responsavel', '')))
        text = f'Conheça o serviço {title}, oferecido por {provider}. Saiba mais: {url}'
    else:
        text = f'Confira {config.kind_label}: {title}. Saiba mais: {url}'
    encoded_url, encoded_text = quote(url, safe=''), quote(text, safe='')
    return {
        'titulo': title, 'texto': text, 'url': url,
        'whatsapp': f'https://wa.me/?text={encoded_text}',
        'facebook': f'https://www.facebook.com/sharer/sharer.php?u={encoded_url}',
        'linkedin': f'https://www.linkedin.com/sharing/share-offsite/?url={encoded_url}',
        'telegram': f'https://t.me/share/url?url={encoded_url}&text={quote(title)}',
        'email': f'mailto:?subject={quote(title)}&body={encoded_text}',
    }


def _cache_key(objeto, formato, url):
    changed = getattr(objeto, 'atualizado_em', '')
    digest = sha256(f'{url}|{changed}'.encode()).hexdigest()[:24]
    return f'public-qr:{formato}:{digest}'


def gerar_qrcode_png(objeto, request=None):
    url = obter_url_publica(objeto, request)
    key = _cache_key(objeto, 'png', url)
    content = cache.get(key)
    if content is None:
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
        qr.add_data(url); qr.make(fit=True)
        stream = BytesIO(); qr.make_image(fill_color='black', back_color='white').save(stream, format='PNG')
        content = stream.getvalue(); cache.set(key, content, 86400)
    return content


def gerar_qrcode_svg(objeto, request=None):
    url = obter_url_publica(objeto, request)
    key = _cache_key(objeto, 'svg', url)
    content = cache.get(key)
    if content is None:
        image = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
        stream = BytesIO(); image.save(stream); content = stream.getvalue(); cache.set(key, content, 86400)
    return content


def gerar_material_impressao(objeto, request=None):
    data = obter_dados_compartilhamento(objeto, request)
    data['titulo'] = strip_tags(data['titulo'])
    data['tipo'] = _path_for(objeto)[1].kind_label
    return data
