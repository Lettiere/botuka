"""Modelos do módulo interno de Comunicação do BOTUKA.

Domínios isolados:

1. Prospecção comercial
2. Distribuição de e-mails
3. E-mail marketing

IMPORTANTE:
Este app permanece desativado nesta etapa.
Nenhuma tabela será criada enquanto não houver ativação e migration explícitas.
"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel, UUIDModel


class ComunicacaoBase(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Base comum das entidades persistentes de Comunicação."""

    class Meta:
        abstract = True


# =============================================================================
# PROSPECÇÃO COMERCIAL
# =============================================================================


class ProspectoEmpresa(ComunicacaoBase):
    """Empresa externa ainda não cadastrada como Empresa BOTUKA."""

    class Status(models.TextChoices):
        NOVO = "NOVO", "Novo"
        VALIDADO = "VALIDADO", "Validado"
        CONTATADO = "CONTATADO", "Contatado"
        INTERESSADO = "INTERESSADO", "Interessado"
        NEGOCIACAO = "NEGOCIACAO", "Em negociação"
        CONVERTIDO = "CONVERTIDO", "Convertido"
        SEM_INTERESSE = "SEM_INTERESSE", "Sem interesse"
        NAO_CONTATAR = "NAO_CONTATAR", "Não contatar"

    class Origem(models.TextChoices):
        BASE_COMERCIAL = "BASE_COMERCIAL", "Base comercial"
        IMPORTACAO = "IMPORTACAO", "Importação"
        PESQUISA = "PESQUISA", "Pesquisa"
        INDICACAO = "INDICACAO", "Indicação"
        EVENTO = "EVENTO", "Evento"
        SITE = "SITE", "Site"
        MANUAL = "MANUAL", "Cadastro manual"
        OUTRO = "OUTRO", "Outro"

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_prospecto_empresa_id",
    )

    nome_fantasia = models.CharField(
        max_length=180,
        db_column="comunicacao_prospecto_empresa_nome_fantasia",
    )
    razao_social = models.CharField(
        max_length=180,
        blank=True,
        db_column="comunicacao_prospecto_empresa_razao_social",
    )
    cnpj = models.CharField(
        max_length=14,
        blank=True,
        db_index=True,
        db_column="comunicacao_prospecto_empresa_cnpj",
        help_text="Somente números.",
    )

    segmento = models.CharField(
        max_length=140,
        blank=True,
        db_index=True,
        db_column="comunicacao_prospecto_empresa_segmento",
    )

    cidade = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
        db_column="comunicacao_prospecto_empresa_cidade",
    )
    estado = models.CharField(
        max_length=2,
        blank=True,
        db_column="comunicacao_prospecto_empresa_estado",
    )
    bairro = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
        db_column="comunicacao_prospecto_empresa_bairro",
    )
    endereco = models.CharField(
        max_length=220,
        blank=True,
        db_column="comunicacao_prospecto_empresa_endereco",
    )
    cep = models.CharField(
        max_length=8,
        blank=True,
        db_column="comunicacao_prospecto_empresa_cep",
    )

    telefone = models.CharField(
        max_length=30,
        blank=True,
        db_column="comunicacao_prospecto_empresa_telefone",
    )
    whatsapp = models.CharField(
        max_length=30,
        blank=True,
        db_column="comunicacao_prospecto_empresa_whatsapp",
    )
    email_principal = models.EmailField(
        blank=True,
        db_index=True,
        db_column="comunicacao_prospecto_empresa_email_principal",
    )
    site = models.URLField(
        blank=True,
        db_column="comunicacao_prospecto_empresa_site",
    )

    origem = models.CharField(
        max_length=30,
        choices=Origem.choices,
        default=Origem.MANUAL,
        db_index=True,
        db_column="comunicacao_prospecto_empresa_origem",
    )
    origem_detalhe = models.CharField(
        max_length=220,
        blank=True,
        db_column="comunicacao_prospecto_empresa_origem_detalhe",
    )

    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.NOVO,
        db_index=True,
        db_column="comunicacao_prospecto_empresa_status",
    )

    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prospectos_empresas_responsavel",
        db_column="comunicacao_prospecto_empresa_responsavel_fk",
    )

    empresa_convertida = models.ForeignKey(
        "organizations.Empresa",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prospectos_origem",
        db_column="comunicacao_prospecto_empresa_convertida_fk",
        help_text="Preenchida apenas quando o prospecto virar uma Empresa BOTUKA.",
    )

    observacoes = models.TextField(
        blank=True,
        db_column="comunicacao_prospecto_empresa_observacoes",
    )

    ultimo_contato_em = models.DateTimeField(
        null=True,
        blank=True,
        db_column="comunicacao_prospecto_empresa_ultimo_contato_em",
    )
    proximo_contato_em = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        db_column="comunicacao_prospecto_empresa_proximo_contato_em",
    )

    class Meta:
        db_table = '"comunicacao"."comunicacao_prospecto_empresa_tb"'
        ordering = ["nome_fantasia", "id"]
        verbose_name = "prospecto de empresa"
        verbose_name_plural = "prospectos de empresas"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="CONVERTIDO",
                        empresa_convertida__isnull=False,
                    )
                    | (
                        ~models.Q(status="CONVERTIDO")
                        & models.Q(empresa_convertida__isnull=True)
                    )
                ),
                name="com_prosp_conv_status_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["cidade", "segmento", "status"],
                name="com_prosp_cid_seg_status_idx",
            ),
            models.Index(
                fields=["status", "proximo_contato_em"],
                name="com_prosp_status_prox_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.email_principal:
            self.email_principal = self.email_principal.strip().lower()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.nome_fantasia


class ProspectoContato(ComunicacaoBase):
    """Pessoa ou endereço de contato vinculado a um prospecto."""

    class Tipo(models.TextChoices):
        COMERCIAL = "COMERCIAL", "Comercial"
        ADMINISTRATIVO = "ADMINISTRATIVO", "Administrativo"
        FINANCEIRO = "FINANCEIRO", "Financeiro"
        MARKETING = "MARKETING", "Marketing"
        RH = "RH", "Recursos humanos"
        PROPRIETARIO = "PROPRIETARIO", "Proprietário"
        DIRETORIA = "DIRETORIA", "Diretoria"
        OUTRO = "OUTRO", "Outro"

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_prospecto_contato_id",
    )

    prospecto = models.ForeignKey(
        ProspectoEmpresa,
        on_delete=models.CASCADE,
        related_name="contatos",
        db_column="comunicacao_prospecto_contato_empresa_fk",
    )

    nome = models.CharField(
        max_length=160,
        blank=True,
        db_column="comunicacao_prospecto_contato_nome",
    )
    cargo = models.CharField(
        max_length=120,
        blank=True,
        db_column="comunicacao_prospecto_contato_cargo",
    )
    tipo = models.CharField(
        max_length=24,
        choices=Tipo.choices,
        default=Tipo.COMERCIAL,
        db_column="comunicacao_prospecto_contato_tipo",
    )

    email = models.EmailField(
        blank=True,
        db_index=True,
        db_column="comunicacao_prospecto_contato_email",
    )
    telefone = models.CharField(
        max_length=30,
        blank=True,
        db_column="comunicacao_prospecto_contato_telefone",
    )
    whatsapp = models.CharField(
        max_length=30,
        blank=True,
        db_column="comunicacao_prospecto_contato_whatsapp",
    )

    principal = models.BooleanField(
        default=False,
        db_column="comunicacao_prospecto_contato_principal",
    )

    observacoes = models.TextField(
        blank=True,
        db_column="comunicacao_prospecto_contato_observacoes",
    )

    class Meta:
        db_table = '"comunicacao"."comunicacao_prospecto_contato_tb"'
        ordering = ["-principal", "nome", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["prospecto", "email"],
                condition=models.Q(
                    email__gt="",
                    ativo=True,
                    removido_em__isnull=True,
                ),
                name="com_prosp_cont_email_ativo_uk",
            ),
            models.UniqueConstraint(
                fields=["prospecto"],
                condition=models.Q(
                    principal=True,
                    ativo=True,
                    removido_em__isnull=True,
                ),
                name="com_prosp_cont_princ_ativo_uk",
            ),
        ]
        indexes = [
            models.Index(
                fields=["prospecto", "principal", "ativo"],
                name="com_prosp_cont_princ_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.nome or self.email or f"Contato {self.pk}"


class ListaProspeccao(ComunicacaoBase):
    """Agrupamento de prospectos para ação comercial."""

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_lista_prospeccao_id",
    )
    nome = models.CharField(
        max_length=160,
        db_column="comunicacao_lista_prospeccao_nome",
    )
    descricao = models.TextField(
        blank=True,
        db_column="comunicacao_lista_prospeccao_descricao",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="listas_prospeccao_criadas",
        db_column="comunicacao_lista_prospeccao_criado_por_fk",
    )

    class Meta:
        db_table = '"comunicacao"."comunicacao_lista_prospeccao_tb"'
        ordering = ["nome", "id"]

    def __str__(self) -> str:
        return self.nome


class ListaProspecto(ComunicacaoBase):
    """Vínculo entre lista de prospecção e empresa prospectada."""

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_lista_prospecto_id",
    )
    lista = models.ForeignKey(
        ListaProspeccao,
        on_delete=models.CASCADE,
        related_name="itens",
        db_column="comunicacao_lista_prospecto_lista_fk",
    )
    prospecto = models.ForeignKey(
        ProspectoEmpresa,
        on_delete=models.CASCADE,
        related_name="listas",
        db_column="comunicacao_lista_prospecto_empresa_fk",
    )

    class Meta:
        db_table = '"comunicacao"."comunicacao_lista_prospecto_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=["lista", "prospecto"],
                condition=models.Q(
                    ativo=True,
                    removido_em__isnull=True,
                ),
                name="com_lista_prospecto_ativo_uk",
            )
        ]


