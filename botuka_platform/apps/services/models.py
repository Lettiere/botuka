from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Avg, Count, Exists, OuterRef, Q
from django.utils import timezone

from apps.core.models import BairroCidade, CidadeBrasil, EstadoBrasil, RegiaoCidade, UUIDModel
from apps.core.public_links import TipoLink, normalizar_link_publico, url_embed_youtube
from apps.core.utils import gerar_slug_unico
from apps.core.services.rich_text import sanitizar_html_rico
from apps.organizations.models import Empresa
from apps.services.taxonomy_moderation import (
    filtro_visibilidade_catalogo,
    normalizar_nome_catalogo,
)


class CatalogoQuerySet(models.QuerySet):
    def visiveis_para(self, usuario=None):
        return self.filter(filtro_visibilidade_catalogo(usuario))


class CatalogoModerado(models.Model):
    class Origem(models.TextChoices):
        SISTEMA = 'SISTEMA', 'Sistema'
        USUARIO = 'USUARIO', 'Usuário'

    class StatusCatalogo(models.TextChoices):
        APROVADO = 'APROVADO', 'Aprovado'
        PENDENTE = 'PENDENTE', 'Pendente'
        REJEITADO = 'REJEITADO', 'Rejeitado'
        MESCLADO = 'MESCLADO', 'Mesclado'

    origem = models.CharField(max_length=10, choices=Origem.choices, default=Origem.SISTEMA)
    status_catalogo = models.CharField(
        max_length=10, choices=StatusCatalogo.choices, default=StatusCatalogo.APROVADO,
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )

    objects = CatalogoQuerySet.as_manager()

    class Meta:
        abstract = True


class ServicoQuerySet(models.QuerySet):
    def ativos(self):
        return self.filter(ativo=True, excluido_em__isnull=True)

    def delete(self):
        updated = self.update(ativo=False, excluido_em=timezone.now())
        return updated, {self.model._meta.label: updated}

    def publicamente_visiveis(self):
        vinculo_aprovado = ProfissaoTipoServico.objects.filter(
            profissao_id=OuterRef('profissao_id'),
            tipo_servico_id=OuterRef('tipo_servico_id'),
            ativo=True,
            status_catalogo=CatalogoModerado.StatusCatalogo.APROVADO,
        )
        return self.alias(
            _vinculo_taxonomia_aprovado=Exists(vinculo_aprovado),
        ).filter(
            ativo=True,
            excluido_em__isnull=True,
            status='PUBLICADO',
            publicado_em__isnull=False,
            setor__ativo=True,
            setor__status_catalogo=CatalogoModerado.StatusCatalogo.APROVADO,
            profissao__ativo=True,
            profissao__status_catalogo=CatalogoModerado.StatusCatalogo.APROVADO,
        ).filter(
            Q(area__isnull=True, profissao__area__isnull=True) | Q(
                area__ativo=True,
                area__status_catalogo=CatalogoModerado.StatusCatalogo.APROVADO,
            ),
        ).filter(
            Q(tipo_servico__isnull=True) | Q(
                tipo_servico__ativo=True,
                tipo_servico__status_catalogo=CatalogoModerado.StatusCatalogo.APROVADO,
                _vinculo_taxonomia_aprovado=True,
            ),
        )


class ServicoManager(models.Manager):
    def get_queryset(self):
        return ServicoQuerySet(self.model, using=self._db).ativos()

    def publicamente_visiveis(self):
        return self.get_queryset().publicamente_visiveis()


