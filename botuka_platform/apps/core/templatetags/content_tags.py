from django import template
from math import ceil

from django.utils.html import conditional_escape, linebreaks, strip_tags
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def richtext(value):
    value = value or ""
    if "<" not in value:
        return mark_safe(linebreaks(conditional_escape(value)))
    return mark_safe(value)


@register.filter
def reading_minutes(value):
    words = len(strip_tags(value or "").split())
    return max(1, ceil(words / 200))
