"""Modelos de localização geográfica."""

from __future__ import annotations

from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel, UUIDModel


class Pais(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """País atendido pela plataforma."""

    id = models.BigAutoField(primary_key=True, db_column='platform_pais_id')
    nome = models.CharField(max_length=100, unique=True, verbose_name='nome')
    nome_oficial = models.CharField(
        max_length=160,
        blank=True,
        verbose_name='nome oficial',
    )
    codigo_iso_2 = models.CharField(
        max_length=2,
        unique=True,
        verbose_name='código ISO 2',
    )
    codigo_iso_3 = models.CharField(
        max_length=3,
        unique=True,
        verbose_name='código ISO 3',
    )

    class Meta:
        ordering = ['nome']
        verbose_name = 'país'
        verbose_name_plural = 'países'
        db_table = '"platform"."platform_pais_tb"'
        indexes = [
            models.Index(fields=['nome'], name='platform_pais_nome_idx'),
            models.Index(fields=['codigo_iso_2'], name='platform_pais_iso2_idx'),
            models.Index(fields=['ativo'], name='platform_pais_ativo_idx'),
        ]

    def __str__(self) -> str:
        return self.nome


class Estado(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Estado ou unidade federativa."""

    id = models.BigAutoField(primary_key=True, db_column='platform_estado_id')
    pais = models.ForeignKey(
        Pais,
        on_delete=models.PROTECT,
        db_column='platform_pais_fk',
        related_name='estados',
        verbose_name='país',
    )
    nome = models.CharField(max_length=100, verbose_name='nome')
    sigla = models.CharField(max_length=2, verbose_name='sigla')
    codigo_ibge = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='código IBGE',
    )

    class Meta:
        ordering = ['pais__nome', 'nome']
        verbose_name = 'estado'
        verbose_name_plural = 'estados'
        db_table = '"platform"."platform_estado_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['pais', 'sigla'],
                name='platform_estado_pais_sigla_uk',
            ),
            models.UniqueConstraint(
                fields=['pais', 'nome'],
                name='platform_estado_pais_nome_uk',
            ),
        ]
        indexes = [
            models.Index(fields=['pais', 'nome'], name='platform_estado_nome_idx'),
            models.Index(fields=['pais', 'sigla'], name='platform_estado_sigla_idx'),
            models.Index(fields=['ativo'], name='platform_estado_ativo_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.nome}/{self.sigla}'


class Cidade(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Cidade vinculada a um estado."""

    id = models.BigAutoField(primary_key=True, db_column='platform_cidade_id')
    estado = models.ForeignKey(
        Estado,
        on_delete=models.PROTECT,
        db_column='platform_estado_fk',
        related_name='cidades',
        verbose_name='estado',
    )
    nome = models.CharField(max_length=120, verbose_name='nome')
    codigo_ibge = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='código IBGE',
    )

    class Meta:
        ordering = ['estado__sigla', 'nome']
        verbose_name = 'cidade'
        verbose_name_plural = 'cidades'
        db_table = '"platform"."platform_cidade_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['estado', 'nome'],
                name='platform_cidade_estado_nome_uk',
            ),
        ]
        indexes = [
            models.Index(fields=['estado', 'nome'], name='platform_cidade_nome_idx'),
            models.Index(fields=['codigo_ibge'], name='platform_cidade_ibge_idx'),
            models.Index(fields=['ativo'], name='platform_cidade_ativo_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.nome}/{self.estado.sigla}'


class Bairro(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Bairro vinculado a uma cidade."""

    id = models.BigAutoField(primary_key=True, db_column='platform_bairro_id')
    cidade = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        db_column='platform_cidade_fk',
        related_name='bairros',
        verbose_name='cidade',
    )
    nome = models.CharField(max_length=120, verbose_name='nome')

    class Meta:
        ordering = ['cidade__nome', 'nome']
        verbose_name = 'bairro'
        verbose_name_plural = 'bairros'
        db_table = '"platform"."platform_bairro_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['cidade', 'nome'],
                name='platform_bairro_cidade_nome_uk',
            ),
        ]
        indexes = [
            models.Index(fields=['cidade', 'nome'], name='platform_bairro_nome_idx'),
            models.Index(fields=['ativo'], name='platform_bairro_ativo_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.nome} - {self.cidade}'