class Setor(CatalogoModerado, UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_setor_id')
    nome = models.CharField(max_length=120, unique=True, db_column='services_setor_nome')
    slug = models.SlugField(max_length=160, unique=True, blank=True, db_column='services_setor_slug')
    descricao = models.TextField(blank=True, db_column='services_setor_descricao')
    icone = models.CharField(max_length=80, blank=True, db_column='services_setor_icone')
    ordem = models.PositiveIntegerField(default=0, db_column='services_setor_ordem')
    ativo = models.BooleanField(default=True, db_column='services_setor_ativo')
    nome_normalizado = models.CharField(max_length=120, blank=True, db_index=True)
    mesclado_com = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='itens_mesclados',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_setor_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_setor_atualizado_em')

    class Meta:
        ordering = ['ordem', 'nome']
        db_table = '"services"."services_setor_tb"'
        indexes = [models.Index(fields=['slug'], name='services_setor_idx_slug')]

    def save(self, *args, **kwargs):
        self.nome_normalizado = normalizar_nome_catalogo(self.nome)
        if kwargs.get('update_fields') is not None and 'nome' in kwargs['update_fields']:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'nome_normalizado'}
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class AreaProfissional(CatalogoModerado, UUIDModel):
    id = models.BigAutoField(
        primary_key=True,
        db_column='services_area_profissional_id',
    )
    setor = models.ForeignKey(
        Setor,
        on_delete=models.PROTECT,
        db_column='services_area_profissional_fk_setor',
        related_name='areas_profissionais',
    )
    nome = models.CharField(
        max_length=120,
        db_column='services_area_profissional_nome',
    )
    slug = models.SlugField(
        max_length=180,
        blank=True,
        db_column='services_area_profissional_slug',
    )
    descricao = models.TextField(
        blank=True,
        db_column='services_area_profissional_descricao',
    )
    ordem = models.PositiveIntegerField(
        default=0,
        db_column='services_area_profissional_ordem',
    )
    ativo = models.BooleanField(
        default=True,
        db_column='services_area_profissional_ativo',
    )
    nome_normalizado = models.CharField(max_length=120, blank=True, db_index=True)
    mesclado_com = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='itens_mesclados',
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        db_column='services_area_profissional_criado_em',
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        db_column='services_area_profissional_atualizado_em',
    )

    class Meta:
        ordering = ['setor__nome', 'ordem', 'nome']
        db_table = '"services"."services_area_profissional_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['setor', 'nome'],
                name='services_area_profissional_setor_nome_uk',
            ),
        ]
        indexes = [
            models.Index(
                fields=['setor', 'slug'],
                name='services_area_prof_idx_slug',
            ),
        ]

    def save(self, *args, **kwargs):
        self.nome_normalizado = normalizar_nome_catalogo(self.nome)
        if kwargs.get('update_fields') is not None and 'nome' in kwargs['update_fields']:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'nome_normalizado'}
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.nome} ({self.setor})'