class InteracaoProspeccao(ComunicacaoBase):
    """Histórico comercial do prospecto."""

    class Tipo(models.TextChoices):
        EMAIL = "EMAIL", "E-mail"
        TELEFONE = "TELEFONE", "Telefone"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        REUNIAO = "REUNIAO", "Reunião"
        VISITA = "VISITA", "Visita"
        OBSERVACAO = "OBSERVACAO", "Observação"
        STATUS = "STATUS", "Alteração de status"
        OUTRO = "OUTRO", "Outro"

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_interacao_prospeccao_id",
    )
    prospecto = models.ForeignKey(
        ProspectoEmpresa,
        on_delete=models.CASCADE,
        related_name="interacoes",
        db_column="comunicacao_interacao_prospeccao_empresa_fk",
    )
    contato = models.ForeignKey(
        ProspectoContato,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interacoes",
        db_column="comunicacao_interacao_prospeccao_contato_fk",
    )
    tipo = models.CharField(
        max_length=24,
        choices=Tipo.choices,
        db_index=True,
        db_column="comunicacao_interacao_prospeccao_tipo",
    )
    titulo = models.CharField(
        max_length=180,
        blank=True,
        db_column="comunicacao_interacao_prospeccao_titulo",
    )
    descricao = models.TextField(
        blank=True,
        db_column="comunicacao_interacao_prospeccao_descricao",
    )
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interacoes_prospeccao_realizadas",
        db_column="comunicacao_interacao_prospeccao_usuario_fk",
    )

    class Meta:
        db_table = '"comunicacao"."comunicacao_interacao_prospeccao_tb"'
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(
                fields=["prospecto", "tipo", "criado_em"],
                name="com_inter_prosp_tipo_idx",
            )
        ]


