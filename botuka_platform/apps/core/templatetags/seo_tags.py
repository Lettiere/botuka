import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def json_ld(value):
    payload = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    payload = payload.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    return mark_safe(payload)
