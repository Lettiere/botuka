from django import template

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
