import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import SoftDeleteModel, TimeStampedModel, UUIDModel
from apps.core.services.rich_text import sanitizar_html_rico


class SetorProduto(UUIDModel, TimeStampedModel):
    nome = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    descricao = models.TextField(blank=True)
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class CategoriaProduto(UUIDModel, TimeStampedModel):
    setor = models.ForeignKey(SetorProduto, on_delete=models.PROTECT, null=True, blank=True, related_name='categorias')
    nome = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    descricao = models.TextField(blank=True)
    icone = models.CharField(max_length=80, blank=True)
    ordem = models.PositiveIntegerField(default=0)
    exige_segmento = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    removido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(fields=['slug'], condition=models.Q(ativo=True), name='products_category_active_slug_uk'),
            models.UniqueConstraint(fields=['nome'], condition=models.Q(ativo=True), name='products_category_active_name_uk'),
        ]

    def __str__(self):
        return f'{self.setor} / {self.nome}' if self.setor_id else self.nome


class FamiliaProduto(UUIDModel, TimeStampedModel):
    categoria = models.ForeignKey(CategoriaProduto, on_delete=models.PROTECT, related_name='familias')
    nome = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    descricao = models.TextField(blank=True)
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    removido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(fields=['categoria', 'slug'], name='products_family_category_slug_uk'),
        ]

    def __str__(self):
        return f'{self.categoria} / {self.nome}'


class TipoProduto(UUIDModel, TimeStampedModel):
    familia = models.ForeignKey(FamiliaProduto, on_delete=models.PROTECT, related_name='tipos')
    nome = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    descricao = models.TextField(blank=True)
    ordem = models.PositiveIntegerField(default=0)
    permite_segmento = models.BooleanField(default=False)
    exige_segmento = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    removido_em = models.DateTimeField(null=True, blank=True)
    segmentos = models.ManyToManyField('SegmentoProduto', through='TipoProdutoSegmento', related_name='tipos')

    class Meta:
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(fields=['familia', 'slug'], name='products_type_family_slug_uk'),
        ]

    def __str__(self):
        return f'{self.familia} / {self.nome}'

    def clean(self):
        if self.exige_segmento and not self.permite_segmento:
            raise ValidationError({'exige_segmento': 'Um tipo só pode exigir segmento quando permite segmentos.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class SegmentoProduto(UUIDModel, TimeStampedModel):
    nome = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    descricao = models.TextField(blank=True)
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    removido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome


class TipoProdutoSegmento(UUIDModel, TimeStampedModel):
    tipo_produto = models.ForeignKey(TipoProduto, on_delete=models.CASCADE, related_name='segmentos_relacionados')
    segmento = models.ForeignKey(SegmentoProduto, on_delete=models.PROTECT, related_name='tipos_relacionados')
    obrigatorio = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'segmento__nome']
        constraints = [
            models.UniqueConstraint(fields=['tipo_produto', 'segmento'], name='products_type_segment_uk'),
        ]


class AtributoProduto(UUIDModel, TimeStampedModel):
    class Tipo(models.TextChoices):
        TEXTO = 'TEXTO', 'Texto'
        INTEIRO = 'INTEIRO', 'Número inteiro'
        DECIMAL = 'DECIMAL', 'Número decimal'
        BOOLEANO = 'BOOLEANO', 'Sim ou não'
        ESCOLHA = 'ESCOLHA', 'Escolha'

    categoria_taxonomia = models.ForeignKey(
        CategoriaProduto, on_delete=models.CASCADE, related_name='atributos',
    )
    nome = models.CharField(max_length=100)
    chave = models.SlugField(max_length=100)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.TEXTO)
    opcoes = models.JSONField(default=list, blank=True)
    obrigatorio = models.BooleanField(default=False)
    filtravel = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['ordem', 'nome']
        constraints = [
            models.UniqueConstraint(
                fields=['categoria_taxonomia', 'chave'], name='products_attribute_category_key_uk',
            ),
        ]

    def __str__(self):
        return self.nome