class CBOGrandeGrupo(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_cbo_grande_grupo_id')
    codigo = models.CharField(max_length=2, unique=True, db_column='services_cbo_grande_grupo_codigo')
    titulo = models.CharField(max_length=255, db_column='services_cbo_grande_grupo_titulo')
    ativo = models.BooleanField(default=True, db_column='services_cbo_grande_grupo_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_cbo_grande_grupo_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_cbo_grande_grupo_atualizado_em')

    class Meta:
        ordering = ['codigo']
        db_table = '"services"."services_cbo_grande_grupo_tb"'

    def __str__(self):
        return f'{self.codigo} — {self.titulo}'


class CBOSubgrupoPrincipal(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_cbo_subgrupo_principal_id')
    grande_grupo = models.ForeignKey(CBOGrandeGrupo, on_delete=models.PROTECT, db_column='services_cbo_subgrupo_principal_fk_grande_grupo', related_name='subgrupos_principais')
    codigo = models.CharField(max_length=2, unique=True, db_column='services_cbo_subgrupo_principal_codigo')
    titulo = models.CharField(max_length=255, db_column='services_cbo_subgrupo_principal_titulo')
    ativo = models.BooleanField(default=True, db_column='services_cbo_subgrupo_principal_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_cbo_subgrupo_principal_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_cbo_subgrupo_principal_atualizado_em')

    class Meta:
        ordering = ['codigo']
        db_table = '"services"."services_cbo_subgrupo_principal_tb"'
        indexes = [models.Index(fields=['grande_grupo', 'codigo'], name='services_cbo_sgp_gg_cod_idx')]

    def __str__(self):
        return f'{self.codigo} — {self.titulo}'


class CBOSubgrupo(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_cbo_subgrupo_id')
    subgrupo_principal = models.ForeignKey(CBOSubgrupoPrincipal, on_delete=models.PROTECT, db_column='services_cbo_subgrupo_fk_subgrupo_principal', related_name='subgrupos')
    codigo = models.CharField(max_length=3, unique=True, db_column='services_cbo_subgrupo_codigo')
    titulo = models.CharField(max_length=255, db_column='services_cbo_subgrupo_titulo')
    ativo = models.BooleanField(default=True, db_column='services_cbo_subgrupo_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_cbo_subgrupo_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_cbo_subgrupo_atualizado_em')

    class Meta:
        ordering = ['codigo']
        db_table = '"services"."services_cbo_subgrupo_tb"'
        indexes = [models.Index(fields=['subgrupo_principal', 'codigo'], name='services_cbo_sg_sgp_cod_idx')]

    def __str__(self):
        return f'{self.codigo} — {self.titulo}'


class CBOFamilia(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_cbo_familia_id')
    subgrupo = models.ForeignKey(CBOSubgrupo, on_delete=models.PROTECT, db_column='services_cbo_familia_fk_subgrupo', related_name='familias')
    codigo = models.CharField(max_length=4, unique=True, db_column='services_cbo_familia_codigo')
    titulo = models.CharField(max_length=255, db_column='services_cbo_familia_titulo')
    ativo = models.BooleanField(default=True, db_column='services_cbo_familia_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_cbo_familia_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_cbo_familia_atualizado_em')

    class Meta:
        ordering = ['codigo']
        db_table = '"services"."services_cbo_familia_tb"'
        indexes = [models.Index(fields=['subgrupo', 'codigo'], name='services_cbo_fam_sg_cod_idx')]

    def __str__(self):
        return f'{self.codigo} — {self.titulo}'


class CBOOcupacao(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_cbo_ocupacao_id')
    familia = models.ForeignKey(CBOFamilia, on_delete=models.PROTECT, db_column='services_cbo_ocupacao_fk_familia', related_name='ocupacoes')
    codigo = models.CharField(max_length=6, unique=True, db_column='services_cbo_ocupacao_codigo')
    titulo = models.CharField(max_length=255, db_column='services_cbo_ocupacao_titulo')
    ativo = models.BooleanField(default=True, db_column='services_cbo_ocupacao_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_cbo_ocupacao_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_cbo_ocupacao_atualizado_em')

    class Meta:
        ordering = ['codigo']
        db_table = '"services"."services_cbo_ocupacao_tb"'
        indexes = [models.Index(fields=['familia', 'codigo'], name='services_cbo_oc_fam_cod_idx')]

    def __str__(self):
        return f'{self.codigo} — {self.titulo}'


class CBOSinonimo(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_cbo_sinonimo_id')
    ocupacao = models.ForeignKey(CBOOcupacao, on_delete=models.CASCADE, db_column='services_cbo_sinonimo_fk_ocupacao', related_name='sinonimos')
    titulo = models.CharField(max_length=255, db_column='services_cbo_sinonimo_titulo')
    ativo = models.BooleanField(default=True, db_column='services_cbo_sinonimo_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_cbo_sinonimo_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_cbo_sinonimo_atualizado_em')

    class Meta:
        ordering = ['titulo']
        db_table = '"services"."services_cbo_sinonimo_tb"'
        constraints = [models.UniqueConstraint(fields=['ocupacao', 'titulo'], name='services_cbo_sinonimo_ocup_titulo_uk')]
        indexes = [models.Index(fields=['ocupacao', 'ativo'], name='services_cbo_sin_oc_ativo_idx')]

    def __str__(self):
        return self.titulo


class Profissao(CatalogoModerado, UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_profissao_id')
    setor = models.ForeignKey(Setor, on_delete=models.PROTECT, db_column='services_profissao_fk_setor', related_name='profissoes')
    area = models.ForeignKey(
        AreaProfissional,
        on_delete=models.PROTECT,
        db_column='services_profissao_fk_area',
        related_name='profissoes',
        null=True,
        blank=True,
    )
    nome = models.CharField(max_length=120, db_column='services_profissao_nome')
    slug = models.SlugField(max_length=180, blank=True, db_column='services_profissao_slug')
    descricao = models.TextField(blank=True, db_column='services_profissao_descricao')
    exige_registro_profissional = models.BooleanField(default=False, db_column='services_profissao_exige_registro_profissional')
    tipo_registro = models.CharField(max_length=60, blank=True, db_column='services_profissao_tipo_registro')
    ativo = models.BooleanField(default=True, db_column='services_profissao_ativo')
    nome_normalizado = models.CharField(max_length=120, blank=True, db_index=True)
    mesclado_com = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='itens_mesclados',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_profissao_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_profissao_atualizado_em')
    ocupacoes_cbo = models.ManyToManyField(
        'CBOOcupacao',
        through='ProfissaoCBO',
        related_name='profissoes',
        blank=True,
    )

    class Meta:
        ordering = ['setor__nome', 'nome']
        db_table = '"services"."services_profissao_tb"'
        constraints = [models.UniqueConstraint(fields=['setor', 'nome'], name='services_profissao_setor_nome_uk')]
        indexes = [models.Index(fields=['setor', 'slug'], name='services_profissao_idx_slug')]

    def save(self, *args, **kwargs):
        self.nome_normalizado = normalizar_nome_catalogo(self.nome)
        if kwargs.get('update_fields') is not None and 'nome' in kwargs['update_fields']:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'nome_normalizado'}
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.area_id and self.setor_id and self.area.setor_id != self.setor_id:
            raise ValidationError({'area': 'A área profissional deve pertencer ao setor da profissão.'})

    def __str__(self):
        return f'{self.nome} ({self.setor})'


class ProfissaoCBO(UUIDModel):
    CONFIANCA_CHOICES = (('ALTA', 'Alta'), ('MEDIA', 'Média'), ('BAIXA', 'Baixa'))
    id = models.BigAutoField(primary_key=True, db_column='services_profissao_cbo_id')
    profissao = models.ForeignKey(Profissao, on_delete=models.PROTECT, db_column='services_profissao_cbo_fk_profissao', related_name='vinculos_cbo')
    ocupacao = models.ForeignKey(CBOOcupacao, on_delete=models.PROTECT, db_column='services_profissao_cbo_fk_ocupacao', related_name='vinculos_profissoes')
    principal = models.BooleanField(default=False, db_column='services_profissao_cbo_principal')
    confianca = models.CharField(max_length=8, choices=CONFIANCA_CHOICES, blank=True, db_column='services_profissao_cbo_confianca')
    origem = models.CharField(max_length=80, blank=True, db_column='services_profissao_cbo_origem')
    observacao = models.TextField(blank=True, db_column='services_profissao_cbo_observacao')
    ativo = models.BooleanField(default=True, db_column='services_profissao_cbo_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_profissao_cbo_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_profissao_cbo_atualizado_em')

    class Meta:
        ordering = ['profissao__nome', '-principal', 'ocupacao__codigo']
        db_table = '"services"."services_profissao_cbo_tb"'
        constraints = [
            models.UniqueConstraint(fields=['profissao', 'ocupacao'], name='services_profissao_cbo_prof_ocup_uk'),
            models.UniqueConstraint(fields=['profissao'], condition=models.Q(principal=True), name='services_profissao_cbo_principal_uk'),
        ]
        indexes = [
            models.Index(fields=['profissao', 'ativo'], name='services_prof_cbo_ativo_idx'),
            models.Index(fields=['ocupacao', 'ativo'], name='services_cbo_prof_ativo_idx'),
        ]

    def __str__(self):
        return f'{self.profissao} — {self.ocupacao}'


class TipoServico(CatalogoModerado, UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_tipo_servico_id')
    nome = models.CharField(max_length=120, unique=True, db_column='services_tipo_servico_nome')
    slug = models.SlugField(max_length=160, unique=True, blank=True, db_column='services_tipo_servico_slug')
    descricao = models.TextField(blank=True, db_column='services_tipo_servico_descricao')
    ativo = models.BooleanField(default=True, db_column='services_tipo_servico_ativo')
    nome_normalizado = models.CharField(max_length=120, blank=True, db_index=True)
    mesclado_com = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='itens_mesclados',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_tipo_servico_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_tipo_servico_atualizado_em')
    profissoes = models.ManyToManyField(
        Profissao, through='ProfissaoTipoServico', related_name='tipos_servico', blank=True,
    )

    class Meta:
        ordering = ['nome']
        db_table = '"services"."services_tipo_servico_tb"'

    def save(self, *args, **kwargs):
        self.nome_normalizado = normalizar_nome_catalogo(self.nome)
        if kwargs.get('update_fields') is not None and 'nome' in kwargs['update_fields']:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'nome_normalizado'}
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class ProfissaoTipoServico(CatalogoModerado, UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_profissao_tipo_servico_id')
    profissao = models.ForeignKey(
        Profissao, on_delete=models.PROTECT,
        db_column='services_profissao_tipo_servico_fk_profissao',
        related_name='vinculos_tipos_servico',
    )
    tipo_servico = models.ForeignKey(
        TipoServico, on_delete=models.PROTECT,
        db_column='services_profissao_tipo_servico_fk_tipo_servico',
        related_name='vinculos_profissoes',
    )
    ordem = models.PositiveIntegerField(default=0, db_column='services_profissao_tipo_servico_ordem')
    ativo = models.BooleanField(default=True, db_column='services_profissao_tipo_servico_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_profissao_tipo_servico_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_profissao_tipo_servico_atualizado_em')

    class Meta:
        ordering = ['ordem', 'tipo_servico__nome']
        db_table = '"services"."services_profissao_tipo_servico_tb"'
        constraints = [models.UniqueConstraint(
            fields=['profissao', 'tipo_servico'], name='services_profissao_tipo_servico_uk',
        )]
        indexes = [models.Index(
            fields=['profissao', 'ativo'], name='services_prof_tipo_ativo_idx',
        )]

    def __str__(self):
        return f'{self.profissao} — {self.tipo_servico}'


class FormaCobranca(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_forma_cobranca_id')
    nome = models.CharField(max_length=120, unique=True, db_column='services_forma_cobranca_nome')
    slug = models.SlugField(max_length=160, unique=True, blank=True, db_column='services_forma_cobranca_slug')
    ativo = models.BooleanField(default=True, db_column='services_forma_cobranca_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_forma_cobranca_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_forma_cobranca_atualizado_em')

    class Meta:
        ordering = ['nome']
        db_table = '"services"."services_forma_cobranca_tb"'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class Servico(UUIDModel):
    class PrestadorTipo(models.TextChoices):
        PESSOA_FISICA = 'PESSOA_FISICA', 'Pessoa física'
        EMPRESA = 'EMPRESA', 'Empresa'

    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        PENDENTE = 'PENDENTE', 'Pendente'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        PUBLICADO = 'PUBLICADO', 'Publicado'
        PAUSADO = 'PAUSADO', 'Pausado'
        REJEITADO = 'REJEITADO', 'Rejeitado'
        BLOQUEADO = 'BLOQUEADO', 'Bloqueado'

    id = models.BigAutoField(primary_key=True, db_column='services_servico_id')
    usuario_responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column='services_servico_fk_usuario_responsavel', related_name='servicos_responsavel')
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, null=True, blank=True, db_column='services_servico_fk_empresa', related_name='servicos')
    prestador_tipo = models.CharField(max_length=20, choices=PrestadorTipo.choices, db_column='services_servico_prestador_tipo')
    setor = models.ForeignKey(
        Setor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='services_servico_fk_setor',
        related_name='servicos',
    )
    area = models.ForeignKey(
        AreaProfissional,
        on_delete=models.PROTECT,
        db_column='services_servico_fk_area',
        related_name='servicos',
        null=True,
        blank=True,
    )
    profissao = models.ForeignKey(
        Profissao,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='services_servico_fk_profissao',
        related_name='servicos',
    )
    tipo_servico = models.ForeignKey(
        TipoServico,
        on_delete=models.PROTECT,
        db_column='services_servico_fk_tipo_servico',
        related_name='servicos',
        null=True,
        blank=True,
    )
    forma_cobranca = models.ForeignKey(
        FormaCobranca,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='services_servico_fk_forma_cobranca',
        related_name='servicos',
    )
    titulo = models.CharField(max_length=160, blank=True, db_column='services_servico_titulo')
    slug = models.SlugField(max_length=220, unique=True, blank=True, db_column='services_servico_slug')
    descricao_curta = models.CharField(max_length=220, blank=True, db_column='services_servico_descricao_curta')
    descricao_completa = models.TextField(blank=True, db_column='services_servico_descricao_completa')
    experiencia = models.TextField(blank=True, db_column='services_servico_experiencia')
    preco_inicial = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, db_column='services_servico_preco_inicial')
    preco_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, db_column='services_servico_preco_final')
    preco_sob_consulta = models.BooleanField(default=False, db_column='services_servico_preco_sob_consulta')
    unidade_preco = models.CharField(max_length=60, blank=True, db_column='services_servico_unidade_preco')
    atendimento_remoto = models.BooleanField(default=False, db_column='services_servico_atendimento_remoto')
    atendimento_presencial = models.BooleanField(default=True, db_column='services_servico_atendimento_presencial')
    atendimento_emergencial = models.BooleanField(default=False, db_column='services_servico_atendimento_emergencial')
    prazo_medio = models.CharField(max_length=120, blank=True, db_column='services_servico_prazo_medio')
    telefone_publico = models.CharField(max_length=20, blank=True, db_column='services_servico_telefone_publico')
    whatsapp_publico = models.CharField(max_length=20, blank=True, db_column='services_servico_whatsapp_publico')
    email_publico = models.EmailField(blank=True, db_column='services_servico_email_publico')
    destaque = models.BooleanField(default=False, db_column='services_servico_destaque')
    verificado = models.BooleanField(default=False, db_column='services_servico_verificado')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RASCUNHO, db_column='services_servico_status')
    ativo = models.BooleanField(default=True, db_column='services_servico_ativo')
    publicado_em = models.DateTimeField(null=True, blank=True, db_column='services_servico_publicado_em')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_servico_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_servico_atualizado_em')
    excluido_em = models.DateTimeField(null=True, blank=True, db_column='services_servico_excluido_em')
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column='services_servico_qr_token')
    qr_ativo = models.BooleanField(default=True, db_default=True, db_column='services_servico_qr_ativo')
    qr_atualizado_em = models.DateTimeField(default=timezone.now, db_column='services_servico_qr_atualizado_em')

    objects = ServicoManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-criado_em']
        db_table = '"services"."services_servico_tb"'
        permissions = [
            ('aprovar_servico', 'Pode aprovar serviço'),
            ('bloquear_servico', 'Pode bloquear serviço'),
        ]
        indexes = [
            models.Index(fields=['slug'], name='services_servico_idx_slug'),
            models.Index(fields=['status'], name='services_servico_idx_status'),
            models.Index(fields=['usuario_responsavel'], name='services_servico_idx_usuario'),
            models.Index(fields=['empresa'], name='services_servico_idx_empresa'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(prestador_tipo='PESSOA_FISICA', empresa__isnull=True)
                    | models.Q(prestador_tipo='EMPRESA', empresa__isnull=False)
                ),
                name='services_servico_prestador_empresa_ck',
            ),
        ]

    def clean(self):
        super().clean()
        usuario_catalogo = self.usuario_responsavel if self.usuario_responsavel_id else None
        catalogos = (
            (Setor, self.setor_id, 'setor'),
            (AreaProfissional, self.area_id, 'area'),
            (Profissao, self.profissao_id, 'profissao'),
            (TipoServico, self.tipo_servico_id, 'tipo_servico'),
        )
        for modelo, objeto_id, campo in catalogos:
            if objeto_id and not modelo.objects.visiveis_para(usuario_catalogo).filter(
                pk=objeto_id,
            ).exists():
                raise ValidationError({campo: 'Item de catálogo indisponível para este usuário.'})
        self.descricao_completa = sanitizar_html_rico(self.descricao_completa)
        self.experiencia = sanitizar_html_rico(self.experiencia)
        if self.prestador_tipo == self.PrestadorTipo.EMPRESA and not self.empresa_id:
            raise ValidationError({'empresa': 'Informe a empresa prestadora.'})
        if self.prestador_tipo == self.PrestadorTipo.PESSOA_FISICA and self.empresa_id:
            raise ValidationError({'empresa': 'Pessoa física não deve ter empresa vinculada.'})

        if self.status != self.Status.RASCUNHO:
            obrigatorios = {}
            if not self.setor_id:
                obrigatorios['setor'] = 'Informe o setor antes de enviar para publicação.'
            if not self.area_id:
                obrigatorios['area'] = 'Informe a área profissional antes de enviar para publicação.'
            if not self.profissao_id:
                obrigatorios['profissao'] = 'Informe a profissão antes de enviar para publicação.'
            if not self.forma_cobranca_id:
                obrigatorios['forma_cobranca'] = 'Informe a forma de cobrança antes de enviar para publicação.'
            if not (self.titulo or '').strip():
                obrigatorios['titulo'] = 'Informe o título antes de enviar para publicação.'
            if obrigatorios:
                raise ValidationError(obrigatorios)

        if self.area_id and self.setor_id and self.area.setor_id != self.setor_id:
            raise ValidationError({'area': 'A área profissional deve pertencer ao setor selecionado.'})
        if self.profissao_id and self.setor_id and self.profissao.setor_id != self.setor_id:
            raise ValidationError({'profissao': 'A profissão deve pertencer ao setor selecionado.'})
        # Registros legados com profissão sem área permanecem editáveis; toda
        # profissão do novo catálogo possui área e exige o mesmo vínculo.
        if self.profissao_id and self.profissao.area_id and not self.area_id:
            raise ValidationError({'area': 'Selecione a área profissional da profissão.'})
        if self.profissao_id and self.profissao.area_id and self.area_id != self.profissao.area_id:
            raise ValidationError({'profissao': 'A profissão deve pertencer à área profissional selecionada.'})
        if (
            self.profissao_id and self.tipo_servico_id and self.profissao.area_id
            and ProfissaoTipoServico.objects.visiveis_para(usuario_catalogo).filter(
                profissao_id=self.profissao_id,
                ativo=True,
            ).exists()
            and not ProfissaoTipoServico.objects.visiveis_para(usuario_catalogo).filter(
                profissao_id=self.profissao_id,
                tipo_servico_id=self.tipo_servico_id,
                ativo=True,
                tipo_servico__ativo=True,
            ).exists()
        ):
            raise ValidationError({'tipo_servico': 'O tipo de serviço não pertence à profissão selecionada.'})
        if self.preco_inicial and self.preco_final and self.preco_inicial > self.preco_final:
            raise ValidationError({'preco_final': 'O preço final não pode ser menor que o inicial.'})
        if (
            self.status != self.Status.RASCUNHO
            and not self.atendimento_remoto
            and not self.atendimento_presencial
        ):
            raise ValidationError('Informe ao menos atendimento remoto ou presencial.')
        if self.status == self.Status.PUBLICADO and self.empresa_id and not self.empresa.pode_publicar_servico:
            raise ValidationError('Empresa não está apta a publicar serviços.')
        if self.status == self.Status.PUBLICADO:
            for modelo, objeto_id, campo in catalogos:
                if objeto_id and not modelo.objects.visiveis_para(usuario_catalogo).filter(
                    pk=objeto_id, ativo=True,
                ).exists():
                    raise ValidationError({campo: 'Item de catálogo indisponível para publicação.'})
            if (
                self.profissao_id and self.tipo_servico_id
                and ProfissaoTipoServico.objects.filter(
                    profissao_id=self.profissao_id, ativo=True,
                ).exists()
                and not ProfissaoTipoServico.objects.visiveis_para(usuario_catalogo).filter(
                    profissao_id=self.profissao_id,
                    tipo_servico_id=self.tipo_servico_id,
                    ativo=True,
                    tipo_servico__ativo=True,
                ).exists()
            ):
                raise ValidationError({
                    'tipo_servico': 'O vínculo com a profissão está indisponível para publicação.',
                })

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = (self.titulo or '').strip() or f'rascunho-{self.uuid}'
            self.slug = gerar_slug_unico(self, base_slug)
        if self.status == self.Status.PUBLICADO and not self.publicado_em:
            self.publicado_em = timezone.now()
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        self.ativo = False
        self.excluido_em = timezone.now()
        self.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])
        return 1, {self._meta.label: 1}

    @property
    def media_avaliacoes(self):
        return self.avaliacoes.filter(status=ServicoAvaliacao.Status.PUBLICADA, excluido_em__isnull=True).aggregate(media=Avg('nota'))['media'] or 0

    @property
    def total_avaliacoes(self):
        return self.avaliacoes.filter(status=ServicoAvaliacao.Status.PUBLICADA, excluido_em__isnull=True).aggregate(total=Count('id'))['total'] or 0

    def __str__(self):
        return self.titulo

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('publico:servico', args=[self.slug])

    def regenerar_qr_token(self):
        self.qr_token = uuid.uuid4()
        self.qr_atualizado_em = timezone.now()
        self.save(update_fields=['qr_token', 'qr_atualizado_em', 'atualizado_em'])


