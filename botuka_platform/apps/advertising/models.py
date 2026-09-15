from __future__ import annotations

import uuid
import mimetypes
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.html import strip_tags


def formatos_criativo_padrao():
    return ['jpg', 'jpeg', 'png', 'webp', 'mp4', 'webm']


class PlanoPublicitario(models.Model):
    class Nivel(models.IntegerChoices):
        ZERO = 0, 'Impacto / Takeover'
        UM = 1, 'Destaque Premium'
        DOIS = 2, 'Destaque Plus'
        TRES = 3, 'Destaque Segmentado'
        QUATRO = 4, 'Standard'

    nome = models.CharField(max_length=120, unique=True)
    descricao = models.TextField(blank=True)
    nivel = models.PositiveSmallIntegerField(choices=Nivel.choices)
    preco_diario = models.DecimalField(max_digits=12, decimal_places=2)
    prioridade = models.PositiveSmallIntegerField(default=0)
    exclusivo = models.BooleanField(default=False)
    limite_anunciantes = models.PositiveIntegerField(default=0, help_text='Zero significa sem limite.')
    impressoes_por_usuario_dia = models.PositiveIntegerField(default=3)
    duracao_segundos = models.PositiveSmallIntegerField(default=8)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = '"advertising"."advertising_plano_tb"'
        constraints = [
            models.CheckConstraint(condition=models.Q(preco_diario__gte=0), name='adv_plano_preco_ck'),
            models.CheckConstraint(condition=models.Q(impressoes_por_usuario_dia__gte=1), name='adv_plano_freq_ck'),
        ]

    def clean(self):
        if self.nivel == self.Nivel.ZERO and not self.exclusivo:
            raise ValidationError({'exclusivo': 'Takeover deve ser exclusivo.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class Posicionamento(models.Model):
    codigo = models.SlugField(max_length=80, unique=True)
    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True)
    contexto = models.CharField(max_length=80, db_index=True)
    largura = models.PositiveIntegerField(null=True, blank=True)
    altura = models.PositiveIntegerField(null=True, blank=True)
    largura_mobile = models.PositiveIntegerField(null=True, blank=True)
    altura_mobile = models.PositiveIntegerField(null=True, blank=True)
    proporcao_recomendada = models.CharField(max_length=24, blank=True)
    tamanho_maximo_bytes = models.PositiveIntegerField(default=5 * 1024 * 1024)
    formatos_permitidos = models.JSONField(
        default=formatos_criativo_padrao, blank=True,
        help_text='Extensões sem ponto, por exemplo: jpg, png, webp, mp4, webm.',
    )
    permite_imagem = models.BooleanField(default=True)
    permite_video = models.BooleanField(default=True)
    permite_texto = models.BooleanField(default=True)
    dimensoes_obrigatorias = models.BooleanField(default=False)
    aceita_takeover = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = '"advertising"."advertising_posicionamento_tb"'

    def __str__(self):
        return self.nome

    def clean(self):
        if not isinstance(self.formatos_permitidos, list):
            raise ValidationError({'formatos_permitidos': 'Informe uma lista de extensões.'})
        formatos = []
        for value in self.formatos_permitidos:
            normalized = str(value).strip().lower().lstrip('.')
            if not normalized or not normalized.isalnum():
                raise ValidationError({'formatos_permitidos': 'Extensão inválida.'})
            formatos.append(normalized)
        self.formatos_permitidos = list(dict.fromkeys(formatos))
        if self.dimensoes_obrigatorias and not (self.largura and self.altura):
            raise ValidationError('Dimensões desktop são obrigatórias quando a validação estrita está ativa.')
        if not any((self.permite_imagem, self.permite_video, self.permite_texto)):
            raise ValidationError('Permita ao menos um tipo de criativo.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Campanha(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        AGUARDANDO_APROVACAO = 'AGUARDANDO_APROVACAO', 'Aguardando aprovação'
        APROVADA = 'APROVADA', 'Aprovada'
        ATIVA = 'ATIVA', 'Ativa'
        PAUSADA = 'PAUSADA', 'Pausada'
        ENCERRADA = 'ENCERRADA', 'Encerrada'
        CANCELADA = 'CANCELADA', 'Cancelada'
        REJEITADA = 'REJEITADA', 'Rejeitada'

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    empresa = models.ForeignKey('organizations.Empresa', on_delete=models.PROTECT, related_name='campanhas_publicitarias')
    plano = models.ForeignKey(PlanoPublicitario, on_delete=models.PROTECT, related_name='campanhas')
    posicionamentos = models.ManyToManyField(Posicionamento, related_name='campanhas')
    nome = models.CharField(max_length=160)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RASCUNHO, editable=False)
    inicio = models.DateTimeField()
    fim = models.DateTimeField()
    aprovada_em = models.DateTimeField(null=True, blank=True, editable=False)
    aprovada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='campanhas_aprovadas')
    motivo_rejeicao = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='campanhas_criadas')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"advertising"."advertising_campanha_tb"'
        indexes = [models.Index(fields=['status', 'inicio', 'fim'], name='adv_camp_status_period_idx')]
        constraints = [models.CheckConstraint(condition=models.Q(fim__gt=models.F('inicio')), name='adv_camp_periodo_ck')]

    def clean(self):
        if self.fim <= self.inicio:
            raise ValidationError({'fim': 'O fim deve ser posterior ao início.'})

    def elegivel(self, agora=None):
        agora = agora or timezone.now()
        return self.status == self.Status.ATIVA and self.aprovada_em is not None and self.inicio <= agora < self.fim and hasattr(self, 'contratacao') and self.contratacao.esta_paga

    @property
    def status_financeiro(self):
        if not hasattr(self, 'contratacao'):
            return 'PENDENTE'
        cobranca = self.contratacao.cobranca
        if cobranca.status == 'PAGA':
            return 'PAGO'
        if cobranca.status == 'CANCELADA':
            return 'CANCELADO'
        if cobranca.status == 'ESTORNADA':
            return 'ESTORNADO'
        if cobranca.vencimento and cobranca.vencimento < timezone.now():
            return 'VENCIDO'
        pagamento = cobranca.pagamentos.order_by('-criado_em').first()
        return 'RECUSADO' if pagamento and pagamento.status == 'FALHOU' else 'PENDENTE'

    def __str__(self):
        return self.nome


