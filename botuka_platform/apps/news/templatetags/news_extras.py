from django import template
from django.utils.html import conditional_escape, linebreaks
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def split(value, separator=","):
    return str(value).split(separator)


@register.filter
def get_item(mapping, key):
    try:
        return mapping[key]
    except (KeyError, TypeError):
        return ""


@register.filter
def richtext(value):
    """Renderiza HTML já sanitizado e preserva artigos antigos em texto simples."""
    value = value or ""
    if "<" not in value:
        return mark_safe(linebreaks(conditional_escape(value)))
    return mark_safe(value)
