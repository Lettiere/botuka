import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

from apps.core.models import SoftDeleteModel, TimeStampedModel, UUIDModel


YOUTUBE_RE = re.compile(
    r'^(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)'
    r'([A-Za-z0-9_-]{11})(?:[?&/].*)?$'
)


def youtube_id(url):
    match = YOUTUBE_RE.match((url or '').strip())
    if not match:
        raise ValidationError('Informe uma URL válida do YouTube.')
    return match.group(1)


class TurismoStatus(models.TextChoices):
    RASCUNHO = 'RASCUNHO', 'Rascunho'
    EM_ANALISE = 'EM_ANALISE', 'Em análise'
    PUBLICADO = 'PUBLICADO', 'Publicado'
    REJEITADO = 'REJEITADO', 'Rejeitado'
    PAUSADO = 'PAUSADO', 'Pausado'
    ARQUIVADO = 'ARQUIVADO', 'Arquivado'


class LocalizacaoVisibilidade(models.TextChoices):
    PUBLICA = 'PUBLICA', 'Pública'
    APROXIMADA = 'APROXIMADA', 'Aproximada'
    PRIVADA = 'PRIVADA', 'Privada'


class SituacaoLocal(models.TextChoices):
    ABERTO = 'ABERTO', 'Aberto à visitação'
    TEMPORARIAMENTE_FECHADO = 'TEMP_FECHADO', 'Temporariamente fechado'
    EM_MANUTENCAO = 'MANUTENCAO', 'Em manutenção'
    SAZONAL = 'SAZONAL', 'Funcionamento sazonal'


class PrecisaoLocalizacao(models.TextChoices):
    EXATA = 'EXATA', 'Coordenada exata'
    ESTIMADA = 'ESTIMADA', 'Coordenada estimada'
    APROXIMADA = 'APROXIMADA', 'Somente região aproximada'


class CategoriaTurismo(UUIDModel, TimeStampedModel, SoftDeleteModel):
    nome = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    pai = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='subcategorias',
    )
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'nome']
        constraints = [
            models.UniqueConstraint(fields=['pai', 'nome'], name='tourism_categoria_pai_nome_uk'),
        ]

    def __str__(self):
        return f'{self.pai.nome} — {self.nome}' if self.pai_id else self.nome


class EstruturaTurismo(UUIDModel, TimeStampedModel, SoftDeleteModel):
    nome = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class ServicoTurismo(UUIDModel, TimeStampedModel, SoftDeleteModel):
    nome = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class TurismoAutoriaModel(UUIDModel, TimeStampedModel, SoftDeleteModel):
    usuario_criador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='%(app_label)s_%(class)s_criados',
    )
    usuario_atualizador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='%(app_label)s_%(class)s_atualizados',
    )
    publicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_publicados',
    )
    publicado_em = models.DateTimeField(null=True, blank=True)
    moderado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_moderados',
    )
    moderado_em = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=TurismoStatus.choices,
        default=TurismoStatus.RASCUNHO, db_index=True,
    )

    class Meta:
        abstract = True


