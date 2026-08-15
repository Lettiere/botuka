"""Modelos centrais e abstrações reutilizáveis do BOTUKA."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags


class UUIDModel(models.Model):
    """Adiciona um identificador UUID público e imutável."""

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name='UUID',
    )

    class Meta:
        abstract = True


class AtributoAdicional(UUIDModel):
    class Tipo(models.TextChoices):
        CNH = 'CNH', 'CNH'
        EXPERIENCIA = 'EXPERIENCIA', 'Experiência'
        ESCOLARIDADE = 'ESCOLARIDADE', 'Escolaridade'
        CURSO = 'CURSO', 'Curso'
        CERTIFICACAO = 'CERTIFICACAO', 'Certificação'
        DISPONIBILIDADE = 'DISPONIBILIDADE', 'Disponibilidade'
        VEICULO = 'VEICULO', 'Veículo'
        IDIOMA = 'IDIOMA', 'Idioma'
        HABILIDADE = 'HABILIDADE', 'Habilidade'
        CONHECIMENTO = 'CONHECIMENTO', 'Conhecimento técnico'
        ATENDIMENTO = 'ATENDIMENTO', 'Atendimento'
        ESPECIALIDADE = 'ESPECIALIDADE', 'Especialidade'
        AREA_ATUACAO = 'AREA_ATUACAO', 'Área de atuação'
        EQUIPAMENTO = 'EQUIPAMENTO', 'Equipamento'
        PRAZO = 'PRAZO', 'Prazo'
        LOCAL_ATENDIMENTO = 'LOCAL_ATENDIMENTO', 'Local de atendimento'
        OUTRO = 'OUTRO', 'Outro'

    class Classificacao(models.TextChoices):
        OBRIGATORIO = 'OBRIGATORIO', 'Obrigatório'
        DESEJAVEL = 'DESEJAVEL', 'Desejável'
        CARACTERISTICA = 'CARACTERISTICA', 'Característica'
        DIFERENCIAL = 'DIFERENCIAL', 'Diferencial'
        CONDICAO = 'CONDICAO', 'Condição'
        INFORMATIVO = 'INFORMATIVO', 'Informativo'

    id = models.BigAutoField(primary_key=True, db_column='core_atributo_adicional_id')
    vaga = models.ForeignKey(
        'recruitment.Vaga', null=True, blank=True, on_delete=models.CASCADE,
        related_name='atributos_adicionais', db_column='core_atributo_fk_vaga',
    )
    servico = models.ForeignKey(
        'services.Servico', null=True, blank=True, on_delete=models.CASCADE,
        related_name='atributos_adicionais', db_column='core_atributo_fk_servico',
    )
    tipo = models.CharField(max_length=32, choices=Tipo.choices, db_column='core_atributo_tipo')
    nome_personalizado = models.CharField(max_length=100, blank=True, db_column='core_atributo_nome')
    valor = models.CharField(max_length=240, db_column='core_atributo_valor')
    classificacao = models.CharField(
        max_length=24, choices=Classificacao.choices, default=Classificacao.INFORMATIVO,
        db_column='core_atributo_classificacao',
    )
    observacao = models.CharField(max_length=300, blank=True, db_column='core_atributo_observacao')
    ordem = models.PositiveSmallIntegerField(default=0, db_column='core_atributo_ordem')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='core_atributo_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='core_atributo_atualizado_em')

    class Meta:
        ordering = ['ordem', 'id']
        db_table = '"core"."core_atributo_adicional_tb"'
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(vaga__isnull=False, servico__isnull=True)
                    | models.Q(vaga__isnull=True, servico__isnull=False)
                ),
                name='core_atributo_objeto_xor_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['vaga', 'tipo'], name='core_atributo_vaga_tipo_idx'),
            models.Index(fields=['servico', 'tipo'], name='core_atributo_serv_tipo_idx'),
        ]

    def clean(self):
        if bool(self.vaga_id) == bool(self.servico_id):
            raise ValidationError('O atributo deve pertencer a uma vaga ou a um serviço.')
        self.nome_personalizado = strip_tags(self.nome_personalizado or '').strip()
        self.valor = strip_tags(self.valor or '').strip()
        self.observacao = strip_tags(self.observacao or '').strip()
        if not self.valor:
            raise ValidationError({'valor': 'Informe o valor do atributo.'})
        if self.tipo == self.Tipo.OUTRO and not self.nome_personalizado:
            raise ValidationError({'nome_personalizado': 'Informe o nome do atributo personalizado.'})
        if self.vaga_id and self.classificacao not in {
            self.Classificacao.OBRIGATORIO, self.Classificacao.DESEJAVEL,
            self.Classificacao.INFORMATIVO,
        }:
            raise ValidationError({'classificacao': 'Classificação inválida para vaga.'})
        if self.servico_id and self.classificacao not in {
            self.Classificacao.CARACTERISTICA, self.Classificacao.DIFERENCIAL,
            self.Classificacao.CONDICAO, self.Classificacao.INFORMATIVO,
        }:
            raise ValidationError({'classificacao': 'Classificação inválida para serviço.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def titulo(self):
        return self.nome_personalizado if self.tipo == self.Tipo.OUTRO else self.get_tipo_display()


class TimeStampedModel(models.Model):
    """Adiciona controle de criação e atualização."""

    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='criado em',
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='atualizado em',
    )

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet com exclusão lógica em lote."""

    def delete(self) -> tuple[int, dict[str, int]]:
        updated = self.update(ativo=False, removido_em=timezone.now())
        return updated, {self.model._meta.label: updated}

    def hard_delete(self) -> tuple[int, dict[str, int]]:
        return super().delete()

    def ativos(self) -> SoftDeleteQuerySet:
        return self.filter(ativo=True, removido_em__isnull=True)

    def removidos(self) -> SoftDeleteQuerySet:
        return self.filter(removido_em__isnull=False)


