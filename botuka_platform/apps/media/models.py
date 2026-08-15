import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from apps.core.domain import SoftDeleteMixin, texto_sem_html, validar_imagem_publica
from apps.core.public_links import TipoLink, normalizar_link_publico
from apps.core.utils import gerar_slug_unico


class Canal(SoftDeleteMixin):
    id=models.BigAutoField(primary_key=True,db_column='media_canal_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='media_canal_uuid')
    nome=models.CharField(max_length=150,db_column='media_canal_nome'); slug=models.SlugField(max_length=180,unique=True,blank=True,db_column='media_canal_slug')
    descricao=models.TextField(blank=True,db_column='media_canal_descricao'); plataforma=models.CharField(max_length=40,default='YOUTUBE',db_column='media_canal_plataforma')
    identificador_externo=models.CharField(max_length=150,blank=True,db_column='media_canal_identificador_externo'); url=models.URLField(blank=True,db_column='media_canal_url')
    logotipo=models.ImageField(upload_to='media/canais/logos/',blank=True,validators=[validar_imagem_publica],db_column='media_canal_logotipo'); capa=models.ImageField(upload_to='media/canais/capas/',blank=True,validators=[validar_imagem_publica],db_column='media_canal_capa')
    youtube_url=models.URLField(blank=True,max_length=500,db_column='media_canal_youtube_url'); instagram_url=models.URLField(blank=True,max_length=500,db_column='media_canal_instagram_url'); facebook_url=models.URLField(blank=True,max_length=500,db_column='media_canal_facebook_url'); tiktok_url=models.URLField(blank=True,max_length=500,db_column='media_canal_tiktok_url'); site_url=models.URLField(blank=True,max_length=500,db_column='media_canal_site_url')
    proprietario=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True,related_name='canais_yubotuka',db_column='media_canal_fk_proprietario'); ordem=models.PositiveIntegerField(default=0,db_column='media_canal_ordem'); destaque=models.BooleanField(default=False,db_column='media_canal_destaque')
    oficial=models.BooleanField(default=False,db_column='media_canal_oficial'); ativo=models.BooleanField(default=True,db_column='media_canal_ativo')
    criado_em=models.DateTimeField(auto_now_add=True,db_column='media_canal_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='media_canal_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='media_canal_excluido_em')
    class Meta: db_table='"media"."media_canal_tb"'; ordering=['nome']
    def save(self,*a,**kw):
        if not self.slug:self.slug=gerar_slug_unico(self,self.nome)
        self.full_clean(); super().save(*a,**kw)
    def __str__(self): return self.nome


class Programa(SoftDeleteMixin):
    id=models.BigAutoField(primary_key=True,db_column='media_programa_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='media_programa_uuid')
    canal=models.ForeignKey(Canal,on_delete=models.PROTECT,related_name='programas',db_column='media_programa_fk_canal'); nome=models.CharField(max_length=160,db_column='media_programa_nome'); slug=models.SlugField(max_length=190,unique=True,blank=True,db_column='media_programa_slug')
    descricao=models.TextField(blank=True,db_column='media_programa_descricao'); categoria=models.CharField(max_length=80,blank=True,db_column='media_programa_categoria')
    categoria_editorial=models.ForeignKey('CategoriaYuBotuka',on_delete=models.PROTECT,null=True,blank=True,related_name='programas_editoriais',db_column='media_programa_fk_categoria')
    apresentador=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='programas_apresentados',db_column='media_programa_fk_apresentador'); produtor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='programas_produzidos',db_column='media_programa_fk_produtor')
    imagem=models.ImageField(upload_to='media/programas/',blank=True,validators=[validar_imagem_publica],db_column='media_programa_imagem'); frequencia=models.CharField(max_length=80,blank=True,db_column='media_programa_frequencia'); duracao_media=models.DurationField(null=True,blank=True,db_column='media_programa_duracao_media'); ordem=models.PositiveIntegerField(default=0,db_column='media_programa_ordem'); ativo=models.BooleanField(default=True,db_column='media_programa_ativo')
    criado_em=models.DateTimeField(auto_now_add=True,db_column='media_programa_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='media_programa_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='media_programa_excluido_em')
    class Meta: db_table='"media"."media_programa_tb"'; ordering=['nome']
    def save(self,*a,**kw):
        if not self.slug:self.slug=gerar_slug_unico(self,self.nome)
        self.full_clean(); super().save(*a,**kw)
    def __str__(self): return self.nome