class Produto(UUIDModel, TimeStampedModel, SoftDeleteModel):
    class Status(models.TextChoices):
        RASCUNHO='RASCUNHO','Rascunho'; EM_ANALISE='EM_ANALISE','Em análise'
        APROVADO='APROVADO','Aprovado'; PUBLICADO='PUBLICADO','Publicado'
        PAUSADO='PAUSADO','Pausado'; REJEITADO='REJEITADO','Rejeitado'
        ESGOTADO='ESGOTADO','Esgotado'; INDISPONIVEL='INDISPONIVEL','Indisponível'
        ARQUIVADO='ARQUIVADO','Arquivado'
    class TitularTipo(models.TextChoices):
        PESSOA_FISICA='PF','Pessoa física'; EMPRESA='EMPRESA','Empresa'
    class Condicao(models.TextChoices):
        NOVO='NOVO','Novo'; USADO='USADO','Usado'; RECONDICIONADO='RECONDICIONADO','Recondicionado'
    class Disponibilidade(models.TextChoices):
        DISPONIVEL='DISPONIVEL','Disponível'; SOB_ENCOMENDA='SOB_ENCOMENDA','Sob encomenda'
        ESGOTADO='ESGOTADO','Esgotado'; INDISPONIVEL='INDISPONIVEL','Indisponível'

    nome=models.CharField(max_length=220); slug=models.SlugField(max_length=250,unique=True,blank=True)
    codigo_interno=models.CharField(max_length=80,blank=True); sku=models.CharField(max_length=100,blank=True)
    categoria=models.CharField(max_length=120); subcategoria=models.CharField(max_length=120,blank=True)
    setor = models.ForeignKey(SetorProduto, on_delete=models.PROTECT, null=True, blank=True, related_name='produtos')
    categoria_taxonomia = models.ForeignKey(CategoriaProduto, on_delete=models.PROTECT, null=True, blank=True, related_name='produtos')
    familia = models.ForeignKey(FamiliaProduto, on_delete=models.PROTECT, null=True, blank=True, related_name='produtos')
    tipo_produto = models.ForeignKey(TipoProduto, on_delete=models.PROTECT, null=True, blank=True, related_name='produtos')
    segmento = models.ForeignKey(SegmentoProduto, on_delete=models.PROTECT, null=True, blank=True, related_name='produtos')
    marca=models.CharField(max_length=120,blank=True); modelo=models.CharField(max_length=120,blank=True)
    condicao=models.CharField(max_length=20,choices=Condicao.choices,default=Condicao.NOVO)
    descricao_curta=models.CharField(max_length=300); descricao_completa=models.TextField()
    tags=models.CharField(max_length=300,blank=True)
    preco=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    preco_promocional=models.DecimalField(max_digits=12,decimal_places=2,null=True,blank=True)
    moeda=models.CharField(max_length=3,default='BRL'); preco_sob_consulta=models.BooleanField(default=False)
    unidade_venda=models.CharField(max_length=80,default='unidade'); quantidade_minima=models.PositiveIntegerField(default=1)
    estoque_informativo=models.PositiveIntegerField(null=True,blank=True)
    disponibilidade=models.CharField(max_length=20,choices=Disponibilidade.choices,default=Disponibilidade.DISPONIVEL)
    aceita_encomenda=models.BooleanField(default=False)
    whatsapp=models.CharField(max_length=20,blank=True); telefone=models.CharField(max_length=20,blank=True)
    url_externa=models.URLField(blank=True,max_length=500)
    dimensoes=models.CharField(max_length=160,blank=True); peso=models.CharField(max_length=80,blank=True)
    cor=models.CharField(max_length=80,blank=True); material=models.CharField(max_length=120,blank=True)
    tamanho=models.CharField(max_length=80,blank=True); especificacoes=models.TextField(blank=True)
    garantia=models.TextField(blank=True); prazo_estimado=models.CharField(max_length=120,blank=True)
    origem=models.CharField(max_length=120,blank=True); fabricante=models.CharField(max_length=160,blank=True)
    video_url=models.URLField(blank=True,max_length=500); imagem_social=models.ImageField(upload_to='produtos/social/',blank=True)
    titulo_seo=models.CharField(max_length=70,blank=True); descricao_seo=models.CharField(max_length=160,blank=True)
    titular_tipo=models.CharField(max_length=10,choices=TitularTipo.choices)
    criador_registro=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='produtos_criados')
    proprietario=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='produtos_proprios')
    responsavel=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='produtos_responsavel')
    empresa_proprietaria=models.ForeignKey('organizations.Empresa',on_delete=models.PROTECT,null=True,blank=True,related_name='produtos')
    aprovado_por=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='produtos_aprovados')
    publicado_por=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='produtos_publicados')
    status=models.CharField(max_length=20,choices=Status.choices,default=Status.RASCUNHO,db_index=True)
    destaque=models.BooleanField(default=False); publico=models.BooleanField(default=True)
    motivo_rejeicao=models.TextField(blank=True); aprovado_em=models.DateTimeField(null=True,blank=True)
    publicado_em=models.DateTimeField(null=True,blank=True)

    class Meta:
        ordering=['-atualizado_em']; indexes=[
            models.Index(fields=['status','publico'],name='products_public_status_idx'),
            models.Index(fields=['proprietario','status'],name='products_owner_status_idx'),
            models.Index(fields=['empresa_proprietaria','status'],name='products_company_status_idx'),
        ]; constraints=[
            models.UniqueConstraint(
                fields=['codigo_interno'], condition=~models.Q(codigo_interno=''),
                name='products_internal_code_uk',
            ),
        ]

    def clean(self):
        from .services import normalizar_whatsapp
        if self.whatsapp:
            try:
                self.whatsapp = normalizar_whatsapp(self.whatsapp)
            except ValidationError as exc:
                raise ValidationError({'whatsapp': exc.message})
        self.descricao_completa=sanitizar_html_rico(self.descricao_completa)
        self.especificacoes=sanitizar_html_rico(self.especificacoes)
        self.garantia=sanitizar_html_rico(self.garantia)
        if self.titular_tipo==self.TitularTipo.PESSOA_FISICA and self.empresa_proprietaria_id:
            raise ValidationError({'empresa_proprietaria':'Produto de pessoa física não deve possuir empresa.'})
        if self.titular_tipo==self.TitularTipo.EMPRESA and not self.empresa_proprietaria_id:
            raise ValidationError({'empresa_proprietaria':'Informe a empresa proprietária.'})
        if not self.preco_sob_consulta and self.preco is None:
            raise ValidationError({'preco':'Informe o preço ou marque preço sob consulta.'})
        if self.preco_promocional is not None and self.preco is not None and self.preco_promocional >= self.preco:
            raise ValidationError({'preco_promocional':'O preço promocional deve ser menor que o preço normal.'})
        if (
            self.categoria_taxonomia_id
            and self.categoria_taxonomia.setor_id
            and self.setor_id != self.categoria_taxonomia.setor_id
        ):
            raise ValidationError({'categoria_taxonomia': 'A categoria não pertence ao setor informado.'})
        if self.familia_id and self.categoria_taxonomia_id != self.familia.categoria_id:
            raise ValidationError({'familia': 'A família não pertence à categoria informada.'})
        if self.tipo_produto_id and self.familia_id != self.tipo_produto.familia_id:
            raise ValidationError({'tipo_produto': 'O tipo não pertence à família informada.'})
        if self.tipo_produto_id:
            if self.segmento_id and not self.tipo_produto.permite_segmento:
                raise ValidationError({'segmento': 'Este tipo de produto não permite segmento.'})
            if self.tipo_produto.exige_segmento and not self.segmento_id:
                raise ValidationError({'segmento': 'Informe o segmento exigido para este tipo de produto.'})
            if self.segmento_id and not self.tipo_produto.segmentos_relacionados.filter(
                segmento_id=self.segmento_id, ativo=True, segmento__ativo=True,
            ).exists():
                raise ValidationError({'segmento': 'O segmento não é permitido para este tipo de produto.'})

    def save(self,*args,**kwargs):
        if not self.slug:
            base=slugify(self.nome)[:220] or 'produto'; value=base; number=2
            while type(self).all_objects.exclude(pk=self.pk).filter(slug=value).exists():
                value=f'{base}-{number}'; number+=1
            self.slug=value
        self.full_clean(); return super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):
        self.ativo=False; self.removido_em=timezone.now()
        self.save(update_fields=['ativo','removido_em','atualizado_em'])

    @property
    def imagem_principal(self):
        return self.imagens.filter(ativo=True,removido_em__isnull=True).order_by('-principal','ordem','pk').first()
    @property
    def preco_atual(self):
        return self.preco_promocional if self.preco_promocional is not None else self.preco
    @property
    def codigo_publico(self):
        return self.codigo_interno or f'PRD-{self.pk:06d}'
    @property
    def whatsapp_publico(self):
        from .services import whatsapp_produto
        return whatsapp_produto(self)
    def get_absolute_url(self): return reverse('products:detalhe',args=[self.slug])
    def __str__(self): return self.nome


