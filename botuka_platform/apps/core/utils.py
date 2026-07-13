"""Utilitários compartilhados entre apps de domínio."""

from __future__ import annotations

from django.db import models
from django.utils.text import slugify


def gerar_slug_unico(
    instance: models.Model,
    texto: str,
    campo_slug: str = 'slug',
) -> str:
    """Gera slug único para o modelo da instância informada."""

    slug_base = slugify(texto)[:220] or 'item'
    slug = slug_base
    sufixo = 2
    manager = getattr(instance.__class__, 'all_objects', instance.__class__.objects)
    queryset = manager.filter(**{campo_slug: slug})

    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    while queryset.exists():
        sufixo_texto = f'-{sufixo}'
        slug = f'{slug_base[:220 - len(sufixo_texto)]}{sufixo_texto}'
        queryset = manager.filter(**{campo_slug: slug})

        if instance.pk:
            queryset = queryset.exclude(pk=instance.pk)

        sufixo += 1

    return slug