# =============================================================================
# DISTRIBUIÇÃO DE E-MAILS
# =============================================================================


class ListaDistribuicao(ComunicacaoBase):
    """Lista reutilizável de distribuição."""

    class Tipo(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        DINAMICA = "DINAMICA", "Dinâmica"

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_lista_distribuicao_id",
    )
    nome = models.CharField(
        max_length=160,
        db_column="comunicacao_lista_distribuicao_nome",
    )
    descricao = models.TextField(
        blank=True,
        db_column="comunicacao_lista_distribuicao_descricao",
    )
    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        default=Tipo.MANUAL,
        db_column="comunicacao_lista_distribuicao_tipo",
    )
    filtros = models.JSONField(
        default=dict,
        blank=True,
        db_column="comunicacao_lista_distribuicao_filtros",
        help_text="Filtros usados por listas dinâmicas.",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="listas_distribuicao_criadas",
        db_column="comunicacao_lista_distribuicao_criado_por_fk",
    )

    class Meta:
        db_table = '"comunicacao"."comunicacao_lista_distribuicao_tb"'
        ordering = ["nome", "id"]


class SegmentoDestinatario(ComunicacaoBase):
    """Segmento reutilizável de público do BOTUKA."""

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_segmento_destinatario_id",
    )
    nome = models.CharField(
        max_length=160,
        db_column="comunicacao_segmento_destinatario_nome",
    )
    descricao = models.TextField(
        blank=True,
        db_column="comunicacao_segmento_destinatario_descricao",
    )
    filtros = models.JSONField(
        default=dict,
        blank=True,
        db_column="comunicacao_segmento_destinatario_filtros",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="segmentos_destinatario_criados",
        db_column="comunicacao_segmento_destinatario_criado_por_fk",
    )

    class Meta:
        db_table = '"comunicacao"."comunicacao_segmento_destinatario_tb"'
        ordering = ["nome", "id"]


