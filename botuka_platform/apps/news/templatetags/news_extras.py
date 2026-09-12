import re
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
    """Renderiza HTML sanitizado e incorpora marcadores YouTube controlados."""
    value = value or ""

    if "<" not in value:
        return mark_safe(linebreaks(conditional_escape(value)))

    youtube_marker = re.compile(
        r'<div class="richtext-youtube" '
        r'data-youtube-id="([A-Za-z0-9_-]{11})"></div>'
    )

    def render_youtube(match):
        video_id = match.group(1)
        return (
            '<div class="article-embed article-embed--youtube">'
            '<iframe '
            'loading="lazy" '
            f'src="https://www.youtube-nocookie.com/embed/{video_id}" '
            'title="Vídeo do YouTube" '
            'allow="accelerometer; encrypted-media; picture-in-picture" '
            'allowfullscreen>'
            '</iframe>'
            '</div>'
        )

    value = youtube_marker.sub(render_youtube, value)
    return mark_safe(value)
