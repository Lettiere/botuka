from django import template

from apps.core.services.public_sharing import obter_url_publica
from apps.core.services.public_urls import build_public_absolute_url

register = template.Library()


@register.simple_tag(takes_context=True)
def public_url(context, objeto):
    if not objeto:
        return ''
    request = context.get('request')
    getter = getattr(objeto, 'get_absolute_url', None)
    if callable(getter):
        return build_public_absolute_url(request, getter())
    if isinstance(objeto, str):
        return build_public_absolute_url(request, objeto)
    try:
        return obter_url_publica(objeto, request)
    except ValueError:
        return build_public_absolute_url(request, str(objeto))


@register.inclusion_tag('components/share_actions.html', takes_context=True)
def public_share_actions(context, objeto, tipo):
    request = context.get('request')
    title = str(getattr(objeto, 'titulo', None) or getattr(objeto, 'nome_exibicao', None) or getattr(objeto, 'nome_fantasia', None) or getattr(objeto, 'nome', objeto))
    return {'share_object': objeto, 'share_type': tipo, 'share_title': title, 'share_url': obter_url_publica(objeto, request)}
