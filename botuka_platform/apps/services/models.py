from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Avg, Count
from django.utils import timezone

from apps.core.models import BairroCidade, CidadeBrasil, EstadoBrasil, RegiaoCidade, UUIDModel
from apps.core.public_links import TipoLink, normalizar_link_publico, url_embed_youtube
from apps.core.utils import gerar_slug_unico
from apps.core.services.rich_text import sanitizar_html_rico
from apps.organizations.models import Empresa


class ServicoQuerySet(models.QuerySet):
    def ativos(self):
        return self.filter(ativo=True, excluido_em__isnull=True)

    def delete(self):
        updated = self.update(ativo=False, excluido_em=timezone.now())
        return updated, {self.model._meta.label: updated}


class ServicoManager(models.Manager):
    def get_queryset(self):
        return ServicoQuerySet(self.model, using=self._db).ativos()


class Setor(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_setor_id')
    nome = models.CharField(max_length=120, unique=True, db_column='services_setor_nome')
    slug = models.SlugField(max_length=160, unique=True, blank=True, db_column='services_setor_slug')
    descricao = models.TextField(blank=True, db_column='services_setor_descricao')
    icone = models.CharField(max_length=80, blank=True, db_column='services_setor_icone')
    ordem = models.PositiveIntegerField(default=0, db_column='services_setor_ordem')
    ativo = models.BooleanField(default=True, db_column='services_setor_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_setor_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_setor_atualizado_em')

    class Meta:
        ordering = ['ordem', 'nome']
        db_table = '"services"."services_setor_tb"'
        indexes = [models.Index(fields=['slug'], name='services_setor_idx_slug')]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class AreaProfissional(UUIDModel):
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
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.nome} ({self.setor})'


class Profissao(UUIDModel):
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
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_profissao_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_profissao_atualizado_em')

    class Meta:
        ordering = ['setor__nome', 'nome']
        db_table = '"services"."services_profissao_tb"'
        constraints = [models.UniqueConstraint(fields=['setor', 'nome'], name='services_profissao_setor_nome_uk')]
        indexes = [models.Index(fields=['setor', 'slug'], name='services_profissao_idx_slug')]

    def save(self, *args, **kwargs):
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


class TipoServico(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='services_tipo_servico_id')
    nome = models.CharField(max_length=120, unique=True, db_column='services_tipo_servico_nome')
    slug = models.SlugField(max_length=160, unique=True, blank=True, db_column='services_tipo_servico_slug')
    descricao = models.TextField(blank=True, db_column='services_tipo_servico_descricao')
    ativo = models.BooleanField(default=True, db_column='services_tipo_servico_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='services_tipo_servico_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='services_tipo_servico_atualizado_em')
    profissoes = models.ManyToManyField(
        Profissao, through='ProfissaoTipoServico', related_name='tipos_servico', blank=True,
    )

    class Meta:
        ordering = ['nome']
        db_table = '"services"."services_tipo_servico_tb"'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class ProfissaoTipoServico(UUIDModel):
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
    setor = models.ForeignKey(Setor, on_delete=models.PROTECT, db_column='services_servico_fk_setor', related_name='servicos')
    area = models.ForeignKey(
        AreaProfissional,
        on_delete=models.PROTECT,
        db_column='services_servico_fk_area',
        related_name='servicos',
        null=True,
        blank=True,
    )
    profissao = models.ForeignKey(Profissao, on_delete=models.PROTECT, db_column='services_servico_fk_profissao', related_name='servicos')
    tipo_servico = models.ForeignKey(
        TipoServico,
        on_delete=models.PROTECT,
        db_column='services_servico_fk_tipo_servico',
        related_name='servicos',
        null=True,
        blank=True,
    )
    forma_cobranca = models.ForeignKey(FormaCobranca, on_delete=models.PROTECT, db_column='services_servico_fk_forma_cobranca', related_name='servicos')
    titulo = models.CharField(max_length=160, db_column='services_servico_titulo')
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
        self.descricao_completa = sanitizar_html_rico(self.descricao_completa)
        self.experiencia = sanitizar_html_rico(self.experiencia)
        if self.prestador_tipo == self.PrestadorTipo.EMPRESA and not self.empresa_id:
            raise ValidationError({'empresa': 'Informe a empresa prestadora.'})
        if self.prestador_tipo == self.PrestadorTipo.PESSOA_FISICA and self.empresa_id:
            raise ValidationError({'empresa': 'Pessoa física não deve ter empresa vinculada.'})
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
            and ProfissaoTipoServico.objects.filter(
                profissao_id=self.profissao_id,
                ativo=True,
            ).exists()
            and not ProfissaoTipoServico.objects.filter(
                profissao_id=self.profissao_id,
                tipo_servico_id=self.tipo_servico_id,
                ativo=True,
                tipo_servico__ativo=True,
            ).exists()
        ):
            raise ValidationError({'tipo_servico': 'O tipo de serviço não pertence à profissão selecionada.'})
        if self.preco_inicial and self.preco_final and self.preco_inicial > self.preco_final:
            raise ValidationError({'preco_final': 'O preço final não pode ser menor que o inicial.'})
        if not self.atendimento_remoto and not self.atendimento_presencial:
            raise ValidationError('Informe ao menos atendimento remoto ou presencial.')
        if self.status == self.Status.PUBLICADO and self.empresa_id and not self.empresa.pode_publicar_servico:
            raise ValidationError('Empresa não está apta a publicar serviços.')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.titulo)
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
