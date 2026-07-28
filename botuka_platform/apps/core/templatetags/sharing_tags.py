from django import template

from apps.core.services.public_sharing import obter_url_publica

register = template.Library()


@register.inclusion_tag('components/share_actions.html', takes_context=True)
def public_share_actions(context, objeto, tipo):
    request = context.get('request')
    title = str(getattr(objeto, 'titulo', None) or getattr(objeto, 'nome_exibicao', None) or getattr(objeto, 'nome_fantasia', None) or getattr(objeto, 'nome', objeto))
    return {'share_object': objeto, 'share_type': tipo, 'share_title': title, 'share_url': obter_url_publica(objeto, request)}