class SoftDeleteManager(models.Manager):
    """Manager padrão que expõe apenas registros ativos."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).ativos()


class SoftDeleteModel(models.Model):
    """Adiciona exclusão lógica para entidades de domínio."""

    ativo = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='ativo',
    )
    removido_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='removido em',
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(
        self,
        using: str | None = None,
        keep_parents: bool = False,
    ) -> tuple[int, dict[str, int]]:
        self.ativo = False
        self.removido_em = timezone.now()
        self.save(
            using=using,
            update_fields=['ativo', 'removido_em', 'atualizado_em'],
        )
        return 1, {self._meta.label: 1}

    def hard_delete(
        self,
        using: str | None = None,
        keep_parents: bool = False,
    ) -> tuple[int, dict[str, int]]:
        return super().delete(using=using, keep_parents=keep_parents)


class ConfiguracaoSistema(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Configurações chave/valor controladas pelo sistema."""

    id = models.BigAutoField(
        primary_key=True,
        db_column='core_configuracao_sistema_id',
    )
    chave = models.CharField(max_length=120, unique=True, verbose_name='chave')
    valor = models.TextField(blank=True, verbose_name='valor')
    descricao = models.TextField(blank=True, verbose_name='descrição')

    class Meta:
        ordering = ['chave']
        verbose_name = 'configuração do sistema'
        verbose_name_plural = 'configurações do sistema'
        db_table = '"core"."core_configuracao_sistema_tb"'
        indexes = [
            models.Index(fields=['chave'], name='core_config_sistema_chave_idx'),
            models.Index(fields=['ativo'], name='core_config_sistema_ativo_idx'),
        ]

    def __str__(self) -> str:
        return self.chave