class ProdutoImagem(UUIDModel,TimeStampedModel,SoftDeleteModel):
    produto=models.ForeignKey(Produto,on_delete=models.CASCADE,related_name='imagens')
    imagem=models.ImageField(upload_to='produtos/imagens/%Y/%m/')
    principal=models.BooleanField(default=False); legenda=models.CharField(max_length=180,blank=True)
    credito=models.CharField(max_length=180,blank=True); texto_alternativo=models.CharField(max_length=220)
    ordem=models.PositiveIntegerField(default=0)
    class Meta: ordering=['-principal','ordem','pk']


class ProdutoVideo(UUIDModel, TimeStampedModel, SoftDeleteModel):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='videos')
    url = models.URLField(max_length=500)
    youtube_id = models.CharField(max_length=20)
    titulo = models.CharField(max_length=180, blank=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['produto', 'youtube_id'], name='products_video_product_youtube_uk'),
        ]

    @property
    def embed_url(self):
        return f'https://www.youtube-nocookie.com/embed/{self.youtube_id}'

    def clean(self):
        from .forms import youtube_id
        self.youtube_id = youtube_id(self.url)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ValorAtributoProduto(UUIDModel, TimeStampedModel):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='valores_atributos')
    atributo = models.ForeignKey(AtributoProduto, on_delete=models.PROTECT, related_name='valores')
    valor = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['produto', 'atributo'], name='products_value_product_attribute_uk'),
        ]

    def clean(self):
        if self.produto_id and self.atributo_id:
            if self.produto.categoria_taxonomia_id != self.atributo.categoria_taxonomia_id:
                raise ValidationError({'atributo': 'Atributo incompatível com a categoria do produto.'})
            if self.atributo.tipo == AtributoProduto.Tipo.ESCOLHA and self.valor not in self.atributo.opcoes:
                raise ValidationError({'valor': 'Escolha inválida para este atributo.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class LimiteProdutoAdicional(UUIDModel,TimeStampedModel):
    usuario=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,null=True,blank=True,related_name='limites_produtos')
    empresa=models.ForeignKey('organizations.Empresa',on_delete=models.CASCADE,null=True,blank=True,related_name='limites_produtos')
    adicional=models.PositiveIntegerField(default=0); limite_total=models.PositiveIntegerField(null=True,blank=True)
    ilimitado=models.BooleanField(default=False); ativo=models.BooleanField(default=True)
    inicio=models.DateTimeField(default=timezone.now); fim=models.DateTimeField(null=True,blank=True)
    motivo=models.CharField(max_length=255)
    concedido_por=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='limites_produtos_concedidos')
    class Meta:
        constraints=[models.CheckConstraint(condition=(models.Q(usuario__isnull=False,empresa__isnull=True)|models.Q(usuario__isnull=True,empresa__isnull=False)),name='products_limit_one_owner_ck')]