class ServicoArea(UUIDModel):
    class TipoArea(models.TextChoices):
        ENDERECO = 'ENDERECO', 'Endereço'
        BAIRRO = 'BAIRRO', 'Bairro'
        CIDADE = 'CIDADE', 'Cidade'
        REGIAO = 'REGIAO', 'Região'
        ESTADO = 'ESTADO', 'Estado'
        NACIONAL = 'NACIONAL', 'Nacional'
        REMOTO = 'REMOTO', 'Remoto'

    id = models.BigAutoField(primary_key=True, db_column='services_servico_area_id')
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, db_column='services_servico_area_fk_servico', related_name='areas')
    tipo_area = models.CharField(max_length=20, choices=TipoArea.choices, db_column='services_servico_area_tipo_area')
    cidade = models.ForeignKey(CidadeBrasil, on_delete=models.PROTECT, null=True, blank=True, db_column='services_servico_area_fk_cidade')
    regiao = models.ForeignKey(RegiaoCidade, on_delete=models.PROTECT, null=True, blank=True, db_column='services_servico_area_fk_regiao')
    bairro = models.ForeignKey(BairroCidade, on_delete=models.PROTECT, null=True, blank=True, db_column='services_servico_area_fk_bairro')
    estado = models.ForeignKey(EstadoBrasil, on_delete=models.PROTECT, null=True, blank=True, db_column='services_servico_area_fk_estado')
    raio_km = models.PositiveIntegerField(null=True, blank=True, db_column='services_servico_area_raio_km')
    remoto = models.BooleanField(default=False, db_column='services_servico_area_remoto')
    nacional = models.BooleanField(default=False, db_column='services_servico_area_nacional')
    ativo = models.BooleanField(default=True, db_column='services_servico_area_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_servico_area_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_servico_area_atualizado_em')

    class Meta:
        db_table = '"services"."services_servico_area_tb"'
        constraints = [models.UniqueConstraint(fields=['servico', 'tipo_area', 'cidade', 'regiao', 'bairro', 'estado'], name='services_servico_area_uk')]