class LocalTuristico(TurismoAutoriaModel):
    nome = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    categoria = models.ForeignKey(
        CategoriaTurismo, on_delete=models.PROTECT, null=True, blank=True,
        related_name='locais',
    )
    categoria_legada = models.CharField(max_length=100, blank=True)
    descricao_curta = models.CharField(max_length=240)
    descricao_completa = models.TextField()
    historia = models.TextField(blank=True)
    situacao_local = models.CharField(max_length=16, choices=SituacaoLocal.choices, blank=True)
    etapa_atual = models.PositiveSmallIntegerField(default=1)
    imagem_principal = models.ImageField(upload_to='turismo/locais/capas/', blank=True)
    imagem_principal_webp = models.ImageField(upload_to='turismo/locais/capas/webp/', blank=True, editable=False)
    imagem_thumbnail = models.ImageField(upload_to='turismo/locais/capas/thumbs/', blank=True, editable=False)
    imagem_texto_alternativo = models.CharField(max_length=180, blank=True)
    imagem_credito = models.CharField(max_length=180, blank=True)
    imagem_legenda = models.CharField(max_length=180, blank=True)
    imagem_foco_horizontal = models.PositiveSmallIntegerField(default=50)
    imagem_foco_vertical = models.PositiveSmallIntegerField(default=50)
    destaque_home = models.BooleanField(default=False)
    gratuito = models.BooleanField(default=True)
    valor_informativo = models.CharField(max_length=120, blank=True)
    valor_inteiro = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    valor_meia = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    valor_infantil = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    link_compra = models.URLField(blank=True)
    horario = models.TextField(blank=True)
    dias_funcionamento = models.CharField(max_length=180, blank=True)
    agendamento_necessario = models.BooleanField(default=False)
    agendamento_telefone = models.CharField(max_length=30, blank=True)
    agendamento_whatsapp = models.CharField(max_length=30, blank=True)
    agendamento_site = models.URLField(blank=True)
    agendamento_link = models.URLField(blank=True)
    agendamento_instrucoes = models.TextField(blank=True)
    agendamento_antecedencia_horas = models.PositiveIntegerField(null=True, blank=True)
    acessibilidade = models.TextField(blank=True)
    estacionamento = models.TextField(blank=True)
    estrutura_disponivel = models.TextField(blank=True)
    banheiros = models.TextField(blank=True)
    alimentacao = models.TextField(blank=True)
    seguranca = models.TextField(blank=True)
    regras_local = models.TextField(blank=True)
    aceita_animais = models.BooleanField(default=False)
    recomendacoes = models.TextField(blank=True)
    melhor_periodo = models.CharField(max_length=180, blank=True)
    duracao_media_visita = models.CharField(max_length=120, blank=True)
    empresa_responsavel = models.ForeignKey(
        'organizations.Empresa', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='locais_turisticos',
    )
    telefone_publico = models.CharField(max_length=30, blank=True)
    whatsapp_publico = models.CharField(max_length=30, blank=True)
    email_publico = models.EmailField(blank=True)
    site = models.URLField(blank=True)
    redes_sociais = models.JSONField(default=dict, blank=True)
    cep = models.CharField(max_length=9, blank=True)
    logradouro = models.CharField(max_length=180, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    complemento = models.CharField(max_length=120, blank=True)
    bairro = models.CharField(max_length=120, blank=True)
    cidade = models.CharField(max_length=120, default='Botucatu')
    estado = models.CharField(max_length=2, default='SP')
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    ponto_referencia = models.CharField(max_length=180, blank=True)
    precisao = models.CharField(max_length=12, choices=PrecisaoLocalizacao.choices, blank=True)
    visibilidade_localizacao = models.CharField(
        max_length=12, choices=LocalizacaoVisibilidade.choices,
        default=LocalizacaoVisibilidade.PUBLICA,
    )
    guias_relacionados = models.ManyToManyField(
        'GuiaTuristico', related_name='locais_relacionados', blank=True,
    )
    empresas_relacionadas = models.ManyToManyField(
        'organizations.Empresa', related_name='locais_turisticos_relacionados', blank=True,
    )
    estruturas = models.ManyToManyField(
        EstruturaTurismo, related_name='locais', blank=True,
    )
    servicos_disponiveis = models.ManyToManyField(
        ServicoTurismo, related_name='locais', blank=True,
    )
    responsavel_administrativo = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='locais_turisticos_responsaveis',
    )

    class Meta:
        ordering = ['nome']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome

    @property
    def progresso_cadastro(self):
        return min(100, max(10, self.etapa_atual * 10))

    @property
    def nome_etapa_atual(self):
        nomes = (
            'Identificação', 'Categoria', 'Localização', 'Informações práticas',
            'Imagem principal', 'Galeria de imagens', 'Vídeos e playlists',
            'Contatos e redes sociais', 'Relações e responsáveis',
            'Revisão e publicação',
        )
        return nomes[min(max(self.etapa_atual, 1), 10) - 1]


class GuiaTuristico(TurismoAutoriaModel):
    class Tipo(models.TextChoices):
        PF = 'PF', 'Pessoa física'
        PJ = 'PJ', 'Pessoa jurídica'

    tipo = models.CharField(max_length=2, choices=Tipo.choices)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='guias_turismo')
    empresa = models.ForeignKey(
        'organizations.Empresa', on_delete=models.PROTECT, null=True, blank=True,
        related_name='guias_turismo',
    )
    slug = models.SlugField(max_length=200, unique=True)
    nome_profissional = models.CharField(max_length=180)
    foto = models.ImageField(upload_to='turismo/guias/', blank=True)
    apresentacao = models.TextField()
    idiomas = models.CharField(max_length=300, blank=True)
    especialidades = models.CharField(max_length=300, blank=True)
    regioes_atendidas = models.CharField(max_length=300, blank=True)
    telefone_publico = models.CharField(max_length=30, blank=True)
    whatsapp_publico = models.CharField(max_length=30, blank=True)
    site = models.URLField(blank=True)
    redes_sociais = models.JSONField(default=dict, blank=True)
    registro_profissional_publico = models.CharField(max_length=80, blank=True)
    verificado = models.BooleanField(default=False)
    visibilidade_localizacao = models.CharField(
        max_length=12, choices=LocalizacaoVisibilidade.choices,
        default=LocalizacaoVisibilidade.PRIVADA,
    )

    def clean(self):
        if self.tipo == self.Tipo.PJ and not self.empresa_id:
            raise ValidationError({'empresa': 'Uma empresa é obrigatória para guia pessoa jurídica.'})
        if self.tipo == self.Tipo.PF and self.empresa_id:
            raise ValidationError({'empresa': 'Guia pessoa física não deve possuir empresa.'})

    def __str__(self):
        return self.nome_profissional