class AuditoriaProduto(UUIDModel,TimeStampedModel):
    produto=models.ForeignKey(Produto,on_delete=models.PROTECT,null=True,blank=True,related_name='auditoria')
    usuario=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True)
    acao=models.CharField(max_length=60); dados=models.JSONField(default=dict,blank=True)
    class Meta: ordering=['-criado_em']


class BloqueioNegociacao(UUIDModel, TimeStampedModel):
    bloqueador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bloqueios_realizados')
    bloqueado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bloqueios_recebidos')
    motivo = models.CharField(max_length=255, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['bloqueador', 'bloqueado'], name='products_negotiation_block_uk'),
            models.CheckConstraint(condition=~models.Q(bloqueador=models.F('bloqueado')), name='products_negotiation_block_self_ck'),
        ]


class Conversa(UUIDModel, TimeStampedModel, SoftDeleteModel):
    class Status(models.TextChoices):
        ATIVA = 'ATIVA', 'Ativa'
        ENCERRADA = 'ENCERRADA', 'Encerrada'
        BLOQUEADA = 'BLOQUEADA', 'Bloqueada'

    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='conversas')
    comprador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='conversas_comprador')
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='conversas_vendedor')
    empresa = models.ForeignKey('organizations.Empresa', on_delete=models.PROTECT, null=True, blank=True, related_name='conversas_produtos')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ATIVA, db_index=True)
    ultima_interacao = models.DateTimeField(default=timezone.now, db_index=True)
    encerrada_em = models.DateTimeField(null=True, blank=True)
    bloqueada_em = models.DateTimeField(null=True, blank=True)
    motivo_bloqueio = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-ultima_interacao']
        constraints = [
            models.UniqueConstraint(
                fields=['produto', 'comprador', 'vendedor'],
                condition=models.Q(status='ATIVA', removido_em__isnull=True),
                name='products_active_conversation_uk',
            ),
            models.CheckConstraint(condition=~models.Q(comprador=models.F('vendedor')), name='products_conversation_participants_ck'),
        ]

    def usuario_participa(self, user):
        return user.is_authenticated and user.pk in (self.comprador_id, self.vendedor_id)