class ServicoImagem(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_servico_imagem_id')
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, db_column='services_servico_imagem_fk_servico', related_name='imagens')
    imagem = models.ImageField(upload_to='servicos/imagens/%Y/%m/', db_column='services_servico_imagem_imagem')
    legenda = models.CharField(max_length=160, blank=True, db_column='services_servico_imagem_legenda')
    credito = models.CharField(max_length=160, blank=True, db_column='services_servico_imagem_credito')
    texto_alternativo = models.CharField(max_length=220, blank=True, db_column='services_servico_imagem_alt')
    principal = models.BooleanField(default=False, db_column='services_servico_imagem_principal')
    ordem = models.PositiveIntegerField(default=0, db_column='services_servico_imagem_ordem')
    ativo = models.BooleanField(default=True, db_column='services_servico_imagem_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_servico_imagem_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_servico_imagem_atualizado_em')
    excluido_em = models.DateTimeField(null=True, blank=True, db_column='services_servico_imagem_excluido_em')

    class Meta:
        db_table = '"services"."services_servico_imagem_tb"'
        constraints = [models.UniqueConstraint(fields=['servico'], condition=models.Q(principal=True, ativo=True), name='services_servico_img_principal_uk')]

    def delete(self, using=None, keep_parents=False):
        self.ativo = False
        self.principal = False
        self.excluido_em = timezone.now()
        self.save(update_fields=['ativo', 'principal', 'excluido_em', 'atualizado_em'])
        return 1, {self._meta.label: 1}


