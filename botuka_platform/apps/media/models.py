import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
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
    apresentador=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='programas_apresentados',db_column='media_programa_fk_apresentador'); produtor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='programas_produzidos',db_column='media_programa_fk_produtor')
    imagem=models.ImageField(upload_to='media/programas/',blank=True,validators=[validar_imagem_publica],db_column='media_programa_imagem'); frequencia=models.CharField(max_length=80,blank=True,db_column='media_programa_frequencia'); duracao_media=models.DurationField(null=True,blank=True,db_column='media_programa_duracao_media'); ativo=models.BooleanField(default=True,db_column='media_programa_ativo')
    criado_em=models.DateTimeField(auto_now_add=True,db_column='media_programa_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='media_programa_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='media_programa_excluido_em')
    class Meta: db_table='"media"."media_programa_tb"'; ordering=['nome']
    def save(self,*a,**kw):
        if not self.slug:self.slug=gerar_slug_unico(self,self.nome)
        self.full_clean(); super().save(*a,**kw)
    def __str__(self): return self.nome


class Temporada(SoftDeleteMixin):
    id=models.BigAutoField(primary_key=True,db_column='media_temporada_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='media_temporada_uuid')
    programa=models.ForeignKey(Programa,on_delete=models.CASCADE,related_name='temporadas',db_column='media_temporada_fk_programa'); numero=models.PositiveIntegerField(db_column='media_temporada_numero'); titulo=models.CharField(max_length=160,blank=True,db_column='media_temporada_titulo'); descricao=models.TextField(blank=True,db_column='media_temporada_descricao'); data_inicial=models.DateField(null=True,blank=True,db_column='media_temporada_data_inicial'); data_final=models.DateField(null=True,blank=True,db_column='media_temporada_data_final'); ativo=models.BooleanField(default=True,db_column='media_temporada_ativo')
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
    def __str__(self): return self.titulo


class Pauta(SoftDeleteMixin):
    class Status(models.TextChoices): IDEIA='IDEIA','Ideia'; APROVADA='APROVADA','Aprovada'; PRODUCAO='PRODUCAO','Produção'; CONCLUIDA='CONCLUIDA','Concluída'; CANCELADA='CANCELADA','Cancelada'
    id=models.BigAutoField(primary_key=True,db_column='media_pauta_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='media_pauta_uuid'); titulo=models.CharField(max_length=200,db_column='media_pauta_titulo'); descricao=models.TextField(blank=True,db_column='media_pauta_descricao'); programa=models.ForeignKey(Programa,on_delete=models.PROTECT,related_name='pautas',db_column='media_pauta_fk_programa'); responsavel=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='pautas_media',db_column='media_pauta_fk_responsavel'); convidados=models.TextField(blank=True,db_column='media_pauta_convidados'); roteiro=models.TextField(blank=True,db_column='media_pauta_roteiro'); data_prevista=models.DateTimeField(null=True,blank=True,db_column='media_pauta_data_prevista'); status=models.CharField(max_length=20,choices=Status.choices,default=Status.IDEIA,db_column='media_pauta_status'); observacoes=models.TextField(blank=True,db_column='media_pauta_observacoes'); ativo=models.BooleanField(default=True,db_column='media_pauta_ativo'); criado_em=models.DateTimeField(auto_now_add=True,db_column='media_pauta_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='media_pauta_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='media_pauta_excluido_em')
    class Meta: db_table='"media"."media_pauta_tb"'


class Transmissao(SoftDeleteMixin):
    class Status(models.TextChoices): AGENDADA='AGENDADA','Agendada'; AO_VIVO='AO_VIVO','Ao vivo'; ENCERRADA='ENCERRADA','Encerrada'; CANCELADA='CANCELADA','Cancelada'
    id=models.BigAutoField(primary_key=True,db_column='media_transmissao_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='media_transmissao_uuid'); episodio=models.OneToOneField(Episodio,on_delete=models.CASCADE,related_name='transmissao',db_column='media_transmissao_fk_episodio'); disputa=models.ForeignKey('sports.Disputa',on_delete=models.SET_NULL,null=True,blank=True,related_name='transmissoes',db_column='media_transmissao_fk_disputa'); acao_publica=models.ForeignKey('government.AcaoPublica',on_delete=models.SET_NULL,null=True,blank=True,related_name='transmissoes',db_column='media_transmissao_fk_acao'); data_prevista=models.DateTimeField(null=True,blank=True,db_column='media_transmissao_data_prevista'); inicio=models.DateTimeField(null=True,blank=True,db_column='media_transmissao_inicio'); fim=models.DateTimeField(null=True,blank=True,db_column='media_transmissao_fim'); url_ao_vivo=models.URLField(blank=True,max_length=500,db_column='media_transmissao_url'); status=models.CharField(max_length=20,choices=Status.choices,default=Status.AGENDADA,db_column='media_transmissao_status'); ativo=models.BooleanField(default=True,db_column='media_transmissao_ativo'); criado_em=models.DateTimeField(auto_now_add=True,db_column='media_transmissao_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='media_transmissao_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='media_transmissao_excluido_em')
    class Meta: db_table='"media"."media_transmissao_tb"'
    def clean(self):
        if self.inicio and self.fim and self.fim < self.inicio: raise ValidationError({'fim':'O fim deve ser posterior ao início.'})
        if self.status == self.Status.AO_VIVO and self.episodio.status != Episodio.Status.AO_VIVO: raise ValidationError({'status':'A transmissão ao vivo exige episódio em estado AO_VIVO.'})
    def save(self,*a,**kw): self.full_clean(); super().save(*a,**kw)
