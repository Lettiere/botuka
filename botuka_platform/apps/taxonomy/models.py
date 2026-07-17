"""Modelos de taxonomia da plataforma."""

from __future__ import annotations

from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel, UUIDModel
from apps.core.utils import gerar_slug_unico


class Categoria(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Categoria principal de classificação."""

    id = models.BigAutoField(primary_key=True, db_column='platform_categoria_id')
    nome = models.CharField(max_length=120, unique=True, verbose_name='nome')
    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        verbose_name='slug',
    )
    descricao = models.TextField(blank=True, verbose_name='descrição')
    icone = models.CharField(max_length=80, blank=True, verbose_name='ícone')
    ordem = models.PositiveIntegerField(default=0, verbose_name='ordem')

    class Meta:
        ordering = ['ordem', 'nome']
        verbose_name = 'categoria'
        verbose_name_plural = 'categorias'
        db_table = '"platform"."platform_categoria_tb"'
        indexes = [
            models.Index(fields=['slug'], name='platform_categoria_slug_idx'),
            models.Index(fields=['nome'], name='platform_categoria_nome_idx'),
            models.Index(fields=['ordem'], name='platform_categoria_ordem_idx'),
            models.Index(fields=['ativo'], name='platform_categoria_ativo_idx'),
        ]

    def __str__(self) -> str:
        return self.nome

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)

        super().save(*args, **kwargs)


class Subcategoria(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Subcategoria vinculada a uma categoria principal."""

    id = models.BigAutoField(
        primary_key=True,
        db_column='platform_subcategoria_id',
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        db_column='platform_categoria_fk',
        related_name='subcategorias',
        verbose_name='categoria',
    )
    nome = models.CharField(max_length=120, verbose_name='nome')
    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        verbose_name='slug',
    )
    descricao = models.TextField(blank=True, verbose_name='descrição')
    ordem = models.PositiveIntegerField(default=0, verbose_name='ordem')

    class Meta:
        ordering = ['categoria__nome', 'ordem', 'nome']
        verbose_name = 'subcategoria'
        verbose_name_plural = 'subcategorias'
        db_table = '"platform"."platform_subcategoria_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['categoria', 'nome'],
                name='platform_subcategoria_nome_uk',
            ),
        ]
        indexes = [
            models.Index(fields=['categoria', 'slug'], name='platform_subcat_slug_idx'),
            models.Index(fields=['categoria', 'nome'], name='platform_subcat_nome_idx'),
            models.Index(fields=['ordem'], name='platform_subcat_ordem_idx'),
            models.Index(fields=['ativo'], name='platform_subcat_ativo_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.categoria} - {self.nome}'

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)

        super().save(*args, **kwargs)