class TurismoFoto(TurismoAutoriaModel):
    local = models.ForeignKey(LocalTuristico, on_delete=models.CASCADE, related_name='fotos')
    imagem = models.ImageField(upload_to='turismo/locais/')
    legenda = models.CharField(max_length=180, blank=True)
    texto_alternativo = models.CharField(max_length=180, blank=True)
    credito = models.CharField(max_length=180, blank=True)
    principal = models.BooleanField(default=False)
    ordem = models.PositiveIntegerField(default=0)


class TurismoVideo(TurismoAutoriaModel):
    local = models.ForeignKey(LocalTuristico, on_delete=models.CASCADE, null=True, blank=True, related_name='videos')
    guia = models.ForeignKey(GuiaTuristico, on_delete=models.CASCADE, null=True, blank=True, related_name='videos')
    empresa = models.ForeignKey(
        'EmpresaTuristica', on_delete=models.CASCADE, null=True, blank=True,
        related_name='videos',
    )
    roteiro = models.ForeignKey(
        'RoteiroTuristico', on_delete=models.CASCADE, null=True, blank=True,
        related_name='videos',
    )
    experiencia = models.ForeignKey(
        'ExperienciaTuristica', on_delete=models.CASCADE, null=True, blank=True,
        related_name='videos',
    )
    titulo = models.CharField(max_length=180)
    descricao = models.TextField(blank=True)
    url_youtube = models.URLField()
    youtube_video_id = models.CharField(max_length=11, editable=False, db_index=True)
    thumbnail = models.URLField(blank=True)
    ordem = models.PositiveIntegerField(default=0)
    destaque = models.BooleanField(default=False)

    def clean(self):
        self.youtube_video_id = youtube_id(self.url_youtube)
        vinculos = (self.local_id, self.guia_id, self.empresa_id, self.roteiro_id, self.experiencia_id)
        if sum(bool(value) for value in vinculos) != 1:
            raise ValidationError('Vincule o vídeo a exatamente um conteúdo turístico.')

    def save(self, *args, **kwargs):
        self.youtube_video_id = youtube_id(self.url_youtube)
        if not self.thumbnail:
            self.thumbnail = f'https://i.ytimg.com/vi/{self.youtube_video_id}/hqdefault.jpg'
        super().save(*args, **kwargs)