class Distribuicao(ComunicacaoBase):
    """Envio administrativo ou institucional."""

    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        PREPARANDO = "PREPARANDO", "Preparando"
        AGENDADO = "AGENDADO", "Agendado"
        PROCESSANDO = "PROCESSANDO", "Processando"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        CANCELADO = "CANCELADO", "Cancelado"
        ERRO = "ERRO", "Erro"

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_distribuicao_id",
    )
    titulo = models.CharField(
        max_length=180,
        db_column="comunicacao_distribuicao_titulo",
    )
    assunto = models.CharField(
        max_length=220,
        db_column="comunicacao_distribuicao_assunto",
    )
    conteudo_html = models.TextField(
        db_column="comunicacao_distribuicao_conteudo_html",
    )
    conteudo_texto = models.TextField(
        blank=True,
        db_column="comunicacao_distribuicao_conteudo_texto",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RASCUNHO,
        db_index=True,
        db_column="comunicacao_distribuicao_status",
    )
    lista = models.ForeignKey(
        ListaDistribuicao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="distribuicoes",
        db_column="comunicacao_distribuicao_lista_fk",
    )
    segmento = models.ForeignKey(
        SegmentoDestinatario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="distribuicoes",
        db_column="comunicacao_distribuicao_segmento_fk",
    )
    agendado_para = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        db_column="comunicacao_distribuicao_agendado_para",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="distribuicoes_criadas",
        db_column="comunicacao_distribuicao_criado_por_fk",
    )

    class Meta:
        db_table = '"comunicacao"."comunicacao_distribuicao_tb"'
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(
                fields=["status", "agendado_para"],
                name="com_dist_status_agenda_idx",
            )
        ]


