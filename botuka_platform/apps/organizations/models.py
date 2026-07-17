"""Modelos de organizações, unidades e endereços."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import SoftDeleteModel, TimeStampedModel, UUIDModel
from apps.core.models import EnderecoCore
from apps.core.public_links import TipoLink, normalizar_link_publico, url_embed_youtube
from apps.core.utils import gerar_slug_unico
from apps.locations.models import Bairro, Cidade, Estado
from apps.taxonomy.models import Categoria


def normalizar_digitos(valor: str | None) -> str:
    """Retorna apenas os dígitos de um valor textual."""

    return ''.join(char for char in str(valor or '') if char.isdigit())


def formatar_documento(valor: str | None) -> str:
    """Formata CPF ou CNPJ para exibição."""

    documento = normalizar_digitos(valor)

    if len(documento) == 11:
        return (
            f'{documento[:3]}.{documento[3:6]}.'
            f'{documento[6:9]}-{documento[9:]}'
        )

    if len(documento) == 14:
        return (
            f'{documento[:2]}.{documento[2:5]}.{documento[5:8]}/'
            f'{documento[8:12]}-{documento[12:]}'
        )

    return documento


class EmpresaQuerySet(models.QuerySet):
    """QuerySet com operações reutilizáveis de empresa."""

    def ativas(self) -> EmpresaQuerySet:
        return self.filter(ativo=True, excluido_em__isnull=True)

    def delete(self) -> tuple[int, dict[str, int]]:
        updated = self.update(ativo=False, excluido_em=timezone.now())
        return updated, {self.model._meta.label: updated}

    def hard_delete(self) -> tuple[int, dict[str, int]]:
        return super().delete()


class EmpresaManager(models.Manager):
    """Manager padrão que expõe apenas empresas não excluídas."""

    def get_queryset(self) -> EmpresaQuerySet:
        return EmpresaQuerySet(self.model, using=self._db).ativas()


class Empresa(UUIDModel):
    """Empresa, negócio informal, MEI ou atuação autônoma do usuário."""

    class TipoCadastro(models.TextChoices):
        AUTONOMO = 'AUTONOMO', 'Autônomo'
        INFORMAL = 'INFORMAL', 'Informal'
        MEI = 'MEI', 'MEI'
        EMPRESA = 'EMPRESA', 'Empresa'
        ORGANIZACAO = 'ORGANIZACAO', 'Organização'

    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        PENDENTE = 'PENDENTE', 'Pendente'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        ATIVA = 'ATIVA', 'Ativa'
        REJEITADA = 'REJEITADA', 'Rejeitada'
        SUSPENSA = 'SUSPENSA', 'Suspensa'
        BLOQUEADA = 'BLOQUEADA', 'Bloqueada'

    class CanalLead(models.TextChoices):
        WHATSAPP = 'WHATSAPP', 'WhatsApp'
        EMAIL = 'EMAIL', 'E-mail'
        TELEFONE = 'TELEFONE', 'Telefone'
        PAINEL = 'PAINEL', 'Painel'

    class DistribuicaoLead(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual'
        AUTOMATICA = 'AUTOMATICA', 'Automática'

    id = models.BigAutoField(
        primary_key=True,
        db_column='platform_empresa_id',
    )
    usuario_proprietario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column='platform_empresa_usuario_proprietario_fk',
        related_name='empresas_proprietario_platform',
        verbose_name='usuário proprietário',
    )
    tipo_cadastro = models.CharField(
        max_length=20,
        choices=TipoCadastro.choices,
        default=TipoCadastro.INFORMAL,
        db_column='platform_empresa_tipo_cadastro',
        verbose_name='tipo de cadastro',
    )
    razao_social = models.CharField(
        max_length=180,
        blank=True,
        db_column='platform_empresa_razao_social',
        verbose_name='razão social',
    )
    nome_fantasia = models.CharField(
        max_length=180,
        db_column='platform_empresa_nome_fantasia',
        verbose_name='nome fantasia',
    )
    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        db_column='platform_empresa_slug',
        verbose_name='slug',
    )
    cpf_cnpj = models.CharField(
        max_length=14,
        blank=True,
        db_column='platform_empresa_cpf_cnpj',
        verbose_name='CPF/CNPJ',
        help_text='Documento armazenado somente com números.',
    )
    inscricao_estadual = models.CharField(
        max_length=30,
        blank=True,
        db_column='platform_empresa_inscricao_estadual',
        verbose_name='inscrição estadual',
    )
    inscricao_municipal = models.CharField(
        max_length=30,
        blank=True,
        db_column='platform_empresa_inscricao_municipal',
        verbose_name='inscrição municipal',
    )
    natureza_juridica = models.CharField(
        max_length=120,
        blank=True,
        db_column='platform_empresa_natureza_juridica',
        verbose_name='natureza jurídica',
    )
    porte = models.CharField(
        max_length=40,
        blank=True,
        db_column='platform_empresa_porte',
        verbose_name='porte',
    )
    data_abertura = models.DateField(
        null=True,
        blank=True,
        db_column='platform_empresa_data_abertura',
        verbose_name='data de abertura',
    )
    situacao_cadastral = models.CharField(
        max_length=60,
        blank=True,
        db_column='platform_empresa_situacao_cadastral',
        verbose_name='situação cadastral',
    )
    categoria_empresa = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='platform_empresa_categoria_empresa_fk',
        related_name='empresas',
        verbose_name='categoria da empresa',
    )
    descricao_curta = models.CharField(
        max_length=220,
        blank=True,
        db_column='platform_empresa_descricao_curta',
        verbose_name='descrição curta',
    )
    descricao_completa = models.TextField(
        blank=True,
        db_column='platform_empresa_descricao_completa',
        verbose_name='descrição completa',
    )
    telefone = models.CharField(
        max_length=20,
        blank=True,
        db_column='platform_empresa_telefone',
        verbose_name='telefone',
    )
    whatsapp = models.CharField(
        max_length=20,
        blank=True,
        db_column='platform_empresa_whatsapp',
        verbose_name='WhatsApp',
    )
    email = models.EmailField(
        blank=True,
        db_column='platform_empresa_email',
        verbose_name='e-mail',
    )
    site = models.URLField(
        blank=True,
        db_column='platform_empresa_site',
        verbose_name='site',
    )
    logo = models.ImageField(
        upload_to='empresas/logos/',
        blank=True,
        db_column='platform_empresa_logo',
        verbose_name='logo',
    )
    imagem_capa = models.ImageField(
        upload_to='empresas/capas/',
        blank=True,
        db_column='platform_empresa_imagem_capa',
        verbose_name='imagem de capa',
    )
    cep = models.CharField(
        max_length=8,
        blank=True,
        db_column='platform_empresa_cep',
        verbose_name='CEP',
    )
    endereco = models.CharField(
        max_length=180,
        blank=True,
        db_column='platform_empresa_endereco',
        verbose_name='endereço',
    )
    numero = models.CharField(
        max_length=20,
        blank=True,
        db_column='platform_empresa_numero',
        verbose_name='número',
    )
    complemento = models.CharField(
        max_length=120,
        blank=True,
        db_column='platform_empresa_complemento',
        verbose_name='complemento',
    )
    bairro = models.CharField(
        max_length=120,
        blank=True,
        db_column='platform_empresa_bairro',
        verbose_name='bairro',
    )
    cidade = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        db_column='platform_empresa_cidade_fk',
        related_name='empresas',
        verbose_name='cidade',
    )
    estado = models.ForeignKey(
        Estado,
        on_delete=models.PROTECT,
        db_column='platform_empresa_estado_fk',
        related_name='empresas',
        verbose_name='estado',
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        db_column='platform_empresa_latitude',
        verbose_name='latitude',
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        db_column='platform_empresa_longitude',
        verbose_name='longitude',
    )
    atende_online = models.BooleanField(
        default=False,
        db_column='platform_empresa_atende_online',
        verbose_name='atende online',
    )
    atende_local = models.BooleanField(
        default=True,
        db_column='platform_empresa_atende_local',
        verbose_name='atende no local',
    )
    horario_atendimento = models.TextField(
        blank=True,
        db_column='platform_empresa_horario_atendimento',
        verbose_name='horário de atendimento',
    )
    aceita_leads = models.BooleanField(
        default=True,
        db_column='platform_empresa_aceita_leads',
        verbose_name='aceita leads',
    )
    canal_preferencial_lead = models.CharField(
        max_length=20,
        choices=CanalLead.choices,
        default=CanalLead.PAINEL,
        db_column='platform_empresa_canal_preferencial_lead',
        verbose_name='canal preferencial de lead',
    )
    distribuicao_lead = models.CharField(
        max_length=20,
        choices=DistribuicaoLead.choices,
        default=DistribuicaoLead.MANUAL,
        db_column='platform_empresa_distribuicao_lead',
        verbose_name='distribuição de lead',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RASCUNHO,
        db_column='platform_empresa_status',
        verbose_name='status',
    )
    verificada = models.BooleanField(
        default=False,
        db_column='platform_empresa_verificada',
        verbose_name='verificada',
    )
    perfil_publico = models.BooleanField(
        default=False,
        db_column='platform_empresa_perfil_publico',
        verbose_name='perfil público',
    )
    ativo = models.BooleanField(
        default=True,
        db_column='platform_empresa_ativo',
        verbose_name='ativo',
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        db_column='platform_empresa_criado_em',
        verbose_name='criado em',
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        db_column='platform_empresa_atualizado_em',
        verbose_name='atualizado em',
    )
    excluido_em = models.DateTimeField(
        null=True,
        blank=True,
        db_column='platform_empresa_excluido_em',
        verbose_name='excluído em',
    )
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column='platform_empresa_qr_token')
    qr_ativo = models.BooleanField(default=True, db_default=True, db_column='platform_empresa_qr_ativo')
    qr_atualizado_em = models.DateTimeField(default=timezone.now, db_column='platform_empresa_qr_atualizado_em')

    objects = EmpresaManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['nome_fantasia']
        verbose_name = 'empresa'
        verbose_name_plural = 'empresas'
        db_table = '"platform"."platform_empresa_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['cpf_cnpj'],
                condition=~models.Q(cpf_cnpj=''),
                name='platform_empresa_cpf_cnpj_uk',
            ),
        ]
        indexes = [
            models.Index(fields=['cpf_cnpj'], name='platform_empresa_cpf_cnpj_idx'),
            models.Index(fields=['slug'], name='platform_empresa_slug_idx'),
            models.Index(
                fields=['nome_fantasia'],
                name='platform_empresa_nmfant_idx',
            ),
            models.Index(fields=['status'], name='platform_empresa_status_idx'),
            models.Index(fields=['cidade'], name='platform_empresa_cidade_idx'),
            models.Index(fields=['estado'], name='platform_empresa_estado_idx'),
            models.Index(
                fields=['usuario_proprietario'],
                name='platform_empresa_usu_prop_idx',
            ),
            models.Index(fields=['ativo'], name='platform_empresa_ativo_idx'),
        ]

    def __str__(self) -> str:
        return self.nome_exibicao

    def clean(self) -> None:
        super().clean()

        documento = normalizar_digitos(self.cpf_cnpj)
        if documento:
            if self.tipo_cadastro in {
                self.TipoCadastro.AUTONOMO,
                self.TipoCadastro.INFORMAL,
            } and len(documento) not in {11, 14}:
                raise ValidationError(
                    {'cpf_cnpj': 'Informe um CPF ou CNPJ válido.'}
                )

            if self.tipo_cadastro in {
                self.TipoCadastro.MEI,
                self.TipoCadastro.EMPRESA,
                self.TipoCadastro.ORGANIZACAO,
            } and len(documento) != 14:
                raise ValidationError(
                    {'cpf_cnpj': 'Pessoa jurídica deve informar CNPJ.'}
                )

        if self.cidade_id and self.estado_id and self.cidade.estado_id != self.estado_id:
            raise ValidationError(
                {'cidade': 'A cidade selecionada não pertence ao estado informado.'}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.cpf_cnpj = normalizar_digitos(self.cpf_cnpj)
        self.cep = normalizar_digitos(self.cep)
        self.telefone = normalizar_digitos(self.telefone)
        self.whatsapp = normalizar_digitos(self.whatsapp)

        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome_fantasia)

        self.full_clean()
        super().save(*args, **kwargs)

    def delete(
        self,
        using: str | None = None,
        keep_parents: bool = False,
    ) -> tuple[int, dict[str, int]]:
        self.ativo = False
        self.excluido_em = timezone.now()
        self.save(
            using=using,
            update_fields=['ativo', 'excluido_em', 'atualizado_em'],
        )
        return 1, {self._meta.label: 1}

    def hard_delete(
        self,
        using: str | None = None,
        keep_parents: bool = False,
    ) -> tuple[int, dict[str, int]]:
        return super().delete(using=using, keep_parents=keep_parents)

    @property
    def documento_formatado(self) -> str:
        """Retorna CPF/CNPJ formatado para exibição."""

        return formatar_documento(self.cpf_cnpj)

    @property
    def nome_exibicao(self) -> str:
        """Retorna o melhor nome público da empresa."""

        return self.nome_fantasia or self.razao_social

    @property
    def endereco_resumido(self) -> str:
        """Retorna endereço compacto para cards e cabeçalhos."""

        partes = [
            self.cidade.nome if self.cidade_id else '',
            self.estado.sigla if self.estado_id else '',
        ]
        return ' - '.join(parte for parte in partes if parte)

    @property
    def pode_publicar(self) -> bool:
        """Indica se a empresa está apta a publicar serviços."""

        return self.ativo and self.status == self.Status.ATIVA

    @property
    def endereco_principal(self):
        vinculo = self.enderecos_empresa.filter(ativo=True, principal=True).select_related('endereco').first()
        return vinculo.endereco if vinculo else None

    @property
    def pode_publicar_produto(self) -> bool:
        return self._tem_capacidade_aprovada('VENDER_PRODUTOS')

    @property
    def pode_publicar_servico(self) -> bool:
        return self._tem_capacidade_aprovada('PRESTAR_SERVICOS')

    @property
    def pode_receber_lead(self) -> bool:
        return self.aceita_leads and self._tem_capacidade_aprovada('RECEBER_LEADS')

    def _tem_capacidade_aprovada(self, codigo: str) -> bool:
        return (
            self.ativo
            and self.status == self.Status.ATIVA
            and self.capacidades_empresa.filter(
                ativo=True,
                status=EmpresaCapacidade.Status.APROVADA,
                capacidade__codigo=codigo,
            ).exists()
        )

    @property
    def total_servicos(self) -> int:
        """Retorna total de serviços vinculados quando o módulo existir."""

        servicos = getattr(self, 'servicos', None)
        return servicos.count() if servicos is not None else 0

    @property
    def total_colaboradores(self) -> int:
        return self.usuarios_vinculados.filter(ativo=True).count()

    def regenerar_qr_token(self):
        self.qr_token = uuid.uuid4()
        self.qr_atualizado_em = timezone.now()
        self.save(update_fields=['qr_token', 'qr_atualizado_em', 'atualizado_em'])


class EmpresaLink(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='platform_empresa_link_id')
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True, verbose_name='UUID')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column='platform_empresa_link_fk_empresa', related_name='links')
    tipo_link = models.CharField(max_length=20, choices=TipoLink.choices, db_column='platform_empresa_link_tipo')
    titulo = models.CharField(max_length=120, blank=True, db_column='platform_empresa_link_titulo')
    url = models.URLField(max_length=500, db_column='platform_empresa_link_url')
    identificador_externo = models.CharField(max_length=120, null=True, blank=True, db_column='platform_empresa_link_identificador_externo')
    ordem = models.PositiveSmallIntegerField(default=0, db_column='platform_empresa_link_ordem')
    destaque = models.BooleanField(default=False, db_column='platform_empresa_link_destaque')
    ativo = models.BooleanField(default=True, db_column='platform_empresa_link_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='platform_empresa_link_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='platform_empresa_link_atualizado_em')
    excluido_em = models.DateTimeField(null=True, blank=True, db_column='platform_empresa_link_excluido_em')

    class Meta:
        ordering = ['-destaque', 'ordem', 'id']
        db_table = '"platform"."platform_empresa_link_tb"'
        indexes = [models.Index(fields=['empresa', 'ativo', 'ordem'], name='platform_emp_link_e_a_o_idx')]
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'url'], condition=models.Q(ativo=True, excluido_em__isnull=True), name='platform_emp_link_url_ativa_uk'),
        ]

    def clean(self):
        super().clean()
        if self.empresa_id and self.ativo and self.excluido_em is None:
            ativos = type(self).objects.filter(empresa_id=self.empresa_id, ativo=True, excluido_em__isnull=True).exclude(pk=self.pk)
            if ativos.count() >= 15:
                raise ValidationError('Cada empresa pode ter no máximo 15 links ativos.')
            if self.tipo_link == TipoLink.YOUTUBE and ativos.filter(tipo_link=TipoLink.YOUTUBE, identificador_externo__gt='').count() >= 6:
                raise ValidationError('Cada empresa pode exibir no máximo 6 vídeos do YouTube.')
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


class EmpresaUsuario(UUIDModel):
    """Vínculo de usuários com empresas e permissões operacionais."""

    class Funcao(models.TextChoices):
        PROPRIETARIO = 'PROPRIETARIO', 'Proprietário'
        ADMINISTRADOR = 'ADMINISTRADOR', 'Administrador'
        GERENTE = 'GERENTE', 'Gerente'
        COLABORADOR = 'COLABORADOR', 'Colaborador'
        ATENDENTE = 'ATENDENTE', 'Atendente'

    id = models.BigAutoField(
        primary_key=True,
        db_column='platform_empresa_usuario_id',
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        db_column='platform_empresa_usuario_empresa_fk',
        related_name='usuarios_vinculados',
        verbose_name='empresa',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='platform_empresa_usuario_usuario_fk',
        related_name='empresas_vinculos',
        verbose_name='usuário',
    )
    funcao = models.CharField(
        max_length=20,
        choices=Funcao.choices,
        default=Funcao.COLABORADOR,
        db_column='platform_empresa_usuario_funcao',
        verbose_name='função',
    )
    proprietario = models.BooleanField(
        default=False,
        db_column='platform_empresa_usuario_proprietario',
        verbose_name='proprietário',
    )
    administrador = models.BooleanField(
        default=False,
        db_column='platform_empresa_usuario_administrador',
        verbose_name='administrador',
    )
    pode_editar = models.BooleanField(
        default=False,
        db_column='platform_empresa_usuario_pode_editar',
        verbose_name='pode editar',
    )
    pode_publicar_servico = models.BooleanField(
        default=False,
        db_column='platform_empresa_usuario_pode_publicar_servico',
        verbose_name='pode publicar serviço',
    )
    pode_gerenciar_equipe = models.BooleanField(
        default=False,
        db_column='platform_empresa_usuario_pode_gerenciar_equipe',
        verbose_name='pode gerenciar equipe',
    )
    ativo = models.BooleanField(
        default=True,
        db_column='platform_empresa_usuario_ativo',
        verbose_name='ativo',
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        db_column='platform_empresa_usuario_criado_em',
        verbose_name='criado em',
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        db_column='platform_empresa_usuario_atualizado_em',
        verbose_name='atualizado em',
    )

    class Meta:
        ordering = ['empresa__nome_fantasia', 'usuario__username']
        verbose_name = 'usuário da empresa'
        verbose_name_plural = 'usuários das empresas'
        db_table = '"platform"."platform_empresa_usuario_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'usuario'],
                name='platform_empresa_usuario_uk',
            ),
        ]
        indexes = [
            models.Index(
                fields=['empresa', 'usuario'],
                name='platform_empresa_usuario_idx',
            ),
            models.Index(
                fields=['usuario'],
                name='platform_empresa_usu_usr_idx',
            ),
            models.Index(
                fields=['funcao'],
                name='platform_empresa_usu_func_idx',
            ),
            models.Index(
                fields=['ativo'],
                name='platform_empresa_usu_ativo_idx',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.empresa} - {self.usuario}'

    def clean(self) -> None:
        super().clean()

        if self.proprietario and self.funcao != self.Funcao.PROPRIETARIO:
            self.funcao = self.Funcao.PROPRIETARIO

        if self.funcao == self.Funcao.PROPRIETARIO:
            self.proprietario = True

        if self.proprietario:
            self.administrador = True
            self.pode_editar = True
            self.pode_publicar_servico = True
            self.pode_gerenciar_equipe = True

        if (
            self.empresa_id
            and self.usuario_id
            and self.empresa.usuario_proprietario_id == self.usuario_id
        ):
            self.proprietario = True
            self.funcao = self.Funcao.PROPRIETARIO

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class EmpresaEndereco(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='platform_empresa_endereco_id')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column='platform_empresa_endereco_fk_empresa', related_name='enderecos_empresa')
    endereco = models.ForeignKey(EnderecoCore, on_delete=models.CASCADE, db_column='platform_empresa_endereco_fk_endereco', related_name='empresas_vinculadas')
    principal = models.BooleanField(default=False, db_column='platform_empresa_endereco_principal')
    publico = models.BooleanField(default=True, db_column='platform_empresa_endereco_publico')
    ativo = models.BooleanField(default=True, db_column='platform_empresa_endereco_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='platform_empresa_endereco_criado_em')

    class Meta:
        db_table = '"platform"."platform_empresa_endereco_tb"'
        constraints = [models.UniqueConstraint(fields=['empresa', 'endereco'], name='platform_empresa_endereco_uk')]
        indexes = [models.Index(fields=['empresa', 'principal'], name='platform_empresa_end_idx_princ')]


class Capacidade(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='platform_capacidade_id')
    codigo = models.CharField(max_length=60, unique=True, db_column='platform_capacidade_codigo')
    nome = models.CharField(max_length=120, db_column='platform_capacidade_nome')
    descricao = models.TextField(blank=True, db_column='platform_capacidade_descricao')
    exige_aprovacao = models.BooleanField(default=True, db_column='platform_capacidade_exige_aprovacao')
    ativo = models.BooleanField(default=True, db_column='platform_capacidade_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='platform_capacidade_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='platform_capacidade_atualizado_em')

    class Meta:
        ordering = ['nome']
        db_table = '"platform"."platform_capacidade_tb"'
        indexes = [models.Index(fields=['codigo'], name='platform_capacidade_idx_codigo')]

    def __str__(self) -> str:
        return self.nome


class StatusCapacidadeMixin(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        APROVADA = 'APROVADA', 'Aprovada'
        REJEITADA = 'REJEITADA', 'Rejeitada'
        SUSPENSA = 'SUSPENSA', 'Suspensa'

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)

    class Meta:
        abstract = True


class UsuarioCapacidade(UUIDModel, StatusCapacidadeMixin):
    id = models.BigAutoField(primary_key=True, db_column='platform_usuario_capacidade_id')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='platform_usuario_capacidade_fk_usuario', related_name='capacidades_usuario')
    capacidade = models.ForeignKey(Capacidade, on_delete=models.CASCADE, db_column='platform_usuario_capacidade_fk_capacidade', related_name='usuarios_capacidade')
    status = models.CharField(max_length=20, choices=StatusCapacidadeMixin.Status.choices, default=StatusCapacidadeMixin.Status.PENDENTE, db_column='platform_usuario_capacidade_status')
    aprovado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, db_column='platform_usuario_capacidade_fk_aprovado_por', related_name='capacidades_usuario_aprovadas')
    aprovado_em = models.DateTimeField(null=True, blank=True, db_column='platform_usuario_capacidade_aprovado_em')
    motivo_rejeicao = models.TextField(blank=True, db_column='platform_usuario_capacidade_motivo_rejeicao')
    ativo = models.BooleanField(default=True, db_column='platform_usuario_capacidade_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='platform_usuario_capacidade_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='platform_usuario_capacidade_atualizado_em')

    class Meta:
        db_table = '"platform"."platform_usuario_capacidade_tb"'
        constraints = [models.UniqueConstraint(fields=['usuario', 'capacidade'], name='platform_usuario_capacidade_uk')]


class EmpresaCapacidade(UUIDModel, StatusCapacidadeMixin):
    id = models.BigAutoField(primary_key=True, db_column='platform_empresa_capacidade_id')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column='platform_empresa_capacidade_fk_empresa', related_name='capacidades_empresa')
    capacidade = models.ForeignKey(Capacidade, on_delete=models.CASCADE, db_column='platform_empresa_capacidade_fk_capacidade', related_name='empresas_capacidade')
    status = models.CharField(max_length=20, choices=StatusCapacidadeMixin.Status.choices, default=StatusCapacidadeMixin.Status.PENDENTE, db_column='platform_empresa_capacidade_status')
    aprovado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, db_column='platform_empresa_capacidade_fk_aprovado_por', related_name='capacidades_empresa_aprovadas')
    aprovado_em = models.DateTimeField(null=True, blank=True, db_column='platform_empresa_capacidade_aprovado_em')
    motivo_rejeicao = models.TextField(blank=True, db_column='platform_empresa_capacidade_motivo_rejeicao')
    ativo = models.BooleanField(default=True, db_column='platform_empresa_capacidade_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='platform_empresa_capacidade_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='platform_empresa_capacidade_atualizado_em')

    class Meta:
        db_table = '"platform"."platform_empresa_capacidade_tb"'
        constraints = [models.UniqueConstraint(fields=['empresa', 'capacidade'], name='platform_empresa_capacidade_uk')]


class EmpresaPropriedade(UUIDModel):
    class Origem(models.TextChoices):
        CADASTRO = 'CADASTRO', 'Cadastro'
        REIVINDICACAO = 'REIVINDICACAO', 'Reivindicação'
        TRANSFERENCIA = 'TRANSFERENCIA', 'Transferência'
        ADMINISTRATIVO = 'ADMINISTRATIVO', 'Administrativo'
        MIGRACAO = 'MIGRACAO', 'Migração'

    id = models.BigAutoField(primary_key=True, db_column='platform_empresa_propriedade_id')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column='platform_empresa_propriedade_fk_empresa', related_name='propriedades')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column='platform_empresa_propriedade_fk_usuario', related_name='propriedades_empresa')
    inicio_em = models.DateTimeField(default=timezone.now, db_column='platform_empresa_propriedade_inicio_em')
    fim_em = models.DateTimeField(null=True, blank=True, db_column='platform_empresa_propriedade_fim_em')
    atual = models.BooleanField(default=True, db_column='platform_empresa_propriedade_atual')
    origem = models.CharField(max_length=20, choices=Origem.choices, default=Origem.CADASTRO, db_column='platform_empresa_propriedade_origem')
    aprovado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, db_column='platform_empresa_propriedade_fk_aprovado_por', related_name='propriedades_aprovadas')
    aprovado_em = models.DateTimeField(null=True, blank=True, db_column='platform_empresa_propriedade_aprovado_em')
    observacao = models.TextField(blank=True, db_column='platform_empresa_propriedade_observacao')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='platform_empresa_propriedade_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='platform_empresa_propriedade_atualizado_em')

    class Meta:
        db_table = '"platform"."platform_empresa_propriedade_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['empresa'],
                condition=models.Q(atual=True, fim_em__isnull=True),
                name='platform_empresa_prop_atual_uk',
            ),
        ]


class EmpresaFuncao(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='platform_empresa_funcao_id')
    codigo = models.CharField(max_length=40, unique=True, db_column='platform_empresa_funcao_codigo')
    nome = models.CharField(max_length=100, db_column='platform_empresa_funcao_nome')
    descricao = models.TextField(blank=True, db_column='platform_empresa_funcao_descricao')
    ativo = models.BooleanField(default=True, db_column='platform_empresa_funcao_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='platform_empresa_funcao_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='platform_empresa_funcao_atualizado_em')

    class Meta:
        db_table = '"platform"."platform_empresa_funcao_tb"'

    def __str__(self) -> str:
        return self.nome


class EmpresaUsuarioFuncao(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='platform_empresa_usuario_funcao_id')
    empresa_usuario = models.ForeignKey(EmpresaUsuario, on_delete=models.CASCADE, db_column='platform_empresa_usuario_funcao_fk_empresa_usuario', related_name='funcoes_vinculadas')
    funcao = models.ForeignKey(EmpresaFuncao, on_delete=models.CASCADE, db_column='platform_empresa_usuario_funcao_fk_funcao', related_name='usuarios_vinculados')
    ativo = models.BooleanField(default=True, db_column='platform_empresa_usuario_funcao_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='platform_empresa_usuario_funcao_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='platform_empresa_usuario_funcao_atualizado_em')

    class Meta:
        db_table = '"platform"."platform_empresa_usuario_funcao_tb"'
        constraints = [models.UniqueConstraint(fields=['empresa_usuario', 'funcao'], name='platform_emp_usu_funcao_uk')]


class EmpresaUsuarioPermissao(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='platform_empresa_usuario_permissao_id')
    empresa_usuario = models.ForeignKey(EmpresaUsuario, on_delete=models.CASCADE, db_column='platform_empresa_usuario_permissao_fk_empresa_usuario', related_name='permissoes_granulares')
    codigo = models.CharField(max_length=60, db_column='platform_empresa_usuario_permissao_codigo')
    permitido = models.BooleanField(default=True, db_column='platform_empresa_usuario_permissao_permitido')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='platform_empresa_usuario_permissao_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='platform_empresa_usuario_permissao_atualizado_em')

    class Meta:
        db_table = '"platform"."platform_empresa_usuario_permissao_tb"'
        constraints = [models.UniqueConstraint(fields=['empresa_usuario', 'codigo'], name='platform_emp_usu_perm_uk')]


class CNAE(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='platform_cnae_id')
    codigo = models.CharField(max_length=20, unique=True, db_column='platform_cnae_codigo')
    descricao = models.TextField(db_column='platform_cnae_descricao')
    secao = models.CharField(max_length=5, blank=True, db_column='platform_cnae_secao')
    divisao = models.CharField(max_length=5, blank=True, db_column='platform_cnae_divisao')
    grupo = models.CharField(max_length=5, blank=True, db_column='platform_cnae_grupo')
    classe = models.CharField(max_length=10, blank=True, db_column='platform_cnae_classe')
    subclasse = models.CharField(max_length=20, blank=True, db_column='platform_cnae_subclasse')
    ativo = models.BooleanField(default=True, db_column='platform_cnae_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='platform_cnae_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='platform_cnae_atualizado_em')

    class Meta:
        db_table = '"platform"."platform_cnae_tb"'

    def __str__(self) -> str:
        return f'{self.codigo} - {self.descricao[:80]}'


class EmpresaCNAE(UUIDModel):
    class Origem(models.TextChoices):
        RECEITA = 'RECEITA', 'Receita'
        MANUAL = 'MANUAL', 'Manual'
        ADMINISTRATIVO = 'ADMINISTRATIVO', 'Administrativo'

    id = models.BigAutoField(primary_key=True, db_column='platform_empresa_cnae_id')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column='platform_empresa_cnae_fk_empresa', related_name='cnaes')
    cnae = models.ForeignKey(CNAE, on_delete=models.PROTECT, db_column='platform_empresa_cnae_fk_cnae', related_name='empresas')
    principal = models.BooleanField(default=False, db_column='platform_empresa_cnae_principal')
    origem = models.CharField(max_length=20, choices=Origem.choices, default=Origem.MANUAL, db_column='platform_empresa_cnae_origem')
    ativo = models.BooleanField(default=True, db_column='platform_empresa_cnae_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='platform_empresa_cnae_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='platform_empresa_cnae_atualizado_em')

    class Meta:
        db_table = '"platform"."platform_empresa_cnae_tb"'
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'cnae'], name='platform_empresa_cnae_uk'),
            models.UniqueConstraint(fields=['empresa'], condition=models.Q(principal=True, ativo=True), name='platform_empresa_cnae_princ_uk'),
        ]


class CNPJConsulta(UUIDModel):
    id = models.BigAutoField(primary_key=True, db_column='platform_cnpj_consulta_id')
    cnpj = models.CharField(max_length=14, db_column='platform_cnpj_consulta_cnpj')
    provider = models.CharField(max_length=60, db_column='platform_cnpj_consulta_provider')
    sucesso = models.BooleanField(default=False, db_column='platform_cnpj_consulta_sucesso')
    codigo_resposta = models.CharField(max_length=30, blank=True, db_column='platform_cnpj_consulta_codigo_resposta')
    resposta_json = models.JSONField(default=dict, blank=True, db_column='platform_cnpj_consulta_resposta_json')
    consultado_em = models.DateTimeField(default=timezone.now, db_column='platform_cnpj_consulta_consultado_em')
    expira_em = models.DateTimeField(null=True, blank=True, db_column='platform_cnpj_consulta_expira_em')
    solicitado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, db_column='platform_cnpj_consulta_fk_solicitado_por', related_name='consultas_cnpj')
    erro_resumido = models.CharField(max_length=240, blank=True, db_column='platform_cnpj_consulta_erro_resumido')

    class Meta:
        db_table = '"platform"."platform_cnpj_consulta_tb"'
        indexes = [models.Index(fields=['cnpj', 'provider'], name='plat_cnpj_cnpj_provider_idx')]

    def save(self, *args, **kwargs) -> None:
        self.cnpj = normalizar_digitos(self.cnpj)
        super().save(*args, **kwargs)


class EmpresaSolicitacao(UUIDModel):
    class TipoSolicitacao(models.TextChoices):
        CADASTRO = 'CADASTRO', 'Cadastro'
        REIVINDICACAO = 'REIVINDICACAO', 'Reivindicação'
        VINCULO = 'VINCULO', 'Vínculo'
        PROPRIEDADE = 'PROPRIEDADE', 'Propriedade'
        ALTERACAO_CADASTRAL = 'ALTERACAO_CADASTRAL', 'Alteração cadastral'
        NOVA_CAPACIDADE = 'NOVA_CAPACIDADE', 'Nova capacidade'

    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        PENDENTE = 'PENDENTE', 'Pendente'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        APROVADA = 'APROVADA', 'Aprovada'
        REJEITADA = 'REJEITADA', 'Rejeitada'
        CORRECAO_SOLICITADA = 'CORRECAO_SOLICITADA', 'Correção solicitada'
        CANCELADA = 'CANCELADA', 'Cancelada'

    id = models.BigAutoField(primary_key=True, db_column='platform_empresa_solicitacao_id')
    empresa = models.ForeignKey(Empresa, on_delete=models.SET_NULL, null=True, blank=True, db_column='platform_empresa_solicitacao_fk_empresa', related_name='solicitacoes')
    cnpj = models.CharField(max_length=14, blank=True, db_column='platform_empresa_solicitacao_cnpj')
    usuario_solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='platform_empresa_solicitacao_fk_usuario_solicitante', related_name='solicitacoes_empresa')
    tipo_solicitacao = models.CharField(max_length=30, choices=TipoSolicitacao.choices, db_column='platform_empresa_solicitacao_tipo')
    funcao_pretendida = models.CharField(max_length=60, blank=True, db_column='platform_empresa_solicitacao_funcao_pretendida')
    relacao_empresa = models.CharField(max_length=120, blank=True, db_column='platform_empresa_solicitacao_relacao_empresa')
    justificativa = models.TextField(blank=True, db_column='platform_empresa_solicitacao_justificativa')
    documento_comprovacao = models.FileField(upload_to='empresas/solicitacoes/%Y/%m/', blank=True, db_column='platform_empresa_solicitacao_documento_comprovacao')
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.RASCUNHO, db_column='platform_empresa_solicitacao_status')
    analisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, db_column='platform_empresa_solicitacao_fk_analisado_por', related_name='solicitacoes_empresa_analisadas')
    analisado_em = models.DateTimeField(null=True, blank=True, db_column='platform_empresa_solicitacao_analisado_em')
    motivo_decisao = models.TextField(blank=True, db_column='platform_empresa_solicitacao_motivo_decisao')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='platform_empresa_solicitacao_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='platform_empresa_solicitacao_atualizado_em')

    class Meta:
        db_table = '"platform"."platform_empresa_solicitacao_tb"'
        indexes = [models.Index(fields=['status'], name='platform_emp_solic_idx_status')]


class Organizacao(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Empresa, instituição ou prestador operando na plataforma."""

    id = models.BigAutoField(
        primary_key=True,
        db_column='platform_organizacao_id',
    )
    proprietario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column='platform_proprietario_fk',
        related_name='organizacoes_proprietario',
        verbose_name='proprietário',
    )
    usuarios = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        through='OrganizacaoUsuario',
        related_name='organizacoes',
        verbose_name='usuários',
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        db_column='platform_categoria_fk',
        related_name='organizacoes',
        verbose_name='categoria',
    )
    razao_social = models.CharField(
        max_length=180,
        blank=True,
        verbose_name='razão social',
    )
    nome_fantasia = models.CharField(
        max_length=180,
        verbose_name='nome fantasia',
    )
    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        verbose_name='slug',
    )
    documento = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='documento',
        help_text='CPF ou CNPJ sem formatação obrigatória.',
    )
    email = models.EmailField(blank=True, verbose_name='e-mail')
    telefone = models.CharField(max_length=20, blank=True, verbose_name='telefone')
    site = models.URLField(blank=True, verbose_name='site')

    class Meta:
        ordering = ['nome_fantasia']
        verbose_name = 'organização'
        verbose_name_plural = 'organizações'
        db_table = '"platform"."platform_organizacao_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['documento'],
                condition=~models.Q(documento=''),
                name='platform_organizacao_doc_uk',
            ),
        ]
        indexes = [
            models.Index(fields=['slug'], name='platform_organizacao_slug_idx'),
            models.Index(fields=['nome_fantasia'], name='platform_organizacao_nome_idx'),
            models.Index(fields=['categoria'], name='platform_organizacao_cat_idx'),
            models.Index(fields=['proprietario'], name='platform_organizacao_prop_idx'),
            models.Index(fields=['ativo'], name='platform_organizacao_ativo_idx'),
        ]

    def __str__(self) -> str:
        return self.nome_fantasia

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome_fantasia)

        super().save(*args, **kwargs)