class ServicoLink(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='services_servico_link_id')
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True, verbose_name='UUID')
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, db_column='services_servico_link_fk_servico', related_name='links')
    tipo_link = models.CharField(max_length=20, choices=TipoLink.choices, db_column='services_servico_link_tipo')
    titulo = models.CharField(max_length=120, blank=True, db_column='services_servico_link_titulo')
    url = models.URLField(max_length=500, db_column='services_servico_link_url')
    identificador_externo = models.CharField(max_length=120, null=True, blank=True, db_column='services_servico_link_identificador_externo')
    ordem = models.PositiveSmallIntegerField(default=0, db_column='services_servico_link_ordem')
    destaque = models.BooleanField(default=False, db_column='services_servico_link_destaque')
    ativo = models.BooleanField(default=True, db_column='services_servico_link_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_servico_link_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_servico_link_atualizado_em')
    excluido_em = models.DateTimeField(null=True, blank=True, db_column='services_servico_link_excluido_em')

    class Meta:
        ordering = ['-destaque', 'ordem', 'id']
        db_table = '"services"."services_servico_link_tb"'
        indexes = [models.Index(fields=['servico', 'ativo', 'ordem'], name='services_serv_link_s_a_o_idx')]
        constraints = [
            models.UniqueConstraint(fields=['servico', 'url'], condition=models.Q(ativo=True, excluido_em__isnull=True), name='services_serv_link_url_ativa_uk'),
        ]

    def clean(self):
        super().clean()
        if self.servico_id and self.ativo and self.excluido_em is None:
            ativos = type(self).objects.filter(servico_id=self.servico_id, ativo=True, excluido_em__isnull=True).exclude(pk=self.pk)
            if ativos.count() >= 15:
                raise ValidationError('Cada serviço pode ter no máximo 15 links ativos.')
            if self.tipo_link == TipoLink.YOUTUBE and ativos.filter(tipo_link=TipoLink.YOUTUBE, identificador_externo__gt='').count() >= 6:
                raise ValidationError('Cada serviço pode exibir no máximo 6 vídeos do YouTube.')
        self.url, self.identificador_externo = normalizar_link_publico(self.tipo_link, self.url)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        self.ativo = False
        self.excluido_em = timezone.now()
        self.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])
        return 1, {self._meta.label: 1}

    @property
    def url_embed(self):
        return url_embed_youtube(self.identificador_externo)