class DistribuicaoDestinatario(ComunicacaoBase):
    """Snapshot dos destinatários de uma distribuição."""

    class TipoOrigem(models.TextChoices):
        USUARIO = "USUARIO", "Usuário"
        EMPRESA = "EMPRESA", "Empresa"
        PROSPECTO = "PROSPECTO", "Prospecto"
        MANUAL = "MANUAL", "Manual"
        OUTRO = "OUTRO", "Outro"

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        FILA = "FILA", "Na fila"
        ENVIADO = "ENVIADO", "Enviado"
        ENTREGUE = "ENTREGUE", "Entregue"
        FALHOU = "FALHOU", "Falhou"
        SUPRIMIDO = "SUPRIMIDO", "Suprimido"

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_distribuicao_destinatario_id",
    )
    distribuicao = models.ForeignKey(
        Distribuicao,
        on_delete=models.CASCADE,
        related_name="destinatarios",
        db_column="comunicacao_distribuicao_destinatario_distribuicao_fk",
    )
    nome = models.CharField(
        max_length=180,
        blank=True,
        db_column="comunicacao_distribuicao_destinatario_nome",
    )
    email = models.EmailField(
        db_index=True,
        db_column="comunicacao_distribuicao_destinatario_email",
    )
    tipo_origem = models.CharField(
        max_length=20,
        choices=TipoOrigem.choices,
        default=TipoOrigem.MANUAL,
        db_column="comunicacao_distribuicao_destinatario_tipo_origem",
    )
    origem_uuid = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        db_column="comunicacao_distribuicao_destinatario_origem_uuid",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_index=True,
        db_column="comunicacao_distribuicao_destinatario_status",
    )
    erro = models.TextField(
        blank=True,
        db_column="comunicacao_distribuicao_destinatario_erro",
    )

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        return super().save(*args, **kwargs)

    class Meta:
        db_table = '"comunicacao"."comunicacao_distribuicao_destinatario_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=["distribuicao", "email"],
                condition=models.Q(
                    ativo=True,
                    removido_em__isnull=True,
                ),
                name="com_dist_dest_email_ativo_uk",
            )
        ]
        indexes = [
            models.Index(
                fields=["distribuicao", "status"],
                name="com_dist_dest_status_idx",
            )
        ]


# =============================================================================
# E-MAIL MARKETING
# =============================================================================


class TemplateEmail(ComunicacaoBase):
    """Template reutilizável de e-mail."""

    class Categoria(models.TextChoices):
        PROSPECCAO = "PROSPECCAO", "Prospecção"
        INSTITUCIONAL = "INSTITUCIONAL", "Institucional"
        NEWSLETTER = "NEWSLETTER", "Newsletter"
        PROMOCIONAL = "PROMOCIONAL", "Promocional"
        EVENTOS = "EVENTOS", "Eventos"
        VAGAS = "VAGAS", "Vagas"
        OUTRO = "OUTRO", "Outro"

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_template_email_id",
    )
    nome = models.CharField(
        max_length=160,
        db_column="comunicacao_template_email_nome",
    )
    categoria = models.CharField(
        max_length=24,
        choices=Categoria.choices,
        default=Categoria.OUTRO,
        db_index=True,
        db_column="comunicacao_template_email_categoria",
    )
    assunto_padrao = models.CharField(
        max_length=220,
        blank=True,
        db_column="comunicacao_template_email_assunto_padrao",
    )
    conteudo_html = models.TextField(
        db_column="comunicacao_template_email_conteudo_html",
    )
    conteudo_texto = models.TextField(
        blank=True,
        db_column="comunicacao_template_email_conteudo_texto",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="templates_email_criados",
        db_column="comunicacao_template_email_criado_por_fk",
    )

    class Meta:
        db_table = '"comunicacao"."comunicacao_template_email_tb"'
        ordering = ["categoria", "nome", "id"]


class CampanhaEmail(ComunicacaoBase):
    """Campanha de e-mail marketing."""

    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        PREPARANDO = "PREPARANDO", "Preparando"
        AGENDADA = "AGENDADA", "Agendada"
        PROCESSANDO = "PROCESSANDO", "Processando"
        PAUSADA = "PAUSADA", "Pausada"
        CONCLUIDA = "CONCLUIDA", "Concluída"
        CANCELADA = "CANCELADA", "Cancelada"
        ERRO = "ERRO", "Erro"

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_campanha_email_id",
    )
    nome = models.CharField(
        max_length=180,
        db_column="comunicacao_campanha_email_nome",
    )
    assunto = models.CharField(
        max_length=220,
        db_column="comunicacao_campanha_email_assunto",
    )
    template = models.ForeignKey(
        TemplateEmail,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campanhas",
        db_column="comunicacao_campanha_email_template_fk",
    )
    segmento = models.ForeignKey(
        SegmentoDestinatario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campanhas",
        db_column="comunicacao_campanha_email_segmento_fk",
    )
    lista_prospeccao = models.ForeignKey(
        ListaProspeccao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campanhas_email",
        db_column="comunicacao_campanha_email_lista_prospeccao_fk",
    )

    conteudo_html = models.TextField(
        db_column="comunicacao_campanha_email_conteudo_html",
    )
    conteudo_texto = models.TextField(
        blank=True,
        db_column="comunicacao_campanha_email_conteudo_texto",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RASCUNHO,
        db_index=True,
        db_column="comunicacao_campanha_email_status",
    )
    agendada_para = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        db_column="comunicacao_campanha_email_agendada_para",
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="campanhas_email_criadas",
        db_column="comunicacao_campanha_email_criado_por_fk",
    )

    class Meta:
        db_table = '"comunicacao"."comunicacao_campanha_email_tb"'
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(
                fields=["status", "agendada_para"],
                name="com_camp_status_agenda_idx",
            )
        ]