class Temporada(SoftDeleteMixin):
    id=models.BigAutoField(primary_key=True,db_column='media_temporada_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='media_temporada_uuid')
    programa=models.ForeignKey(Programa,on_delete=models.CASCADE,related_name='temporadas',db_column='media_temporada_fk_programa'); numero=models.PositiveIntegerField(db_column='media_temporada_numero'); titulo=models.CharField(max_length=160,blank=True,db_column='media_temporada_titulo'); descricao=models.TextField(blank=True,db_column='media_temporada_descricao'); capa=models.ImageField(upload_to='media/temporadas/',blank=True,validators=[validar_imagem_publica],db_column='media_temporada_capa'); data_inicial=models.DateField(null=True,blank=True,db_column='media_temporada_data_inicial'); data_final=models.DateField(null=True,blank=True,db_column='media_temporada_data_final'); ordem=models.PositiveIntegerField(default=0,db_column='media_temporada_ordem'); encerrada=models.BooleanField(default=False,db_column='media_temporada_encerrada'); ativo=models.BooleanField(default=True,db_column='media_temporada_ativo')
    criado_em=models.DateTimeField(auto_now_add=True,db_column='media_temporada_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='media_temporada_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='media_temporada_excluido_em')
    class Meta: db_table='"media"."media_temporada_tb"'; constraints=[models.UniqueConstraint(fields=['programa','numero'],condition=models.Q(ativo=True,excluido_em__isnull=True),name='media_temporada_programa_num_uk')]
    def clean(self):
        if self.data_inicial and self.data_final and self.data_final < self.data_inicial: raise ValidationError({'data_final':'A data final deve ser posterior à inicial.'})
    def save(self,*a,**kw): self.full_clean(); super().save(*a,**kw)


class Episodio(SoftDeleteMixin):
    class Tipo(models.TextChoices): VIDEO='VIDEO','Vídeo'; PODCAST='PODCAST','Podcast'; ENTREVISTA='ENTREVISTA','Entrevista'; TRANSMISSAO='TRANSMISSAO','Transmissão'; SHORT='SHORT','Short'; ESPECIAL='ESPECIAL','Especial'
    class Status(models.TextChoices): PAUTA='PAUTA','Pauta'; PRODUCAO='PRODUCAO','Produção'; GRAVADO='GRAVADO','Gravado'; EDITANDO='EDITANDO','Editando'; AGENDADO='AGENDADO','Agendado'; AO_VIVO='AO_VIVO','Ao vivo'; PUBLICADO='PUBLICADO','Publicado'; CANCELADO='CANCELADO','Cancelado'
    id=models.BigAutoField(primary_key=True,db_column='media_episodio_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='media_episodio_uuid')
    programa=models.ForeignKey(Programa,on_delete=models.PROTECT,related_name='episodios',db_column='media_episodio_fk_programa'); temporada=models.ForeignKey(Temporada,on_delete=models.SET_NULL,null=True,blank=True,related_name='episodios',db_column='media_episodio_fk_temporada')
    titulo=models.CharField(max_length=200,db_column='media_episodio_titulo'); slug=models.SlugField(max_length=230,unique=True,blank=True,db_column='media_episodio_slug'); descricao=models.TextField(blank=True,db_column='media_episodio_descricao'); numero=models.PositiveIntegerField(null=True,blank=True,db_column='media_episodio_numero'); tipo=models.CharField(max_length=20,choices=Tipo.choices,default=Tipo.VIDEO,db_column='media_episodio_tipo')
    youtube_url=models.URLField(blank=True,max_length=500,db_column='media_episodio_youtube_url'); video_id=models.CharField(max_length=20,blank=True,db_column='media_episodio_video_id'); thumbnail=models.URLField(blank=True,max_length=500,db_column='media_episodio_thumbnail'); duracao=models.DurationField(null=True,blank=True,db_column='media_episodio_duracao')
    data_gravacao=models.DateTimeField(null=True,blank=True,db_column='media_episodio_data_gravacao'); data_programada=models.DateTimeField(null=True,blank=True,db_column='media_episodio_data_programada'); publicado_em=models.DateTimeField(null=True,blank=True,db_column='media_episodio_publicado_em'); status=models.CharField(max_length=20,choices=Status.choices,default=Status.PAUTA,db_column='media_episodio_status'); destaque=models.BooleanField(default=False,db_column='media_episodio_destaque'); ativo=models.BooleanField(default=True,db_column='media_episodio_ativo')
    video_editorial=models.OneToOneField('Video',on_delete=models.SET_NULL,null=True,blank=True,related_name='episodio_legado',db_column='media_episodio_fk_video')
    criado_em=models.DateTimeField(auto_now_add=True,db_column='media_episodio_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='media_episodio_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='media_episodio_excluido_em')
    class Meta: db_table='"media"."media_episodio_tb"'; ordering=['-publicado_em','-criado_em']; indexes=[models.Index(fields=['status','ativo'],name='media_episodio_status_idx')]
    def clean(self):
        self.descricao=texto_sem_html(self.descricao)
        if self.temporada_id and self.temporada.programa_id != self.programa_id: raise ValidationError({'temporada':'A temporada deve pertencer ao programa do episódio.'})
        if self.youtube_url:
            self.youtube_url,self.video_id=normalizar_link_publico(TipoLink.YOUTUBE,self.youtube_url)
            if not self.video_id: raise ValidationError({'youtube_url':'Informe a URL de um vídeo do YouTube.'})
    def save(self,*a,**kw):
        if not self.slug:self.slug=gerar_slug_unico(self,self.titulo)
        if self.status==self.Status.PUBLICADO and not self.publicado_em:self.publicado_em=timezone.now()
        self.full_clean(); super().save(*a,**kw)
    @property
    def embed_url(self): return f'https://www.youtube-nocookie.com/embed/{self.video_id}' if self.video_id else ''
    @property
    def public_url(self): return reverse('media_public:episodio', args=[self.slug])
    def __str__(self): return self.titulo


class Pauta(SoftDeleteMixin):
    class Status(models.TextChoices): IDEIA='IDEIA','Ideia'; APROVADA='APROVADA','Aprovada'; PRODUCAO='PRODUCAO','Produção'; CONCLUIDA='CONCLUIDA','Concluída'; CANCELADA='CANCELADA','Cancelada'
    id=models.BigAutoField(primary_key=True,db_column='media_pauta_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='media_pauta_uuid'); titulo=models.CharField(max_length=200,db_column='media_pauta_titulo'); descricao=models.TextField(blank=True,db_column='media_pauta_descricao'); programa=models.ForeignKey(Programa,on_delete=models.PROTECT,related_name='pautas',db_column='media_pauta_fk_programa'); responsavel=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='pautas_media',db_column='media_pauta_fk_responsavel'); convidados=models.TextField(blank=True,db_column='media_pauta_convidados'); roteiro=models.TextField(blank=True,db_column='media_pauta_roteiro'); data_prevista=models.DateTimeField(null=True,blank=True,db_column='media_pauta_data_prevista'); status=models.CharField(max_length=20,choices=Status.choices,default=Status.IDEIA,db_column='media_pauta_status'); observacoes=models.TextField(blank=True,db_column='media_pauta_observacoes'); ativo=models.BooleanField(default=True,db_column='media_pauta_ativo'); criado_em=models.DateTimeField(auto_now_add=True,db_column='media_pauta_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='media_pauta_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='media_pauta_excluido_em')
    class Meta: db_table='"media"."media_pauta_tb"'


class Transmissao(SoftDeleteMixin):
    class Status(models.TextChoices): RASCUNHO='RASCUNHO','Rascunho'; EM_ANALISE='EM_ANALISE','Em análise'; APROVADO='APROVADO','Aprovado'; AGENDADA='AGENDADA','Agendada'; AO_VIVO='AO_VIVO','Ao vivo'; ENCERRADA='ENCERRADA','Encerrada'; CANCELADA='CANCELADA','Cancelada'; PUBLICADA='PUBLICADA','Publicada'; ARQUIVADA='ARQUIVADA','Arquivada'
    id=models.BigAutoField(primary_key=True,db_column='media_transmissao_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='media_transmissao_uuid'); episodio=models.OneToOneField(Episodio,on_delete=models.SET_NULL,null=True,blank=True,related_name='transmissao',db_column='media_transmissao_fk_episodio'); titulo=models.CharField(max_length=200,blank=True,db_column='media_transmissao_titulo'); slug=models.SlugField(max_length=230,unique=True,null=True,blank=True,editable=False,db_column='media_transmissao_slug'); descricao=models.TextField(blank=True,db_column='media_transmissao_descricao'); canal=models.ForeignKey(Canal,on_delete=models.PROTECT,null=True,blank=True,related_name='transmissoes_yubotuka',db_column='media_transmissao_fk_canal'); programa=models.ForeignKey(Programa,on_delete=models.SET_NULL,null=True,blank=True,related_name='transmissoes_yubotuka',db_column='media_transmissao_fk_programa'); categoria=models.ForeignKey('CategoriaYuBotuka',on_delete=models.PROTECT,null=True,blank=True,related_name='transmissoes_yubotuka',db_column='media_transmissao_fk_categoria'); autor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True,related_name='transmissoes_yubotuka',db_column='media_transmissao_fk_autor'); moderado_por=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True,related_name='transmissoes_yubotuka_moderadas',db_column='media_transmissao_fk_moderador'); video_resultante=models.ForeignKey('Video',on_delete=models.SET_NULL,null=True,blank=True,related_name='transmissoes_origem',db_column='media_transmissao_fk_video_resultante'); disputa=models.ForeignKey('sports.Disputa',on_delete=models.SET_NULL,null=True,blank=True,related_name='transmissoes',db_column='media_transmissao_fk_disputa'); acao_publica=models.ForeignKey('government.AcaoPublica',on_delete=models.SET_NULL,null=True,blank=True,related_name='transmissoes',db_column='media_transmissao_fk_acao'); data_prevista=models.DateTimeField(null=True,blank=True,db_column='media_transmissao_data_prevista'); inicio=models.DateTimeField(null=True,blank=True,db_column='media_transmissao_inicio'); fim=models.DateTimeField(null=True,blank=True,db_column='media_transmissao_fim'); url_ao_vivo=models.URLField(blank=True,max_length=500,db_column='media_transmissao_url'); video_id=models.CharField(max_length=20,blank=True,db_column='media_transmissao_video_id'); thumbnail=models.URLField(max_length=500,blank=True,db_column='media_transmissao_thumbnail'); local=models.CharField(max_length=180,blank=True,db_column='media_transmissao_local'); exibir_na_home=models.BooleanField(default=False,db_column='media_transmissao_exibir_home'); destaque=models.BooleanField(default=False,db_column='media_transmissao_destaque'); status=models.CharField(max_length=20,choices=Status.choices,default=Status.RASCUNHO,db_column='media_transmissao_status'); ativo=models.BooleanField(default=True,db_column='media_transmissao_ativo'); criado_em=models.DateTimeField(auto_now_add=True,db_column='media_transmissao_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='media_transmissao_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='media_transmissao_excluido_em')
    class Meta: db_table='"media"."media_transmissao_tb"'
    def clean(self):
        self.descricao=texto_sem_html(self.descricao)
        if self.inicio and self.fim and self.fim < self.inicio: raise ValidationError({'fim':'O fim deve ser posterior ao início.'})
        if self.programa_id and self.canal_id and self.programa.canal_id != self.canal_id: raise ValidationError({'programa':'O programa deve pertencer ao canal selecionado.'})
        if self.url_ao_vivo:
            self.url_ao_vivo,self.video_id=normalizar_link_publico(TipoLink.YOUTUBE,self.url_ao_vivo)
            if not self.video_id: raise ValidationError({'url_ao_vivo':'Informe uma URL válida do YouTube.'})
        if self.status == self.Status.AO_VIVO and (not self.inicio or self.inicio > timezone.now()): raise ValidationError({'status':'A transmissão só pode entrar ao vivo após o início registrado.'})
    def save(self,*a,**kw):
        if not self.titulo and self.episodio_id:self.titulo=self.episodio.titulo
        if not self.slug and self.titulo:self.slug=gerar_slug_unico(self,self.titulo)
        self.full_clean(); super().save(*a,**kw)
    @property
    def embed_url(self): return f'https://www.youtube-nocookie.com/embed/{self.video_id}' if self.video_id else ''
    @property
    def public_url(self): return reverse('media_public:transmissao',args=[self.slug]) if self.slug else ''
    def __str__(self): return self.titulo or f'Transmissão {self.pk}'


class CategoriaYuBotuka(SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column='media_categoria_id')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column='media_categoria_uuid')
    nome = models.CharField(max_length=120, db_column='media_categoria_nome')
    slug = models.SlugField(max_length=150, unique=True, blank=True, editable=False, db_column='media_categoria_slug')
    categoria_pai = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='subcategorias', db_column='media_categoria_fk_pai',
    )
    icone = models.CharField(max_length=60, blank=True, db_column='media_categoria_icone')
    cor = models.CharField(max_length=20, blank=True, db_column='media_categoria_cor')
    ordem = models.PositiveIntegerField(default=0, db_column='media_categoria_ordem')
    ativo = models.BooleanField(default=True, db_column='media_categoria_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='media_categoria_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='media_categoria_atualizado_em')
    excluido_em = models.DateTimeField(null=True, blank=True, db_column='media_categoria_excluido_em')

    class Meta:
        db_table = '"media"."media_categoria_tb"'
        ordering = ['ordem', 'nome']
        constraints = [
            models.UniqueConstraint(
                fields=['categoria_pai', 'nome'],
                condition=models.Q(excluido_em__isnull=True),
                name='media_categoria_pai_nome_uk',
            ),
        ]

    def clean(self):
        duplicada = type(self).all_objects.filter(
            categoria_pai_id=self.categoria_pai_id,
            nome__iexact=self.nome,
            excluido_em__isnull=True,
        )
        if self.pk:
            duplicada = duplicada.exclude(pk=self.pk)
        if duplicada.exists():
            raise ValidationError({'nome': 'Já existe uma categoria com este nome neste nível.'})
        if self.categoria_pai_id and self.categoria_pai_id == self.pk:
            raise ValidationError({'categoria_pai': 'Uma categoria não pode ser pai dela mesma.'})
        ancestral = self.categoria_pai
        visitados = {self.pk}
        while ancestral:
            if ancestral.pk in visitados:
                raise ValidationError({'categoria_pai': 'A hierarquia de categorias não pode possuir ciclos.'})
            visitados.add(ancestral.pk)
            ancestral = ancestral.categoria_pai

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def caminho(self):
        partes = [self.nome]
        ancestral = self.categoria_pai
        while ancestral:
            partes.insert(0, ancestral.nome)
            ancestral = ancestral.categoria_pai
        return ' › '.join(partes)

    def __str__(self):
        return self.caminho


class MotivoRejeicao(SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column='media_motivo_rejeicao_id')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column='media_motivo_rejeicao_uuid')
    nome = models.CharField(max_length=140, db_column='media_motivo_rejeicao_nome')
    descricao = models.TextField(blank=True, db_column='media_motivo_rejeicao_descricao')
    exige_complemento = models.BooleanField(default=False, db_column='media_motivo_rejeicao_exige_complemento')
    ativo = models.BooleanField(default=True, db_column='media_motivo_rejeicao_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='media_motivo_rejeicao_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='media_motivo_rejeicao_atualizado_em')
    excluido_em = models.DateTimeField(null=True, blank=True, db_column='media_motivo_rejeicao_excluido_em')

    class Meta:
        db_table = '"media"."media_motivo_rejeicao_tb"'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Video(SoftDeleteMixin):
    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        CORRECAO = 'CORRECAO', 'Em correção'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        APROVADO = 'APROVADO', 'Aprovado'
        REJEITADO = 'REJEITADO', 'Rejeitado'
        AGENDADO = 'AGENDADO', 'Agendado'
        PUBLICADO = 'PUBLICADO', 'Publicado'
        ARQUIVADO = 'ARQUIVADO', 'Arquivado'

    class Tipo(models.TextChoices):
        VIDEO = 'VIDEO', 'Vídeo'
        SHORT = 'SHORT', 'Short'
        LIVE = 'LIVE', 'Live'
        PODCAST = 'PODCAST', 'Podcast'
        ENTREVISTA = 'ENTREVISTA', 'Entrevista'
        ESPECIAL = 'ESPECIAL', 'Especial'

    class Idioma(models.TextChoices):
        PT_BR = 'PT_BR', 'Português (Brasil)'
        EN = 'EN', 'Inglês'
        ES = 'ES', 'Espanhol'
        LIBRAS = 'LIBRAS', 'Libras'
        OUTRO = 'OUTRO', 'Outro'

    class Classificacao(models.TextChoices):
        LIVRE = 'L', 'Livre'
        DEZ = '10', '10 anos'
        DOZE = '12', '12 anos'
        QUATORZE = '14', '14 anos'
        DEZESSEIS = '16', '16 anos'
        DEZOITO = '18', '18 anos'

    class Formato(models.TextChoices):
        HORIZONTAL = 'HORIZONTAL', 'Horizontal'
        VERTICAL = 'VERTICAL', 'Vertical'
        QUADRADO = 'QUADRADO', 'Quadrado'

    class Origem(models.TextChoices):
        YOUTUBE = 'YOUTUBE', 'YouTube'

    id = models.BigAutoField(primary_key=True, db_column='media_video_id')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column='media_video_uuid')
    titulo = models.CharField(max_length=200, db_column='media_video_titulo')
    slug = models.SlugField(max_length=230, unique=True, blank=True, editable=False, db_column='media_video_slug')
    descricao_curta = models.CharField(max_length=300, blank=True, db_column='media_video_descricao_curta')
    descricao = models.TextField(blank=True, db_column='media_video_descricao')
    youtube_url = models.URLField(max_length=500, db_column='media_video_youtube_url')
    video_id = models.CharField(max_length=20, blank=True, db_column='media_video_youtube_id')
    thumbnail = models.URLField(max_length=500, blank=True, db_column='media_video_thumbnail')
    duracao = models.DurationField(null=True, blank=True, db_column='media_video_duracao')
    categoria = models.ForeignKey(
        CategoriaYuBotuka, on_delete=models.PROTECT, null=True, blank=True,
        related_name='videos', db_column='media_video_fk_categoria',
    )
    canal = models.ForeignKey(
        Canal, on_delete=models.PROTECT, related_name='videos_editoriais',
        db_column='media_video_fk_canal',
    )
    programa = models.ForeignKey(
        Programa, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='videos_editoriais', db_column='media_video_fk_programa',
    )
    temporada = models.ForeignKey(
        Temporada, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='videos_editoriais', db_column='media_video_fk_temporada',
    )
    numero_episodio = models.PositiveIntegerField(null=True, blank=True, db_column='media_video_numero_episodio')
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.VIDEO, db_column='media_video_tipo')
    idioma = models.CharField(max_length=12, choices=Idioma.choices, default=Idioma.PT_BR, db_column='media_video_idioma')
    classificacao = models.CharField(max_length=3, choices=Classificacao.choices, default=Classificacao.LIVRE, db_column='media_video_classificacao')
    formato = models.CharField(max_length=20, choices=Formato.choices, default=Formato.HORIZONTAL, db_column='media_video_formato')
    origem = models.CharField(max_length=20, choices=Origem.choices, default=Origem.YOUTUBE, db_column='media_video_origem')
    permitir_comentarios = models.BooleanField(default=True, db_column='media_video_permitir_comentarios')
    conteudo_infantil = models.BooleanField(default=False, db_column='media_video_conteudo_infantil')
    publico = models.BooleanField(default=True, db_column='media_video_publico')
    titulo_seo = models.CharField(max_length=70, blank=True, db_column='media_video_titulo_seo')
    descricao_seo = models.CharField(max_length=160, blank=True, db_column='media_video_descricao_seo')
    imagem_compartilhamento = models.URLField(max_length=500, blank=True, db_column='media_video_imagem_compartilhamento')
    data_gravacao = models.DateTimeField(null=True, blank=True, db_column='media_video_data_gravacao')
    data_agendamento = models.DateTimeField(null=True, blank=True, db_column='media_video_data_agendamento')
    publicado_em = models.DateTimeField(null=True, blank=True, db_column='media_video_publicado_em')
    destaque = models.BooleanField(default=False, db_column='media_video_destaque')
    publicar_na_home = models.BooleanField(default=False, db_column='media_video_publicar_home')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RASCUNHO, db_column='media_video_status')
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='videos_yubotuka', db_column='media_video_fk_autor',
    )
    moderado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='videos_yubotuka_moderados', db_column='media_video_fk_moderador',
    )
    motivo_rejeicao = models.ForeignKey(
        MotivoRejeicao, on_delete=models.PROTECT, null=True, blank=True,
        related_name='videos', db_column='media_video_fk_motivo_rejeicao',
    )
    observacao_rejeicao = models.TextField(blank=True, db_column='media_video_observacao_rejeicao')
    motivo_arquivamento = models.TextField(blank=True, db_column='media_video_motivo_arquivamento')
    status_antes_arquivamento = models.CharField(max_length=20, blank=True, db_column='media_video_status_antes_arquivamento')
    arquivado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='videos_yubotuka_arquivados', db_column='media_video_fk_arquivador',
    )
    ativo = models.BooleanField(default=True, db_column='media_video_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='media_video_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='media_video_atualizado_em')
    excluido_em = models.DateTimeField(null=True, blank=True, db_column='media_video_excluido_em')

    class Meta:
        db_table = '"media"."media_video_tb"'
        ordering = ['-atualizado_em']
        indexes = [
            models.Index(fields=['status', 'ativo'], name='media_video_status_idx'),
            models.Index(fields=['autor', 'status'], name='media_video_autor_idx'),
        ]

    def clean(self):
        self.descricao_curta = texto_sem_html(self.descricao_curta)
        self.descricao = texto_sem_html(self.descricao)
        if self.youtube_url:
            self.youtube_url, self.video_id = normalizar_link_publico(TipoLink.YOUTUBE, self.youtube_url)
            if not self.video_id:
                raise ValidationError({'youtube_url': 'Informe a URL de um vídeo do YouTube.'})
        if self.programa_id and self.canal_id and self.programa.canal_id != self.canal_id:
            raise ValidationError({'programa': 'O programa deve pertencer ao canal selecionado.'})
        if self.temporada_id and self.programa_id != self.temporada.programa_id:
            raise ValidationError({'temporada': 'A temporada deve pertencer ao programa selecionado.'})
        if self.status == self.Status.REJEITADO and not self.motivo_rejeicao_id:
            raise ValidationError({'motivo_rejeicao': 'Informe o motivo da rejeição.'})
        if self.status == self.Status.AGENDADO and not self.data_agendamento:
            raise ValidationError({'data_agendamento': 'Informe a data de agendamento.'})

    def save(self, *args, **kwargs):
        titulo_alterado = False
        if self.pk:
            anterior = type(self).all_objects.filter(pk=self.pk).values('titulo', 'status', 'slug').first()
            titulo_alterado = bool(anterior and anterior['titulo'] != self.titulo)
            if anterior and anterior['status'] == self.Status.PUBLICADO:
                self.slug = anterior['slug']
        if not self.slug or (
            titulo_alterado and self.status in {self.Status.RASCUNHO, self.Status.CORRECAO}
        ):
            self.slug = gerar_slug_unico(self, self.titulo)
        if self.status == self.Status.PUBLICADO and not self.publicado_em:
            self.publicado_em = timezone.now()
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def embed_url(self):
        return f'https://www.youtube-nocookie.com/embed/{self.video_id}' if self.video_id else ''

    @property
    def public_url(self):
        return reverse('media_public:video', args=[self.slug])

    def __str__(self):
        return self.titulo