class ServicoCaracteristica(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_servico_caracteristica_id')
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, db_column='services_servico_caracteristica_fk_servico', related_name='caracteristicas')
    titulo = models.CharField(max_length=120, db_column='services_servico_caracteristica_titulo')
    descricao = models.TextField(blank=True, db_column='services_servico_caracteristica_descricao')
    icone = models.CharField(max_length=80, blank=True, db_column='services_servico_caracteristica_icone')
    ordem = models.PositiveIntegerField(default=0, db_column='services_servico_caracteristica_ordem')
    ativo = models.BooleanField(default=True, db_column='services_servico_caracteristica_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_servico_caracteristica_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_servico_caracteristica_atualizado_em')

    class Meta:
        db_table = '"services"."services_servico_caracteristica_tb"'


class ServicoAvaliacao(UUIDModel):
    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        PUBLICADA = 'PUBLICADA', 'Publicada'
        REJEITADA = 'REJEITADA', 'Rejeitada'
        DENUNCIADA = 'DENUNCIADA', 'Denunciada'

    id = models.BigAutoField(primary_key=True, db_column='services_servico_avaliacao_id')
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, db_column='services_servico_avaliacao_fk_servico', related_name='avaliacoes')
    usuario_avaliador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='services_servico_avaliacao_fk_usuario_avaliador', related_name='avaliacoes_servicos')
    nota = models.PositiveSmallIntegerField(db_column='services_servico_avaliacao_nota')
    titulo = models.CharField(max_length=120, blank=True, db_column='services_servico_avaliacao_titulo')
    comentario = models.TextField(blank=True, db_column='services_servico_avaliacao_comentario')
    resposta_prestador = models.TextField(blank=True, db_column='services_servico_avaliacao_resposta_prestador')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE, db_column='services_servico_avaliacao_status')
    verificada = models.BooleanField(default=False, db_column='services_servico_avaliacao_verificada')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_servico_avaliacao_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_servico_avaliacao_atualizado_em')
    respondido_em = models.DateTimeField(null=True, blank=True, db_column='services_servico_avaliacao_respondido_em')
    excluido_em = models.DateTimeField(null=True, blank=True, db_column='services_servico_avaliacao_excluido_em')

    class Meta:
        db_table = '"services"."services_servico_avaliacao_tb"'

    def clean(self):
        if self.nota < 1 or self.nota > 5:
            raise ValidationError({'nota': 'A nota deve estar entre 1 e 5.'})
        if self.servico_id and self.usuario_avaliador_id == self.servico.usuario_responsavel_id:
            raise ValidationError('O responsável não pode avaliar o próprio serviço.')


class ServicoFavorito(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_servico_favorito_id')
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, db_column='services_servico_favorito_fk_servico', related_name='favoritos')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='services_servico_favorito_fk_usuario', related_name='servicos_favoritos')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_servico_favorito_criado_em')

    class Meta:
        db_table = '"services"."services_servico_favorito_tb"'
        constraints = [models.UniqueConstraint(fields=['servico', 'usuario'], name='services_servico_favorito_uk')]
