"""Compatibilidade do sanitizador editorial com o componente compartilhado."""

from apps.core.services.rich_text import sanitizar_html_rico


def sanitizar_html_editorial(value):
    return sanitizar_html_rico(value)