class CampanhaDestinatario(ComunicacaoBase):
    """Snapshot e estado de cada destinatário de uma campanha."""

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        FILA = "FILA", "Na fila"
        ENVIADO = "ENVIADO", "Enviado"
        ENTREGUE = "ENTREGUE", "Entregue"
        ABERTO = "ABERTO", "Aberto"
        CLICADO = "CLICADO", "Clicado"
        BOUNCE = "BOUNCE", "Bounce"
        RECLAMACAO = "RECLAMACAO", "Reclamação"
        DESCADASTRADO = "DESCADASTRADO", "Descadastrado"
        SUPRIMIDO = "SUPRIMIDO", "Suprimido"
        FALHOU = "FALHOU", "Falhou"

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_campanha_destinatario_id",
    )
    campanha = models.ForeignKey(
        CampanhaEmail,
        on_delete=models.CASCADE,
        related_name="destinatarios",
        db_column="comunicacao_campanha_destinatario_campanha_fk",
    )
    nome = models.CharField(
        max_length=180,
        blank=True,
        db_column="comunicacao_campanha_destinatario_nome",
    )
    email = models.EmailField(
        db_index=True,
        db_column="comunicacao_campanha_destinatario_email",
    )
    origem_tipo = models.CharField(
        max_length=30,
        blank=True,
        db_column="comunicacao_campanha_destinatario_origem_tipo",
    )
    origem_uuid = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        db_column="comunicacao_campanha_destinatario_origem_uuid",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_index=True,
        db_column="comunicacao_campanha_destinatario_status",
    )

    enviado_em = models.DateTimeField(
        null=True,
        blank=True,
        db_column="comunicacao_campanha_destinatario_enviado_em",
    )
    entregue_em = models.DateTimeField(
        null=True,
        blank=True,
        db_column="comunicacao_campanha_destinatario_entregue_em",
    )
    aberto_em = models.DateTimeField(
        null=True,
        blank=True,
        db_column="comunicacao_campanha_destinatario_aberto_em",
    )
    clicado_em = models.DateTimeField(
        null=True,
        blank=True,
        db_column="comunicacao_campanha_destinatario_clicado_em",
    )

    tentativas = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        db_column="comunicacao_campanha_destinatario_tentativas",
    )
    ultimo_erro = models.TextField(
        blank=True,
        db_column="comunicacao_campanha_destinatario_ultimo_erro",
    )

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        return super().save(*args, **kwargs)

    class Meta:
        db_table = '"comunicacao"."comunicacao_campanha_destinatario_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=["campanha", "email"],
                condition=models.Q(
                    ativo=True,
                    removido_em__isnull=True,
                ),
                name="com_camp_dest_email_ativo_uk",
            )
        ]
        indexes = [
            models.Index(
                fields=["campanha", "status"],
                name="com_camp_dest_status_idx",
            )
        ]