class Playlist(SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column='media_playlist_id')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column='media_playlist_uuid')
    nome = models.CharField(max_length=160, db_column='media_playlist_nome')
    slug = models.SlugField(max_length=190, unique=True, blank=True, editable=False, db_column='media_playlist_slug')
    descricao = models.TextField(blank=True, db_column='media_playlist_descricao')
    thumbnail = models.URLField(max_length=500, blank=True, db_column='media_playlist_thumbnail')
    canal = models.ForeignKey(Canal, on_delete=models.PROTECT, related_name='playlists', db_column='media_playlist_fk_canal')
    categoria = models.ForeignKey(
        CategoriaYuBotuka, on_delete=models.PROTECT, null=True, blank=True,
        related_name='playlists', db_column='media_playlist_fk_categoria',
    )
    playlist_pai = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='subplaylists', db_column='media_playlist_fk_pai',
    )
    proprietario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='playlists_yubotuka', db_column='media_playlist_fk_proprietario',
    )
    ordem = models.PositiveIntegerField(default=0, db_column='media_playlist_ordem')
    ativo = models.BooleanField(default=True, db_column='media_playlist_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='media_playlist_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='media_playlist_atualizado_em')
    excluido_em = models.DateTimeField(null=True, blank=True, db_column='media_playlist_excluido_em')

    class Meta:
        db_table = '"media"."media_playlist_tb"'
        ordering = ['ordem', 'nome']
        constraints = [
            models.UniqueConstraint(
                fields=['canal', 'playlist_pai', 'nome'],
                condition=models.Q(excluido_em__isnull=True),
                name='media_playlist_hierarquia_uk',
            ),
        ]

    def clean(self):
        self.descricao = texto_sem_html(self.descricao)
        duplicada = type(self).all_objects.filter(
            canal_id=self.canal_id,
            playlist_pai_id=self.playlist_pai_id,
            nome__iexact=self.nome,
            excluido_em__isnull=True,
        )
        if self.pk:
            duplicada = duplicada.exclude(pk=self.pk)
        if duplicada.exists():
            raise ValidationError({'nome': 'Já existe uma playlist com este nome neste nível.'})
        if self.playlist_pai_id and self.playlist_pai_id == self.pk:
            raise ValidationError({'playlist_pai': 'Uma playlist não pode ser pai dela mesma.'})
        ancestral = self.playlist_pai
        visitados = {self.pk}
        while ancestral:
            if ancestral.pk in visitados:
                raise ValidationError({'playlist_pai': 'A hierarquia de playlists não pode possuir ciclos.'})
            if self.canal_id and ancestral.canal_id != self.canal_id:
                raise ValidationError({'playlist_pai': 'A playlist pai deve pertencer ao mesmo canal.'})
            visitados.add(ancestral.pk)
            ancestral = ancestral.playlist_pai

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def caminho(self):
        partes = [self.nome]
        ancestral = self.playlist_pai
        while ancestral:
            partes.insert(0, ancestral.nome)
            ancestral = ancestral.playlist_pai
        return ' › '.join(partes)

    def __str__(self):
        return self.caminho