class ContratacaoPublicidade(models.Model):
    campanha = models.OneToOneField(Campanha, on_delete=models.PROTECT, related_name='contratacao')
    cobranca = models.OneToOneField('payments.Cobranca', on_delete=models.PROTECT, related_name='contratacao_publicidade')
    quantidade_dias = models.PositiveIntegerField(editable=False)
    valor_diario = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"advertising"."advertising_contratacao_tb"'
        constraints = [
            models.CheckConstraint(condition=models.Q(quantidade_dias__gte=1), name='adv_contratacao_dias_ck'),
            models.CheckConstraint(condition=models.Q(valor_total__gt=0), name='adv_contratacao_total_ck'),
        ]

    @property
    def esta_paga(self):
        from apps.payments.models import Cobranca
        return self.cobranca.status == Cobranca.Status.PAGA


class CampanhaSegmentacao(models.Model):
    campanha = models.OneToOneField(Campanha, on_delete=models.CASCADE, related_name='segmentacao')
    categorias = models.ManyToManyField('taxonomy.Categoria', blank=True, related_name='campanhas_segmentadas')
    subcategorias = models.ManyToManyField('taxonomy.Subcategoria', blank=True, related_name='campanhas_segmentadas')
    cnaes = models.ManyToManyField('organizations.CNAE', blank=True, related_name='campanhas_segmentadas')
    termos = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = '"advertising"."advertising_segmentacao_tb"'

    def clean(self):
        if not isinstance(self.termos, list) or any(not isinstance(t, str) or not t.strip() for t in self.termos):
            raise ValidationError({'termos': 'Termos devem ser uma lista de textos não vazios.'})
        self.termos = list(dict.fromkeys(t.strip().casefold()[:80] for t in self.termos))[:50]

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Criativo(models.Model):
    class Tipo(models.TextChoices):
        IMAGEM = 'IMAGEM', 'Imagem'
        VIDEO = 'VIDEO', 'Vídeo'
        TEXTO = 'TEXTO', 'Texto'

    campanha = models.ForeignKey(Campanha, on_delete=models.CASCADE, related_name='criativos')
    posicionamento = models.ForeignKey(
        Posicionamento, on_delete=models.PROTECT, related_name='criativos',
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    titulo = models.CharField(max_length=120)
    texto = models.TextField(blank=True)
    imagem = models.ImageField(upload_to='advertising/criativos/', blank=True)
    imagem_mobile = models.ImageField(upload_to='advertising/criativos/mobile/', blank=True)
    video = models.FileField(upload_to='advertising/criativos/videos/', blank=True)
    video_mobile = models.FileField(upload_to='advertising/criativos/videos/mobile/', blank=True)
    url_destino = models.URLField()
    ativo = models.BooleanField(default=True)
    aprovado = models.BooleanField(default=False, editable=False)

    class Meta:
        db_table = '"advertising"."advertising_criativo_tb"'
        indexes = [
            models.Index(
                fields=['campanha', 'posicionamento', 'ativo', 'aprovado'],
                name='adv_criativo_slot_idx',
            ),
        ]

    def clean(self):
        if self.tipo == self.Tipo.IMAGEM and not self.imagem:
            raise ValidationError({'imagem': 'Criativo de imagem exige arquivo.'})
        if self.tipo == self.Tipo.VIDEO and not self.video:
            raise ValidationError({'video': 'Criativo de vídeo exige arquivo.'})
        if self.tipo == self.Tipo.TEXTO and not self.texto.strip():
            raise ValidationError({'texto': 'Informe o conteúdo do criativo.'})
        if self.tipo == self.Tipo.TEXTO and strip_tags(self.texto) != self.texto:
            raise ValidationError({'texto': 'HTML não é permitido em criativos de texto.'})
        if self.campanha_id and self.posicionamento_id:
            if not self.campanha.posicionamentos.filter(pk=self.posicionamento_id).exists():
                raise ValidationError({
                    'posicionamento': 'O posicionamento deve pertencer à campanha.',
                })
            self._validar_posicionamento(self.posicionamento)

    def _validar_posicionamento(self, posicionamento):
        permitidos = {
            self.Tipo.IMAGEM: posicionamento.permite_imagem,
            self.Tipo.VIDEO: posicionamento.permite_video,
            self.Tipo.TEXTO: posicionamento.permite_texto,
        }
        if not permitidos.get(self.tipo, False):
            raise ValidationError({'tipo': f'Tipo incompatível com {posicionamento.nome}.'})
        if self.tipo == self.Tipo.TEXTO:
            return
        desktop = self.imagem if self.tipo == self.Tipo.IMAGEM else self.video
        mobile = self.imagem_mobile if self.tipo == self.Tipo.IMAGEM else self.video_mobile
        self._validar_arquivo(desktop, posicionamento, variante='desktop')
        if mobile:
            self._validar_arquivo(mobile, posicionamento, variante='mobile')

    def _validar_arquivo(self, arquivo, posicionamento, *, variante):
        if not arquivo:
            return
        if arquivo.size > posicionamento.tamanho_maximo_bytes:
            raise ValidationError({
                self._campo_midia(variante):
                    f'Arquivo {variante} excede o tamanho máximo do posicionamento.',
            })
        extensao = arquivo.name.rsplit('.', 1)[-1].lower() if '.' in arquivo.name else ''
        formatos = posicionamento.formatos_permitidos
        if formatos and extensao not in formatos:
            raise ValidationError({
                self._campo_midia(variante):
                    f'Formato do arquivo {variante} não permitido para o posicionamento.',
            })
        mime = (
            getattr(arquivo, 'content_type', '')
            or getattr(arquivo.file, 'content_type', '')
            or mimetypes.guess_type(arquivo.name)[0]
            or ''
        )
        prefixo = 'image/' if self.tipo == self.Tipo.IMAGEM else 'video/'
        if not mime.startswith(prefixo):
            raise ValidationError({
                self._campo_midia(variante):
                    f'MIME do arquivo {variante} incompatível com o tipo de criativo.',
            })
        if self.tipo == self.Tipo.IMAGEM and posicionamento.dimensoes_obrigatorias:
            largura = posicionamento.largura if variante == 'desktop' else posicionamento.largura_mobile
            altura = posicionamento.altura if variante == 'desktop' else posicionamento.altura_mobile
            # A variante mobile é opcional; quando enviada e sem dimensões móveis
            # configuradas, conserva a validação segura pelas regras gerais do slot.
            if largura and altura and (arquivo.width != largura or arquivo.height != altura):
                raise ValidationError({
                    self._campo_midia(variante):
                        f'Imagem {variante} deve ter {largura} × {altura} px.',
                })

    def _campo_midia(self, variante):
        base = 'imagem' if self.tipo == self.Tipo.IMAGEM else 'video'
        return f'{base}_mobile' if variante == 'mobile' else base

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class EntregaPublicidade(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    campanha = models.ForeignKey(Campanha, on_delete=models.PROTECT, related_name='entregas')
    criativo = models.ForeignKey(Criativo, on_delete=models.PROTECT, related_name='entregas')
    posicionamento = models.ForeignKey(Posicionamento, on_delete=models.PROTECT, related_name='entregas')
    visitante_hash = models.CharField(max_length=64, db_index=True)
    contexto = models.CharField(max_length=80)
    entregue_em = models.DateTimeField(auto_now_add=True)
    clicado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = '"advertising"."advertising_entrega_tb"'
        indexes = [models.Index(fields=['visitante_hash', 'entregue_em'], name='adv_entrega_visit_date_idx')]

    def clean(self):
        errors = {}
        if self.criativo_id and self.campanha_id and self.criativo.campanha_id != self.campanha_id:
            errors['criativo'] = 'O criativo deve pertencer à campanha da entrega.'
        if (
            self.criativo_id and self.posicionamento_id
            and self.criativo.posicionamento_id != self.posicionamento_id
        ):
            errors['posicionamento'] = 'O criativo deve pertencer ao posicionamento da entrega.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class AuditoriaPublicidade(models.Model):
    campanha = models.ForeignKey(Campanha, on_delete=models.PROTECT, related_name='auditoria')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    acao = models.CharField(max_length=48)
    detalhes = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"advertising"."advertising_auditoria_tb"'
