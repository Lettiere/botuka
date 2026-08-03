from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import SoftDeleteModel, TimeStampedModel, UUIDModel
from apps.core.services.rich_text import sanitizar_html_rico


class Evento(UUIDModel, TimeStampedModel, SoftDeleteModel):
    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        APROVADO = 'APROVADO', 'Aprovado'
        PUBLICADO = 'PUBLICADO', 'Publicado'
        REJEITADO = 'REJEITADO', 'Rejeitado'
        PAUSADO = 'PAUSADO', 'Pausado'
        CANCELADO = 'CANCELADO', 'Cancelado'
        ENCERRADO = 'ENCERRADO', 'Encerrado'
        ARQUIVADO = 'ARQUIVADO', 'Arquivado'

    class ParticipacaoFutura(models.TextChoices):
        NAO_DEFINIDA = 'NAO_DEFINIDA', 'Não definida'
        EXTERNA = 'EXTERNA', 'Inscrição externa'
        GRATUITA = 'GRATUITA', 'Ingresso gratuito futuro'
        PAGA = 'PAGA', 'Ingresso pago futuro'

    titulo = models.CharField(max_length=220)
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    resumo = models.CharField(max_length=300)
    descricao = models.TextField()
    imagem_principal = models.ImageField(upload_to='eventos/capas/', blank=True)
    imagem_alt = models.CharField(max_length=220, blank=True)
    inicio = models.DateTimeField()
    fim = models.DateTimeField(null=True, blank=True)
    local = models.CharField(max_length=220)
    endereco = models.CharField(max_length=300, blank=True)
    categoria = models.CharField(max_length=100, blank=True)
    publico = models.BooleanField(default=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RASCUNHO, db_index=True)
    publicado_em = models.DateTimeField(null=True, blank=True)

    proprietario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='eventos_proprios')
    responsavel_edicao = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='eventos_responsavel')
    criador_registro = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='eventos_criados')
    empresa_promotora = models.ForeignKey('organizations.Empresa', on_delete=models.PROTECT, null=True, blank=True, related_name='eventos_promovidos')
    organizador = models.CharField(max_length=180, blank=True)
    realizador = models.CharField(max_length=180, blank=True)

    permitir_interesse = models.BooleanField(default=True)
    mensagem_interesse = models.CharField(max_length=240, blank=True)
    aceita_inscricoes_futuras = models.BooleanField(default=False)
    modalidade_participacao_futura = models.CharField(max_length=20, choices=ParticipacaoFutura.choices, default=ParticipacaoFutura.NAO_DEFINIDA)
    limite_estimado_publico = models.PositiveIntegerField(null=True, blank=True)
    url_inscricao_externa = models.URLField(blank=True, max_length=500)
    observacao_ingresso = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = '"events"."events_evento"'
        ordering = ['inicio', 'titulo']
        indexes = [
            models.Index(fields=['status', 'publico', 'inicio'], name='events_public_status_idx'),
            models.Index(fields=['proprietario', 'status'], name='events_owner_status_idx'),
            models.Index(fields=['empresa_promotora', 'status'], name='events_company_status_idx'),
        ]

    def clean(self):
        self.descricao = sanitizar_html_rico(self.descricao)
        if self.fim and self.fim < self.inicio:
            raise ValidationError({'fim': 'O término deve ser posterior ao início.'})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.titulo)[:220] or 'evento'
            slug = base
            number = 2
            while type(self).all_objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f'{base}-{number}'
                number += 1
            self.slug = slug
        if self.status == self.Status.PUBLICADO and not self.publicado_em:
            self.publicado_em = timezone.now()
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def aceita_novos_interesses(self):
        return (
            self.ativo and self.removido_em is None and self.publico
            and self.status == self.Status.PUBLICADO and self.permitir_interesse
            and self.inicio > timezone.now()
        )

    @property
    def texto_interesse(self):
        return self.mensagem_interesse or 'Marque seu interesse em participar deste evento.'

    def get_absolute_url(self):
        return reverse('events:detalhe', args=[self.slug])

    def __str__(self):
        return self.titulo


class InteresseEvento(UUIDModel, TimeStampedModel):
    class Origem(models.TextChoices):
        WEB = 'WEB', 'Página web'
        PAINEL = 'PAINEL', 'Painel'

    evento = models.ForeignKey(Evento, on_delete=models.PROTECT, related_name='interesses')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='interesses_eventos')
    ativo = models.BooleanField(default=True, db_index=True)
    origem = models.CharField(max_length=16, choices=Origem.choices, default=Origem.WEB)
    cancelado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = '"events"."events_interesseevento"'
        ordering = ['-criado_em']
        constraints = [
            models.UniqueConstraint(fields=['evento', 'usuario'], name='events_interesse_usuario_uk'),
        ]
        indexes = [models.Index(fields=['evento', 'ativo', 'criado_em'], name='events_interest_metric_idx')]

    def __str__(self):
        return f'{self.evento} · {self.usuario}'


class HistoricoEvento(UUIDModel, TimeStampedModel):
    class Acao(models.TextChoices):
        CRIADO = 'CRIADO', 'Criado'
        ALTERADO = 'ALTERADO', 'Alterado'
        STATUS = 'STATUS', 'Status alterado'
        INTERESSE = 'INTERESSE', 'Interesse marcado'
        INTERESSE_REMOVIDO = 'INTERESSE_REMOVIDO', 'Interesse removido'

    evento = models.ForeignKey(Evento, on_delete=models.PROTECT, related_name='historico')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    acao = models.CharField(max_length=24, choices=Acao.choices)
    origem = models.CharField(max_length=20, default='WEB')
    dados = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = '"events"."events_historicoevento"'
        ordering = ['-criado_em']