class PlaylistVideo(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='media_playlist_video_id')
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='itens', db_column='media_playlist_video_fk_playlist')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='itens_playlist', db_column='media_playlist_video_fk_video')
    ordem = models.PositiveIntegerField(default=0, db_column='media_playlist_video_ordem')
    adicionado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='videos_adicionados_a_playlist', db_column='media_playlist_video_fk_usuario',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_column='media_playlist_video_criado_em')

    class Meta:
        db_table = '"media"."media_playlist_video_tb"'
        ordering = ['ordem', 'id']
        constraints = [
            models.UniqueConstraint(fields=['playlist', 'video'], name='media_playlist_video_uk'),
            models.UniqueConstraint(fields=['playlist', 'ordem'], name='media_playlist_ordem_uk'),
        ]


class HistoricoEditorial(models.Model):
    class Acao(models.TextChoices):
        CRIADO = 'CRIADO', 'Criado'
        EDITADO = 'EDITADO', 'Editado'
        ENVIADO_ANALISE = 'ENVIADO_ANALISE', 'Enviado para análise'
        APROVADO = 'APROVADO', 'Aprovado'
        REJEITADO = 'REJEITADO', 'Rejeitado'
        DEVOLVIDO = 'DEVOLVIDO', 'Devolvido para correção'
        AGENDADO = 'AGENDADO', 'Agendado'
        PUBLICADO = 'PUBLICADO', 'Publicado'
        ARQUIVADO = 'ARQUIVADO', 'Arquivado'
        RESTAURADO = 'RESTAURADO', 'Restaurado'
        PLAYLISTS_ALTERADAS = 'PLAYLISTS_ALTERADAS', 'Playlists alteradas'
        ORDEM_ALTERADA = 'ORDEM_ALTERADA', 'Ordem alterada'
        DESTAQUE_ALTERADO = 'DESTAQUE_ALTERADO', 'Destaque alterado'

    id = models.BigAutoField(primary_key=True, db_column='media_historico_editorial_id')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column='media_historico_editorial_uuid')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='historico_editorial', db_column='media_historico_editorial_fk_video')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='historico_editorial_yubotuka', db_column='media_historico_editorial_fk_usuario',
    )
    acao = models.CharField(max_length=30, choices=Acao.choices, db_column='media_historico_editorial_acao')
    status_anterior = models.CharField(max_length=20, blank=True, db_column='media_historico_editorial_status_anterior')
    status_novo = models.CharField(max_length=20, blank=True, db_column='media_historico_editorial_status_novo')
    descricao = models.TextField(blank=True, db_column='media_historico_editorial_descricao')
    ip = models.GenericIPAddressField(null=True, blank=True, db_column='media_historico_editorial_ip')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='media_historico_editorial_criado_em')

    class Meta:
        db_table = '"media"."media_historico_editorial_tb"'
        ordering = ['-criado_em']


