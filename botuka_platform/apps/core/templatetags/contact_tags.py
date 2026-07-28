from django import template

from apps.core.services.contacts import formatar_telefone, telefone_para_whatsapp

register = template.Library()


@register.inclusion_tag('components/public_whatsapp.html')
def public_whatsapp(objeto):
    number = getattr(objeto, 'whatsapp_publico', '') or getattr(objeto, 'whatsapp', '') or getattr(objeto, 'agendamento_whatsapp', '')
    url = telefone_para_whatsapp(number)
    return {'whatsapp_url': url, 'whatsapp_number': formatar_telefone(number) if url else ''}