class MensagemConversa(UUIDModel, TimeStampedModel):
    class Tipo(models.TextChoices):
        TEXTO = 'TEXTO', 'Texto'
        SISTEMA = 'SISTEMA', 'Sistema'

    conversa = models.ForeignKey(Conversa, on_delete=models.PROTECT, related_name='mensagens')
    remetente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='mensagens_produtos')
    conteudo = models.TextField(max_length=2000)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.TEXTO)
    lida_em = models.DateTimeField(null=True, blank=True)
    removida_em = models.DateTimeField(null=True, blank=True)
    denunciada = models.BooleanField(default=False)
    auditoria = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['criado_em']

    def clean(self):
        if self.conversa_id and self.remetente_id not in (self.conversa.comprador_id, self.conversa.vendedor_id):
            raise ValidationError({'remetente': 'Somente participantes podem enviar mensagens.'})
        if self.conversa_id and self.conversa.status != Conversa.Status.ATIVA:
            raise ValidationError({'conversa': 'A conversa não está ativa.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        result = super().save(*args, **kwargs)
        Conversa.objects.filter(pk=self.conversa_id).update(ultima_interacao=self.criado_em)
        return result


class DenunciaNegociacao(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        ABERTA = 'ABERTA', 'Aberta'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        ENCERRADA = 'ENCERRADA', 'Encerrada'

    denunciante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='denuncias_produtos')
    denunciado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='denuncias_produtos_recebidas')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, null=True, blank=True, related_name='denuncias')
    conversa = models.ForeignKey(Conversa, on_delete=models.PROTECT, null=True, blank=True, related_name='denuncias')
    mensagem = models.ForeignKey(MensagemConversa, on_delete=models.PROTECT, null=True, blank=True, related_name='denuncias')
    motivo = models.CharField(max_length=120)
    descricao = models.TextField(max_length=2000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ABERTA, db_index=True)
    dados_auditoria = models.JSONField(default=dict, blank=True)


class LogVerificacaoVendedor(UUIDModel, TimeStampedModel):
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='verificacoes_negociacao')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='verificacoes_vendedor')
    comprador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='verificacoes_comprador')
    permitido = models.BooleanField()
    codigo = models.CharField(max_length=60)
    detalhes = models.JSONField(default=dict, blank=True)