class TagYuBotuka(SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column='media_tag_id')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column='media_tag_uuid')
    nome = models.CharField(max_length=80, db_column='media_tag_nome')
    slug = models.SlugField(max_length=100, unique=True, blank=True, editable=False, db_column='media_tag_slug')
    ativo = models.BooleanField(default=True, db_column='media_tag_ativo')
    criado_em = models.DateTimeField(auto_now_add=True, db_column='media_tag_criado_em')
    atualizado_em = models.DateTimeField(auto_now=True, db_column='media_tag_atualizado_em')
    excluido_em = models.DateTimeField(null=True, blank=True, db_column='media_tag_excluido_em')

    class Meta:
        db_table = '"media"."media_tag_tb"'
        ordering = ['nome']

    def clean(self):
        duplicate = type(self).all_objects.filter(
            nome__iexact=self.nome, excluido_em__isnull=True,
        )
        if self.pk:
            duplicate = duplicate.exclude(pk=self.pk)
        if duplicate.exists():
            raise ValidationError({'nome': 'Já existe uma tag com este nome.'})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.nome)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class PessoaAudiovisualBase(SoftDeleteMixin):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nome = models.CharField(max_length=140)
    foto = models.ImageField(upload_to='media/pessoas/', blank=True, validators=[validar_imagem_publica])
    biografia = models.TextField(blank=True)
    instagram_url = models.URLField(max_length=500, blank=True)
    site_url = models.URLField(max_length=500, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    excluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def clean(self):
        self.biografia = texto_sem_html(self.biografia)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class Apresentador(PessoaAudiovisualBase):
    id = models.BigAutoField(primary_key=True, db_column='media_apresentador_id')

    class Meta:
        db_table = '"media"."media_apresentador_tb"'
        ordering = ['nome']


class Convidado(PessoaAudiovisualBase):
    id = models.BigAutoField(primary_key=True, db_column='media_convidado_id')

    class Meta:
        db_table = '"media"."media_convidado_tb"'
        ordering = ['nome']


class Patrocinador(SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column='media_patrocinador_id')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nome = models.CharField(max_length=160)
    logotipo = models.ImageField(upload_to='media/patrocinadores/', blank=True, validators=[validar_imagem_publica])
    descricao = models.TextField(blank=True)
    site_url = models.URLField(max_length=500, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    excluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = '"media"."media_patrocinador_tb"'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class VideoTag(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='videos_tags')
    tag = models.ForeignKey(TagYuBotuka, on_delete=models.PROTECT, related_name='tags_videos')

    class Meta:
        db_table = '"media"."media_video_tag_tb"'
        constraints = [models.UniqueConstraint(fields=['video', 'tag'], name='media_video_tag_uk')]


class VideoApresentador(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='videos_apresentadores')
    apresentador = models.ForeignKey(Apresentador, on_delete=models.PROTECT, related_name='apresentadores_videos')
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = '"media"."media_video_apresentador_tb"'
        constraints = [models.UniqueConstraint(fields=['video', 'apresentador'], name='media_video_apresentador_uk')]


class VideoConvidado(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='videos_convidados')
    convidado = models.ForeignKey(Convidado, on_delete=models.PROTECT, related_name='convidados_videos')
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = '"media"."media_video_convidado_tb"'
        constraints = [models.UniqueConstraint(fields=['video', 'convidado'], name='media_video_convidado_uk')]


class VideoPatrocinador(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='videos_patrocinadores')
    patrocinador = models.ForeignKey(Patrocinador, on_delete=models.PROTECT, related_name='patrocinadores_videos')
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = '"media"."media_video_patrocinador_tb"'
        constraints = [models.UniqueConstraint(fields=['video', 'patrocinador'], name='media_video_patrocinador_uk')]


class BannerYuBotuka(SoftDeleteMixin):
    class Posicao(models.TextChoices):
        HOME = 'HOME', 'Home do BOTUKA'
        YUBOTUKA = 'YUBOTUKA', 'Página YuBotuka'

    id = models.BigAutoField(primary_key=True, db_column='media_banner_id')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    titulo = models.CharField(max_length=160)
    imagem = models.ImageField(upload_to='media/banners/', validators=[validar_imagem_publica])
    link = models.URLField(max_length=500, blank=True)
    posicao = models.CharField(max_length=20, choices=Posicao.choices, default=Posicao.YUBOTUKA)
    ordem = models.PositiveIntegerField(default=0)
    inicio = models.DateTimeField(null=True, blank=True)
    fim = models.DateTimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    excluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = '"media"."media_banner_tb"'
        ordering = ['ordem', '-criado_em']

    def clean(self):
        if self.inicio and self.fim and self.fim <= self.inicio:
            raise ValidationError({'fim': 'O fim deve ser posterior ao início.'})


class ConfiguracaoYuBotuka(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='media_configuracao_id')
    titulo_publico = models.CharField(max_length=120, default='YuBotuka')
    descricao_publica = models.CharField(max_length=240, blank=True)
    quantidade_home = models.PositiveSmallIntegerField(default=6)
    quantidade_pagina = models.PositiveSmallIntegerField(default=12)
    exibir_categorias = models.BooleanField(default=True)
    exibir_playlists = models.BooleanField(default=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name='configuracoes_yubotuka',
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"media"."media_configuracao_tb"'


class DestaqueEditorial(models.Model):
    class Posicao(models.TextChoices):
        HOME = 'HOME', 'Home principal'
        YUBOTUKA = 'YUBOTUKA', 'Página YuBotuka'
        CANAL = 'CANAL', 'Canal'
        CATEGORIA = 'CATEGORIA', 'Categoria'
        PROGRAMA = 'PROGRAMA', 'Programa'
        PLAYLIST = 'PLAYLIST', 'Playlist'

    id = models.BigAutoField(primary_key=True, db_column='media_destaque_id')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column='media_destaque_uuid')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='posicoes_destaque')
    posicao = models.CharField(max_length=20, choices=Posicao.choices)
    canal = models.ForeignKey(Canal, on_delete=models.CASCADE, null=True, blank=True, related_name='destaques_editoriais')
    categoria = models.ForeignKey(CategoriaYuBotuka, on_delete=models.CASCADE, null=True, blank=True, related_name='destaques_editoriais')
    programa = models.ForeignKey(Programa, on_delete=models.CASCADE, null=True, blank=True, related_name='destaques_editoriais')
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, null=True, blank=True, related_name='destaques_editoriais')
    ordem = models.PositiveIntegerField(default=0)
    inicio = models.DateTimeField(null=True, blank=True)
    fim = models.DateTimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = '"media"."media_destaque_tb"'
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.get_posicao_display()} · {self.video}'