class EventoEmail(ComunicacaoBase):
    """Eventos recebidos do provedor de e-mail."""

    class Tipo(models.TextChoices):
        ACEITO = "ACEITO", "Aceito"
        ENVIADO = "ENVIADO", "Enviado"
        ENTREGUE = "ENTREGUE", "Entregue"
        ABERTO = "ABERTO", "Aberto"
        CLIQUE = "CLIQUE", "Clique"
        BOUNCE = "BOUNCE", "Bounce"
        RECLAMACAO = "RECLAMACAO", "Reclamação"
        DESCADASTRO = "DESCADASTRO", "Descadastro"
        ERRO = "ERRO", "Erro"
        OUTRO = "OUTRO", "Outro"

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_evento_email_id",
    )
    campanha_destinatario = models.ForeignKey(
        CampanhaDestinatario,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="eventos",
        db_column="comunicacao_evento_email_campanha_destinatario_fk",
    )
    distribuicao_destinatario = models.ForeignKey(
        DistribuicaoDestinatario,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="eventos",
        db_column="comunicacao_evento_email_distribuicao_destinatario_fk",
    )
    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        db_index=True,
        db_column="comunicacao_evento_email_tipo",
    )
    provedor = models.CharField(
        max_length=60,
        blank=True,
        db_column="comunicacao_evento_email_provedor",
    )
    mensagem_externa_id = models.CharField(
        max_length=220,
        blank=True,
        db_index=True,
        db_column="comunicacao_evento_email_mensagem_externa_id",
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        db_column="comunicacao_evento_email_payload",
    )

    class Meta:
        db_table = '"comunicacao"."comunicacao_evento_email_tb"'
        ordering = ["-criado_em", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        campanha_destinatario__isnull=False,
                        distribuicao_destinatario__isnull=True,
                    )
                    | models.Q(
                        campanha_destinatario__isnull=True,
                        distribuicao_destinatario__isnull=False,
                    )
                ),
                name="com_event_dest_xor_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["mensagem_externa_id", "tipo"],
                name="com_event_msg_tipo_idx",
            )
        ]


class SupressaoEmail(ComunicacaoBase):
    """Lista central de e-mails que não devem receber determinados envios."""

    class Motivo(models.TextChoices):
        DESCADASTRO = "DESCADASTRO", "Descadastro"
        BOUNCE = "BOUNCE", "Bounce"
        RECLAMACAO = "RECLAMACAO", "Reclamação"
        BLOQUEIO_MANUAL = "BLOQUEIO_MANUAL", "Bloqueio manual"
        PEDIDO_TITULAR = "PEDIDO_TITULAR", "Pedido do titular"
        OUTRO = "OUTRO", "Outro"

    class Escopo(models.TextChoices):
        MARKETING = "MARKETING", "Marketing"
        PROSPECCAO = "PROSPECCAO", "Prospecção"
        TODOS = "TODOS", "Todos os envios não essenciais"

    id = models.BigAutoField(
        primary_key=True,
        db_column="comunicacao_supressao_email_id",
    )
    email = models.EmailField(
        db_index=True,
        db_column="comunicacao_supressao_email_email",
    )
    motivo = models.CharField(
        max_length=24,
        choices=Motivo.choices,
        db_column="comunicacao_supressao_email_motivo",
    )
    escopo = models.CharField(
        max_length=20,
        choices=Escopo.choices,
        default=Escopo.MARKETING,
        db_index=True,
        db_column="comunicacao_supressao_email_escopo",
    )
    origem = models.CharField(
        max_length=120,
        blank=True,
        db_column="comunicacao_supressao_email_origem",
    )
    observacoes = models.TextField(
        blank=True,
        db_column="comunicacao_supressao_email_observacoes",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supressoes_email_registradas",
        db_column="comunicacao_supressao_email_registrado_por_fk",
    )

    class Meta:
        db_table = '"comunicacao"."comunicacao_supressao_email_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=["email", "escopo"],
                condition=models.Q(
                    ativo=True,
                    removido_em__isnull=True,
                ),
                name="com_sup_email_escopo_ativo_uk",
            )
        ]
        indexes = [
            models.Index(
                fields=["email", "escopo", "ativo"],
                name="com_sup_email_escopo_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.email} — {self.get_escopo_display()}"