class TurismoPlaylist(TurismoAutoriaModel):
    titulo = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    descricao = models.TextField(blank=True)
    capa = models.ImageField(upload_to='turismo/playlists/', blank=True)
    url_youtube = models.URLField(blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    categoria = models.CharField(max_length=100, blank=True)
    local = models.ForeignKey(LocalTuristico, on_delete=models.SET_NULL, null=True, blank=True, related_name='playlists')
    guia = models.ForeignKey(GuiaTuristico, on_delete=models.SET_NULL, null=True, blank=True, related_name='playlists')
    roteiro = models.ForeignKey('RoteiroTuristico', on_delete=models.SET_NULL, null=True, blank=True, related_name='playlists')
    experiencia = models.ForeignKey('ExperienciaTuristica', on_delete=models.SET_NULL, null=True, blank=True, related_name='playlists')
    empresa = models.ForeignKey(
        'EmpresaTuristica', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='playlists',
    )


class TurismoPlaylistVideo(UUIDModel, TimeStampedModel):
    playlist = models.ForeignKey(TurismoPlaylist, on_delete=models.CASCADE, related_name='itens')
    video = models.ForeignKey(TurismoVideo, on_delete=models.CASCADE, related_name='playlists')
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem']
        constraints = [models.UniqueConstraint(fields=['playlist', 'video'], name='tourism_playlist_video_uk')]


class RoteiroTuristico(TurismoAutoriaModel):
    titulo = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    resumo = models.CharField(max_length=240)
    descricao = models.TextField()
    duracao = models.CharField(max_length=80, blank=True)
    dificuldade = models.CharField(max_length=80, blank=True)
    custo_estimado = models.CharField(max_length=120, blank=True)
    publico_indicado = models.CharField(max_length=180, blank=True)
    mapa_url = models.URLField(blank=True)
    locais = models.ManyToManyField(LocalTuristico, related_name='roteiros', blank=True)
    guias = models.ManyToManyField(GuiaTuristico, related_name='roteiros', blank=True)


class ExperienciaTuristica(TurismoAutoriaModel):
    titulo = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    resumo = models.CharField(max_length=240)
    descricao = models.TextField()
    local = models.ForeignKey(LocalTuristico, on_delete=models.SET_NULL, null=True, blank=True, related_name='experiencias')
    guia = models.ForeignKey(GuiaTuristico, on_delete=models.SET_NULL, null=True, blank=True, related_name='experiencias')
    empresa = models.ForeignKey(
        'EmpresaTuristica', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='experiencias',
    )
    duracao = models.CharField(max_length=80, blank=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    capacidade = models.PositiveIntegerField(null=True, blank=True)
    datas = models.TextField(blank=True)
    acessibilidade = models.TextField(blank=True)
    requisitos = models.TextField(blank=True)
    contato = models.CharField(max_length=180, blank=True)


class EmpresaTuristica(TurismoAutoriaModel):
    class TipoAtuacao(models.TextChoices):
        AGENCIA = 'AGENCIA', 'Agência'
        OPERADORA = 'OPERADORA', 'Operadora'
        HOSPEDAGEM = 'HOSPEDAGEM', 'Hospedagem'
        GUIA_PJ = 'GUIA_PJ', 'Guia PJ'
        TRANSPORTE = 'TRANSPORTE', 'Transporte turístico'
        GASTRONOMIA = 'GASTRONOMIA', 'Gastronomia'
        EVENTOS = 'EVENTOS', 'Eventos'
        RURAL = 'RURAL', 'Turismo rural'
        EXPERIENCIA = 'EXPERIENCIA', 'Experiência'
        PASSEIO = 'PASSEIO', 'Passeio'
        LOCACAO = 'LOCACAO', 'Locação'
        APOIO = 'APOIO', 'Apoio ao turista'

    empresa = models.OneToOneField(
        'organizations.Empresa', on_delete=models.CASCADE,
        related_name='perfil_turistico',
    )
    tipo_atuacao = models.CharField(max_length=20, choices=TipoAtuacao.choices)
    apresentacao = models.TextField(blank=True)
    regioes_atendidas = models.CharField(max_length=300, blank=True)
    contato_publico = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ['empresa__nome_fantasia']

    def __str__(self):
        return self.empresa.nome_exibicao


class ContatoTurismo(TurismoAutoriaModel):
    class Tipo(models.TextChoices):
        TELEFONE = 'TELEFONE', 'Telefone'
        WHATSAPP = 'WHATSAPP', 'WhatsApp'
        EMAIL = 'EMAIL', 'E-mail'
        SITE = 'SITE', 'Site'
        AGENDAMENTO = 'AGENDAMENTO', 'Link de agendamento'
        OUTRO = 'OUTRO', 'Outro'

    local = models.ForeignKey(LocalTuristico, on_delete=models.CASCADE, related_name='contatos')
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    valor = models.CharField(max_length=240)
    nome_exibicao = models.CharField(max_length=100, blank=True)
    publico = models.BooleanField(default=True)
    principal = models.BooleanField(default=False)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'tipo']


class RedeSocialTurismo(TurismoAutoriaModel):
    class Tipo(models.TextChoices):
        INSTAGRAM = 'INSTAGRAM', 'Instagram'
        FACEBOOK = 'FACEBOOK', 'Facebook'
        YOUTUBE = 'YOUTUBE', 'YouTube'
        TIKTOK = 'TIKTOK', 'TikTok'
        LINKEDIN = 'LINKEDIN', 'LinkedIn'
        X = 'X', 'X / Twitter'
        PINTEREST = 'PINTEREST', 'Pinterest'
        OUTRA = 'OUTRA', 'Outra rede'

    local = models.ForeignKey(LocalTuristico, on_delete=models.CASCADE, related_name='redes_sociais_itens')
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    url = models.URLField()
    nome_exibicao = models.CharField(max_length=100, blank=True)
    publico = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'tipo']