class ProgramaApresentador(models.Model):
    programa = models.ForeignKey(Programa, on_delete=models.CASCADE, related_name='programas_apresentadores')
    apresentador = models.ForeignKey(Apresentador, on_delete=models.PROTECT, related_name='apresentadores_programas')
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = '"media"."media_programa_apresentador_tb"'
        constraints = [models.UniqueConstraint(fields=['programa', 'apresentador'], name='media_programa_apresentador_uk')]


class ProgramaPatrocinador(models.Model):
    programa = models.ForeignKey(Programa, on_delete=models.CASCADE, related_name='programas_patrocinadores')
    patrocinador = models.ForeignKey(Patrocinador, on_delete=models.PROTECT, related_name='patrocinadores_programas')
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = '"media"."media_programa_patrocinador_tb"'
        constraints = [models.UniqueConstraint(fields=['programa', 'patrocinador'], name='media_programa_patrocinador_uk')]


class TransmissaoApresentador(models.Model):
    transmissao = models.ForeignKey(Transmissao, on_delete=models.CASCADE, related_name='transmissoes_apresentadores')
    apresentador = models.ForeignKey(Apresentador, on_delete=models.PROTECT, related_name='apresentadores_transmissoes')
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = '"media"."media_transmissao_apresentador_tb"'
        constraints = [models.UniqueConstraint(fields=['transmissao', 'apresentador'], name='media_transmissao_apresentador_uk')]