class Unidade(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Unidade operacional de uma organização."""

    id = models.BigAutoField(primary_key=True, db_column='platform_unidade_id')
    organizacao = models.ForeignKey(
        Organizacao,
        on_delete=models.CASCADE,
        db_column='platform_organizacao_fk',
        related_name='unidades',
        verbose_name='organização',
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column='platform_responsavel_fk',
        related_name='unidades_responsavel',
        verbose_name='responsável',
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        db_column='platform_categoria_fk',
        related_name='unidades',
        verbose_name='categoria',
    )
    nome = models.CharField(max_length=160, verbose_name='nome')
    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        verbose_name='slug',
    )
    principal = models.BooleanField(default=False, verbose_name='principal')
    email = models.EmailField(blank=True, verbose_name='e-mail')
    telefone = models.CharField(max_length=20, blank=True, verbose_name='telefone')

    class Meta:
        ordering = ['organizacao__nome_fantasia', 'nome']
        verbose_name = 'unidade'
        verbose_name_plural = 'unidades'
        db_table = '"platform"."platform_unidade_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['organizacao', 'nome'],
                name='platform_unidade_nome_uk',
            ),
            models.UniqueConstraint(
                fields=['organizacao'],
                condition=models.Q(principal=True),
                name='platform_unidade_principal_uk',
            ),
        ]
        indexes = [
            models.Index(fields=['organizacao', 'nome'], name='platform_unidade_nome_idx'),
            models.Index(fields=['categoria'], name='platform_unidade_cat_idx'),
            models.Index(fields=['responsavel'], name='platform_unidade_resp_idx'),
            models.Index(fields=['principal'], name='platform_unidade_princ_idx'),
            models.Index(fields=['ativo'], name='platform_unidade_ativo_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.organizacao} - {self.nome}'

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug:
            self.slug = gerar_slug_unico(
                self,
                f'{self.organizacao.nome_fantasia} {self.nome}',
            )

        super().save(*args, **kwargs)


class Endereco(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Endereço físico de uma unidade."""

    id = models.BigAutoField(primary_key=True, db_column='platform_endereco_id')
    unidade = models.OneToOneField(
        Unidade,
        on_delete=models.CASCADE,
        db_column='platform_unidade_fk',
        related_name='endereco',
        verbose_name='unidade',
    )
    cidade = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        db_column='platform_cidade_fk',
        related_name='enderecos',
        verbose_name='cidade',
    )
    bairro = models.ForeignKey(
        Bairro,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column='platform_bairro_fk',
        related_name='enderecos',
        verbose_name='bairro',
    )
    logradouro = models.CharField(max_length=180, verbose_name='logradouro')
    numero = models.CharField(max_length=20, blank=True, verbose_name='número')
    complemento = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='complemento',
    )
    cep = models.CharField(max_length=12, blank=True, verbose_name='CEP')
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name='latitude',
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name='longitude',
    )

    class Meta:
        ordering = ['cidade__nome', 'logradouro', 'numero']
        verbose_name = 'endereço'
        verbose_name_plural = 'endereços'
        db_table = '"platform"."platform_endereco_tb"'
        indexes = [
            models.Index(fields=['cidade'], name='platform_endereco_cidade_idx'),
            models.Index(fields=['bairro'], name='platform_endereco_bairro_idx'),
            models.Index(fields=['cep'], name='platform_endereco_cep_idx'),
            models.Index(fields=['ativo'], name='platform_endereco_ativo_idx'),
        ]

    def __str__(self) -> str:
        numero = f', {self.numero}' if self.numero else ''
        return f'{self.logradouro}{numero} - {self.cidade}'


class OrganizacaoUsuario(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Vincula usuários a organizações com nomenclatura física controlada."""

    id = models.BigAutoField(
        primary_key=True,
        db_column='platform_organizacao_usuario_id',
    )
    organizacao = models.ForeignKey(
        Organizacao,
        on_delete=models.CASCADE,
        db_column='platform_organizacao_fk',
        related_name='organizacao_usuarios',
        verbose_name='organização',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='platform_usuario_fk',
        related_name='organizacao_usuarios',
        verbose_name='usuário',
    )

    class Meta:
        ordering = ['organizacao__nome_fantasia', 'usuario__username']
        verbose_name = 'usuário da organização'
        verbose_name_plural = 'usuários das organizações'
        db_table = '"platform"."platform_organizacao_usuario_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['organizacao', 'usuario'],
                name='platform_org_usuario_uk',
            ),
        ]
        indexes = [
            models.Index(
                fields=['organizacao', 'usuario'],
                name='platform_org_usuario_idx',
            ),
            models.Index(fields=['ativo'], name='platform_org_user_ativo_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.organizacao} - {self.usuario}'