class ContatoInstitucional(UUIDModel):
    """Contato ou rede social oficial do BOTUKA."""

    class Tipo(models.TextChoices):
        TELEFONE = 'TELEFONE', 'Telefone'
        WHATSAPP = 'WHATSAPP', 'WhatsApp'
        EMAIL = 'EMAIL', 'E-mail'
        FACEBOOK = 'FACEBOOK', 'Facebook'
        INSTAGRAM = 'INSTAGRAM', 'Instagram'
        LINKEDIN = 'LINKEDIN', 'LinkedIn'
        YOUTUBE = 'YOUTUBE', 'YouTube'
        TIKTOK = 'TIKTOK', 'TikTok'
        X = 'X', 'X'
        OUTRO = 'OUTRO', 'Outro'

    id = models.BigAutoField(
        primary_key=True,
        db_column='core_contato_institucional_id',
    )
    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        db_column='core_contato_institucional_tipo',
        verbose_name='tipo',
    )
    nome = models.CharField(
        max_length=120,
        db_column='core_contato_institucional_nome',
        verbose_name='nome',
    )
    valor = models.CharField(
        max_length=180,
        db_column='core_contato_institucional_valor',
        verbose_name='valor',
    )
    url = models.URLField(
        blank=True,
        db_column='core_contato_institucional_url',
        verbose_name='URL',
    )
    icone = models.CharField(
        max_length=80,
        blank=True,
        db_column='core_contato_institucional_icone',
        verbose_name='ícone',
    )
    ordem = models.PositiveIntegerField(
        default=0,
        db_column='core_contato_institucional_ordem',
        verbose_name='ordem',
    )
    ativo = models.BooleanField(
        default=True,
        db_index=True,
        db_column='core_contato_institucional_ativo',
        verbose_name='ativo',
    )
    exibir_topbar = models.BooleanField(
        default=True,
        db_column='core_contato_institucional_exibir_topbar',
        verbose_name='exibir na topbar',
    )
    exibir_rodape = models.BooleanField(
        default=True,
        db_column='core_contato_institucional_exibir_rodape',
        verbose_name='exibir no rodapé',
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        db_column='core_contato_institucional_criado_em',
        verbose_name='criado em',
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        db_column='core_contato_institucional_atualizado_em',
        verbose_name='atualizado em',
    )

    class Meta:
        ordering = ['ordem', 'nome']
        verbose_name = 'contato institucional'
        verbose_name_plural = 'contatos institucionais'
        db_table = '"core"."core_contato_institucional_tb"'
        indexes = [
            models.Index(fields=['tipo'], name='core_contato_tipo_idx'),
            models.Index(fields=['ativo'], name='core_contato_ativo_idx'),
            models.Index(fields=['ordem'], name='core_contato_ordem_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.nome} ({self.get_tipo_display()})'

    @property
    def link(self) -> str:
        """Retorna link clicável adequado ao tipo de contato."""

        if self.url:
            return self.url

        valor_limpo = ''.join(char for char in self.valor if char.isdigit())

        if self.tipo == self.Tipo.TELEFONE:
            return f'tel:+55{valor_limpo}' if not valor_limpo.startswith('55') else f'tel:+{valor_limpo}'

        if self.tipo == self.Tipo.WHATSAPP:
            return f'https://wa.me/55{valor_limpo}' if not valor_limpo.startswith('55') else f'https://wa.me/{valor_limpo}'

        if self.tipo == self.Tipo.EMAIL:
            return f'mailto:{self.valor}'

        return self.valor


class Perfil(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Perfil corporativo para agrupamento de permissões."""

    id = models.BigAutoField(primary_key=True, db_column='core_perfil_id')
    nome = models.CharField(max_length=120, unique=True, verbose_name='nome')
    descricao = models.TextField(blank=True, verbose_name='descrição')

    class Meta:
        ordering = ['nome']
        verbose_name = 'perfil'
        verbose_name_plural = 'perfis'
        db_table = '"core"."core_perfil_tb"'
        indexes = [
            models.Index(fields=['nome'], name='core_perfil_nome_idx'),
            models.Index(fields=['ativo'], name='core_perfil_ativo_idx'),
        ]

    def __str__(self) -> str:
        return self.nome


class Permissao(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Permissão granular da plataforma."""

    class Criticidade(models.IntegerChoices):
        BASICA = 10, 'Básica'
        OPERACIONAL = 20, 'Operacional'
        MODERACAO = 30, 'Moderação'
        ADMINISTRATIVA = 40, 'Administrativa'
        PROTEGIDA = 50, 'Protegida'

    id = models.BigAutoField(primary_key=True, db_column='core_permissao_id')
    modulo = models.CharField(max_length=60, blank=True, db_index=True, verbose_name='módulo')
    grupo = models.CharField(max_length=80, blank=True, db_index=True, verbose_name='grupo')
    codigo = models.CharField(
        max_length=120,
        unique=True,
        verbose_name='código',
    )
    nome = models.CharField(max_length=120, verbose_name='nome')
    descricao = models.TextField(blank=True, verbose_name='descrição')
    criticidade = models.PositiveSmallIntegerField(
        choices=Criticidade.choices, default=Criticidade.BASICA,
        verbose_name='criticidade',
    )
    protegida = models.BooleanField(default=False, verbose_name='protegida')

    class Meta:
        ordering = ['codigo']
        verbose_name = 'permissão'
        verbose_name_plural = 'permissões'
        db_table = '"core"."core_permissao_tb"'
        indexes = [
            models.Index(fields=['codigo'], name='core_permissao_codigo_idx'),
            models.Index(fields=['ativo'], name='core_permissao_ativo_idx'),
        ]

    def __str__(self) -> str:
        return self.nome


class PerfilPermissao(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Relaciona perfis corporativos a permissões."""

    id = models.BigAutoField(
        primary_key=True,
        db_column='core_perfil_permissao_id',
    )
    perfil = models.ForeignKey(
        Perfil,
        on_delete=models.CASCADE,
        db_column='core_perfil_fk',
        related_name='perfil_permissoes',
        verbose_name='perfil',
    )
    permissao = models.ForeignKey(
        Permissao,
        on_delete=models.CASCADE,
        db_column='core_permissao_fk',
        related_name='perfil_permissoes',
        verbose_name='permissão',
    )

    class Meta:
        ordering = ['perfil__nome', 'permissao__codigo']
        verbose_name = 'permissão do perfil'
        verbose_name_plural = 'permissões dos perfis'
        db_table = '"core"."core_perfil_permissao_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['perfil', 'permissao'],
                name='core_perfil_permissao_uk',
            ),
        ]
        indexes = [
            models.Index(
                fields=['perfil', 'permissao'],
                name='core_perfil_permissao_idx',
            ),
            models.Index(fields=['ativo'], name='core_perfil_perm_ativo_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.perfil} - {self.permissao}'


def somente_digitos(valor: str | None) -> str:
    return ''.join(char for char in str(valor or '') if char.isdigit())


def mascarar_documento(valor: str | None) -> str:
    documento = somente_digitos(valor)
    if len(documento) == 11:
        return f'{documento[:3]}.***.***-{documento[-2:]}'
    if len(documento) == 14:
        return f'{documento[:2]}.***.***/****-{documento[-2:]}'
    if len(documento) > 4:
        return f'***{documento[-4:]}'
    return documento


class EstadoBrasil(UUIDModel):
    class RegiaoBrasileira(models.TextChoices):
        NORTE = 'NORTE', 'Norte'
        NORDESTE = 'NORDESTE', 'Nordeste'
        CENTRO_OESTE = 'CENTRO_OESTE', 'Centro-Oeste'
        SUDESTE = 'SUDESTE', 'Sudeste'
        SUL = 'SUL', 'Sul'

    id = models.BigAutoField(primary_key=True, db_column='core_estado_id')
    codigo_ibge = models.CharField(max_length=2, blank=True, db_column='core_estado_codigo_ibge')
    nome = models.CharField(max_length=100, db_column='core_estado_nome')
    sigla = models.CharField(max_length=2, unique=True, db_column='core_estado_sigla')
    regiao_brasileira = models.CharField(
        max_length=20,
        choices=RegiaoBrasileira.choices,
        db_column='core_estado_regiao_brasileira',
    )
    ativo = models.BooleanField(default=True, db_column='core_estado_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='core_estado_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='core_estado_atualizado_em')

    class Meta:
        ordering = ['nome']
        verbose_name = 'estado brasileiro'
        verbose_name_plural = 'estados brasileiros'
        db_table = '"core"."core_estado_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['codigo_ibge'],
                condition=~models.Q(codigo_ibge=''),
                name='core_estado_codigo_ibge_uk',
            ),
        ]
        indexes = [
            models.Index(fields=['sigla'], name='core_estado_idx_sigla'),
            models.Index(fields=['ativo'], name='core_estado_idx_ativo'),
        ]

    def __str__(self) -> str:
        return f'{self.nome}/{self.sigla}'


class CidadeBrasil(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='core_cidade_id')
    estado = models.ForeignKey(
        EstadoBrasil,
        on_delete=models.PROTECT,
        db_column='core_cidade_fk_estado',
        related_name='cidades_core',
    )
    codigo_ibge = models.CharField(max_length=7, blank=True, db_column='core_cidade_codigo_ibge')
    nome = models.CharField(max_length=120, db_column='core_cidade_nome')
    slug = models.SlugField(max_length=180, db_column='core_cidade_slug')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_column='core_cidade_latitude')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_column='core_cidade_longitude')
    capital = models.BooleanField(default=False, db_column='core_cidade_capital')
    ativo = models.BooleanField(default=True, db_column='core_cidade_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='core_cidade_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='core_cidade_atualizado_em')

    class Meta:
        ordering = ['estado__sigla', 'nome']
        verbose_name = 'cidade brasileira'
        verbose_name_plural = 'cidades brasileiras'
        db_table = '"core"."core_cidade_tb"'
        constraints = [
            models.UniqueConstraint(fields=['estado', 'nome'], name='core_cidade_estado_nome_uk'),
            models.UniqueConstraint(
                fields=['codigo_ibge'],
                condition=~models.Q(codigo_ibge=''),
                name='core_cidade_codigo_ibge_uk',
            ),
        ]
        indexes = [
            models.Index(fields=['estado', 'nome'], name='core_cidade_idx_nome'),
            models.Index(fields=['slug'], name='core_cidade_idx_slug'),
            models.Index(fields=['ativo'], name='core_cidade_idx_ativo'),
        ]

    def __str__(self) -> str:
        return f'{self.nome}/{self.estado.sigla}'


class RegiaoCidade(UUIDModel):
    class Tipo(models.TextChoices):
        ADMINISTRATIVA = 'ADMINISTRATIVA', 'Administrativa'
        COMERCIAL = 'COMERCIAL', 'Comercial'
        OPERACIONAL = 'OPERACIONAL', 'Operacional'
        TURISTICA = 'TURISTICA', 'Turística'
        MOBILIDADE = 'MOBILIDADE', 'Mobilidade'
        ATENDIMENTO = 'ATENDIMENTO', 'Atendimento'

    id = models.BigAutoField(primary_key=True, db_column='core_regiao_id')
    cidade = models.ForeignKey(CidadeBrasil, on_delete=models.CASCADE, db_column='core_regiao_fk_cidade', related_name='regioes')
    nome = models.CharField(max_length=120, db_column='core_regiao_nome')
    tipo = models.CharField(max_length=20, choices=Tipo.choices, db_column='core_regiao_tipo')
    descricao = models.TextField(blank=True, db_column='core_regiao_descricao')
    ativo = models.BooleanField(default=True, db_column='core_regiao_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='core_regiao_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='core_regiao_atualizado_em')

    class Meta:
        ordering = ['cidade__nome', 'nome']
        db_table = '"core"."core_regiao_tb"'
        constraints = [models.UniqueConstraint(fields=['cidade', 'nome'], name='core_regiao_cidade_nome_uk')]
        indexes = [models.Index(fields=['cidade', 'tipo'], name='core_regiao_idx_tipo')]

    def __str__(self) -> str:
        return f'{self.nome} - {self.cidade}'


class ZonaCidade(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='core_zona_id')
    cidade = models.ForeignKey(CidadeBrasil, on_delete=models.CASCADE, db_column='core_zona_fk_cidade', related_name='zonas')
    nome = models.CharField(max_length=120, db_column='core_zona_nome')
    descricao = models.TextField(blank=True, db_column='core_zona_descricao')
    ativo = models.BooleanField(default=True, db_column='core_zona_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='core_zona_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='core_zona_atualizado_em')

    class Meta:
        ordering = ['cidade__nome', 'nome']
        db_table = '"core"."core_zona_tb"'
        constraints = [models.UniqueConstraint(fields=['cidade', 'nome'], name='core_zona_cidade_nome_uk')]

    def __str__(self) -> str:
        return f'{self.nome} - {self.cidade}'


class BairroCidade(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='core_bairro_id')
    cidade = models.ForeignKey(CidadeBrasil, on_delete=models.CASCADE, db_column='core_bairro_fk_cidade', related_name='bairros_core')
    zona = models.ForeignKey(ZonaCidade, on_delete=models.SET_NULL, null=True, blank=True, db_column='core_bairro_fk_zona', related_name='bairros')
    nome = models.CharField(max_length=120, db_column='core_bairro_nome')
    slug = models.SlugField(max_length=180, db_column='core_bairro_slug')
    codigo_oficial = models.CharField(max_length=30, blank=True, db_column='core_bairro_codigo_oficial')
    ativo = models.BooleanField(default=True, db_column='core_bairro_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='core_bairro_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='core_bairro_atualizado_em')

    class Meta:
        ordering = ['cidade__nome', 'nome']
        db_table = '"core"."core_bairro_tb"'
        constraints = [models.UniqueConstraint(fields=['cidade', 'nome'], name='core_bairro_cidade_nome_uk')]
        indexes = [models.Index(fields=['cidade', 'slug'], name='core_bairro_idx_slug')]

    def __str__(self) -> str:
        return f'{self.nome} - {self.cidade}'


class EnderecoCore(UUIDModel):
    class TipoEndereco(models.TextChoices):
        RESIDENCIAL = 'RESIDENCIAL', 'Residencial'
        COMERCIAL = 'COMERCIAL', 'Comercial'
        ENTREGA = 'ENTREGA', 'Entrega'
        COBRANCA = 'COBRANCA', 'Cobrança'
        ATENDIMENTO = 'ATENDIMENTO', 'Atendimento'
        OUTRO = 'OUTRO', 'Outro'

    id = models.BigAutoField(primary_key=True, db_column='core_endereco_id')
    tipo_endereco = models.CharField(max_length=20, choices=TipoEndereco.choices, default=TipoEndereco.OUTRO, db_column='core_endereco_tipo_endereco')
    cep = models.CharField(max_length=8, blank=True, db_column='core_endereco_cep')
    logradouro = models.CharField(max_length=180, db_column='core_endereco_logradouro')
    numero = models.CharField(max_length=20, blank=True, db_column='core_endereco_numero')
    complemento = models.CharField(max_length=120, blank=True, db_column='core_endereco_complemento')
    bairro = models.ForeignKey(BairroCidade, on_delete=models.SET_NULL, null=True, blank=True, db_column='core_endereco_fk_bairro', related_name='enderecos')
    bairro_texto = models.CharField(max_length=120, blank=True, db_column='core_endereco_bairro_texto')
    cidade = models.ForeignKey(CidadeBrasil, on_delete=models.PROTECT, db_column='core_endereco_fk_cidade', related_name='enderecos_core')
    estado = models.ForeignKey(EstadoBrasil, on_delete=models.PROTECT, db_column='core_endereco_fk_estado', related_name='enderecos_core')
    referencia = models.CharField(max_length=180, blank=True, db_column='core_endereco_referencia')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_column='core_endereco_latitude')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_column='core_endereco_longitude')
    principal = models.BooleanField(default=False, db_column='core_endereco_principal')
    validado = models.BooleanField(default=False, db_column='core_endereco_validado')
    origem_dados = models.CharField(max_length=40, blank=True, db_column='core_endereco_origem_dados')
    ativo = models.BooleanField(default=True, db_column='core_endereco_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='core_endereco_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='core_endereco_atualizado_em')
    excluido_em = models.DateTimeField(null=True, blank=True, db_column='core_endereco_excluido_em')

    class Meta:
        ordering = ['cidade__nome', 'logradouro', 'numero']
        db_table = '"core"."core_endereco_tb"'
        indexes = [
            models.Index(fields=['cep'], name='core_endereco_idx_cep'),
            models.Index(fields=['cidade'], name='core_endereco_idx_cidade'),
            models.Index(fields=['ativo'], name='core_endereco_idx_ativo'),
        ]

    def save(self, *args, **kwargs) -> None:
        self.cep = somente_digitos(self.cep)
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        self.ativo = False
        self.excluido_em = timezone.now()
        self.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])
        return 1, {self._meta.label: 1}

    def __str__(self) -> str:
        numero = f', {self.numero}' if self.numero else ''
        return f'{self.logradouro}{numero} - {self.cidade}'


class UsuarioEndereco(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='core_usuario_endereco_id')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='core_usuario_endereco_fk_usuario', related_name='enderecos_vinculados')
    endereco = models.ForeignKey(EnderecoCore, on_delete=models.CASCADE, db_column='core_usuario_endereco_fk_endereco', related_name='usuarios_vinculados')
    principal = models.BooleanField(default=False, db_column='core_usuario_endereco_principal')
    ativo = models.BooleanField(default=True, db_column='core_usuario_endereco_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='core_usuario_endereco_criado_em')

    class Meta:
        db_table = '"core"."core_usuario_endereco_tb"'
        constraints = [models.UniqueConstraint(fields=['usuario', 'endereco'], name='core_usuario_endereco_uk')]


class TipoDocumento(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='core_tipo_documento_id')
    codigo = models.CharField(max_length=40, unique=True, db_column='core_tipo_documento_codigo')
    nome = models.CharField(max_length=120, db_column='core_tipo_documento_nome')
    descricao = models.TextField(blank=True, db_column='core_tipo_documento_descricao')
    pessoa_fisica = models.BooleanField(default=True, db_column='core_tipo_documento_pessoa_fisica')
    pessoa_juridica = models.BooleanField(default=False, db_column='core_tipo_documento_pessoa_juridica')
    possui_validade = models.BooleanField(default=False, db_column='core_tipo_documento_possui_validade')
    exige_frente = models.BooleanField(default=False, db_column='core_tipo_documento_exige_frente')
    exige_verso = models.BooleanField(default=False, db_column='core_tipo_documento_exige_verso')
    permite_arquivo_unico = models.BooleanField(default=True, db_column='core_tipo_documento_permite_arquivo_unico')
    sensivel = models.BooleanField(default=True, db_column='core_tipo_documento_sensivel')
    ativo = models.BooleanField(default=True, db_column='core_tipo_documento_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='core_tipo_documento_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='core_tipo_documento_atualizado_em')

    class Meta:
        ordering = ['nome']
        db_table = '"core"."core_tipo_documento_tb"'
        indexes = [models.Index(fields=['codigo'], name='core_tipo_doc_idx_codigo')]

    def __str__(self) -> str:
        return self.nome


class PessoaDocumento(UUIDModel):
    class StatusValidacao(models.TextChoices):
        NAO_ENVIADO = 'NAO_ENVIADO', 'Não enviado'
        PENDENTE = 'PENDENTE', 'Pendente'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        APROVADO = 'APROVADO', 'Aprovado'
        REJEITADO = 'REJEITADO', 'Rejeitado'
        EXPIRADO = 'EXPIRADO', 'Expirado'

    id = models.BigAutoField(primary_key=True, db_column='core_pessoa_documento_id')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='core_pessoa_documento_fk_usuario', related_name='documentos_pessoais')
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.PROTECT, db_column='core_pessoa_documento_fk_tipo', related_name='documentos')
    numero_normalizado = models.CharField(max_length=40, blank=True, db_column='core_pessoa_documento_numero_normalizado')
    nome_documento = models.CharField(max_length=120, blank=True, db_column='core_pessoa_documento_nome_documento')
    orgao_emissor = models.CharField(max_length=40, blank=True, db_column='core_pessoa_documento_orgao_emissor')
    uf_emissao = models.CharField(max_length=2, blank=True, db_column='core_pessoa_documento_uf_emissao')
    data_emissao = models.DateField(null=True, blank=True, db_column='core_pessoa_documento_data_emissao')
    data_validade = models.DateField(null=True, blank=True, db_column='core_pessoa_documento_data_validade')
    arquivo_frente = models.FileField(upload_to='documentos/pessoas/frente/%Y/%m/', blank=True, db_column='core_pessoa_documento_arquivo_frente')
    arquivo_verso = models.FileField(upload_to='documentos/pessoas/verso/%Y/%m/', blank=True, db_column='core_pessoa_documento_arquivo_verso')
    arquivo_unico = models.FileField(upload_to='documentos/pessoas/unico/%Y/%m/', blank=True, db_column='core_pessoa_documento_arquivo_unico')
    status_validacao = models.CharField(max_length=20, choices=StatusValidacao.choices, default=StatusValidacao.NAO_ENVIADO, db_column='core_pessoa_documento_status_validacao')
    validado_em = models.DateTimeField(null=True, blank=True, db_column='core_pessoa_documento_validado_em')
    validado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, db_column='core_pessoa_documento_fk_validado_por', related_name='documentos_validados')
    motivo_rejeicao = models.TextField(blank=True, db_column='core_pessoa_documento_motivo_rejeicao')
    principal = models.BooleanField(default=False, db_column='core_pessoa_documento_principal')
    ativo = models.BooleanField(default=True, db_column='core_pessoa_documento_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='core_pessoa_documento_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='core_pessoa_documento_atualizado_em')
    excluido_em = models.DateTimeField(null=True, blank=True, db_column='core_pessoa_documento_excluido_em')

    class Meta:
        ordering = ['usuario', 'tipo_documento__nome']
        db_table = '"core"."core_pessoa_documento_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['tipo_documento', 'numero_normalizado'],
                condition=~models.Q(numero_normalizado=''),
                name='core_pessoa_doc_tipo_numero_uk',
            ),
        ]

    def save(self, *args, **kwargs) -> None:
        self.numero_normalizado = somente_digitos(self.numero_normalizado)
        super().save(*args, **kwargs)

    @property
    def numero_mascarado(self) -> str:
        return mascarar_documento(self.numero_normalizado)


class DocumentoRequisito(UUIDModel):
    class Contexto(models.TextChoices):
        CADASTRO_PF = 'CADASTRO_PF', 'Cadastro PF'
        VENDA_PRODUTO = 'VENDA_PRODUTO', 'Venda de produto'
        PRESTACAO_SERVICO = 'PRESTACAO_SERVICO', 'Prestação de serviço'
        PROPRIETARIO_EMPRESA = 'PROPRIETARIO_EMPRESA', 'Proprietário de empresa'
        VENDEDOR = 'VENDEDOR', 'Vendedor'
        MOTORISTA = 'MOTORISTA', 'Motorista'
        EMISSAO_FISCAL = 'EMISSAO_FISCAL', 'Emissão fiscal'

    id = models.BigAutoField(primary_key=True, db_column='core_documento_requisito_id')
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.CASCADE, db_column='core_documento_requisito_fk_tipo', related_name='requisitos')
    contexto = models.CharField(max_length=40, choices=Contexto.choices, db_column='core_documento_requisito_contexto')
    modulo = models.CharField(max_length=60, db_column='core_documento_requisito_modulo')
    obrigatorio = models.BooleanField(default=False, db_column='core_documento_requisito_obrigatorio')
    condicional = models.BooleanField(default=False, db_column='core_documento_requisito_condicional')
    regra_json = models.JSONField(default=dict, blank=True, db_column='core_documento_requisito_regra_json')
    ativo = models.BooleanField(default=True, db_column='core_documento_requisito_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='core_documento_requisito_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='core_documento_requisito_atualizado_em')

    class Meta:
        db_table = '"core"."core_documento_requisito_tb"'
        constraints = [models.UniqueConstraint(fields=['tipo_documento', 'contexto', 'modulo'], name='core_doc_req_tipo_contexto_uk')]


class CNHDetalhe(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='core_cnh_detalhe_id')
    documento = models.OneToOneField(PessoaDocumento, on_delete=models.CASCADE, db_column='core_cnh_detalhe_fk_documento', related_name='cnh_detalhe')
    numero_registro = models.CharField(max_length=30, db_column='core_cnh_detalhe_numero_registro')
    categoria = models.CharField(max_length=5, db_column='core_cnh_detalhe_categoria')
    possui_ear = models.BooleanField(default=False, db_column='core_cnh_detalhe_possui_ear')
    primeira_habilitacao = models.DateField(null=True, blank=True, db_column='core_cnh_detalhe_primeira_habilitacao')
    validade = models.DateField(null=True, blank=True, db_column='core_cnh_detalhe_validade')
    ativo = models.BooleanField(default=True, db_column='core_cnh_detalhe_ativo')

    class Meta:
        db_table = '"core"."core_cnh_detalhe_tb"'


class Auditoria(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='core_auditoria_id')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, db_column='core_auditoria_fk_usuario', related_name='auditorias')
    acao = models.CharField(max_length=80, db_column='core_auditoria_acao')
    entidade = models.CharField(max_length=120, db_column='core_auditoria_entidade')
    registro_id = models.CharField(max_length=60, blank=True, db_column='core_auditoria_registro_id')
    dados_antes_json = models.JSONField(default=dict, blank=True, db_column='core_auditoria_dados_antes_json')
    dados_depois_json = models.JSONField(default=dict, blank=True, db_column='core_auditoria_dados_depois_json')
    motivo = models.TextField(blank=True, db_column='core_auditoria_motivo')
    ip = models.GenericIPAddressField(null=True, blank=True, db_column='core_auditoria_ip')
    user_agent = models.TextField(blank=True, db_column='core_auditoria_user_agent')
    organizacao_uuid = models.UUIDField(null=True, blank=True, db_column='core_auditoria_organizacao_uuid')
    sucesso = models.BooleanField(default=True, db_column='core_auditoria_sucesso')
    origem = models.CharField(max_length=40, default='SISTEMA', db_column='core_auditoria_origem')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='core_auditoria_criado_em')

    class Meta:
        ordering = ['-criado_em']
        db_table = '"core"."core_auditoria_tb"'
        indexes = [
            models.Index(fields=['acao'], name='core_auditoria_idx_acao'),
            models.Index(fields=['entidade', 'registro_id'], name='core_auditoria_idx_registro'),
        ]