class TransmissaoConvidado(models.Model):
    transmissao = models.ForeignKey(Transmissao, on_delete=models.CASCADE, related_name='transmissoes_convidados')
    convidado = models.ForeignKey(Convidado, on_delete=models.PROTECT, related_name='convidados_transmissoes')
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = '"media"."media_transmissao_convidado_tb"'
        constraints = [models.UniqueConstraint(fields=['transmissao', 'convidado'], name='media_transmissao_convidado_uk')]


class TransmissaoPatrocinador(models.Model):
    transmissao = models.ForeignKey(Transmissao, on_delete=models.CASCADE, related_name='transmissoes_patrocinadores')
    patrocinador = models.ForeignKey(Patrocinador, on_delete=models.PROTECT, related_name='patrocinadores_transmissoes')
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = '"media"."media_transmissao_patrocinador_tb"'
        constraints = [models.UniqueConstraint(fields=['transmissao', 'patrocinador'], name='media_transmissao_patrocinador_uk')]


class CanalUsuario(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='media_canal_usuario_id')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    canal = models.ForeignKey(Canal, on_delete=models.CASCADE, related_name='usuarios_autorizados')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='autorizacoes_canais_yubotuka')
    pode_editar = models.BooleanField(default=True)
    pode_moderar = models.BooleanField(default=False)
    concedido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='autorizacoes_canal_concedidas')
    motivo = models.TextField()
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    revogado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = '"media"."media_canal_usuario_tb"'
        constraints = [
            models.UniqueConstraint(
                fields=['canal', 'usuario'],
                condition=models.Q(ativo=True, revogado_em__isnull=True),
                name='media_canal_usuario_ativo_uk',
            ),
        ]


class HomologacaoVideoMigrado(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='media_homologacao_video_id')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    video = models.OneToOneField(Video, on_delete=models.CASCADE, related_name='homologacao_migracao')
    episodio_legado = models.OneToOneField(Episodio, on_delete=models.PROTECT, related_name='homologacao_video')
    homologado = models.BooleanField(default=False)
    homologado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='videos_migrados_homologados')
    homologado_em = models.DateTimeField(null=True, blank=True)
    observacao = models.TextField(blank=True)
    divergencias = models.JSONField(default=dict, blank=True)
    valores_confirmados = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"media"."media_homologacao_video_tb"'
        ordering = ['homologado', 'video__titulo']
