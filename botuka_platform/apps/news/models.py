import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from apps.core.domain import SoftDeleteMixin, EditorialStatus, texto_sem_html, validar_imagem_publica
from apps.core.public_links import TipoLink, normalizar_link_publico
from apps.core.utils import gerar_slug_unico

TERMOS_PROIBIDOS={'policial','polícia','criminal','crime','violência','ocorrência'}

class CategoriaNoticia(SoftDeleteMixin):
    id=models.BigAutoField(primary_key=True,db_column='news_categoria_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='news_categoria_uuid'); nome=models.CharField(max_length=120,db_column='news_categoria_nome'); slug=models.SlugField(max_length=150,unique=True,blank=True,db_column='news_categoria_slug'); descricao=models.TextField(blank=True,db_column='news_categoria_descricao'); categoria_pai=models.ForeignKey('self',on_delete=models.SET_NULL,null=True,blank=True,related_name='filhas',db_column='news_categoria_fk_pai'); ordem=models.PositiveIntegerField(default=0,db_column='news_categoria_ordem'); ativo=models.BooleanField(default=True,db_column='news_categoria_ativo'); criado_em=models.DateTimeField(auto_now_add=True,db_column='news_categoria_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='news_categoria_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='news_categoria_excluido_em')
    class Meta: db_table='"news"."news_categoria_tb"'; ordering=['ordem','nome']
    def clean(self):
        if any(t in self.nome.lower() for t in TERMOS_PROIBIDOS):raise ValidationError({'nome':'Esta categoria não faz parte da linha editorial do BOTUKA News.'})
    def save(self,*a,**kw):
        if not self.slug:self.slug=gerar_slug_unico(self,self.nome)
        self.full_clean();super().save(*a,**kw)
    def __str__(self):return self.nome

class Artigo(SoftDeleteMixin):
    id=models.BigAutoField(primary_key=True,db_column='news_artigo_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='news_artigo_uuid'); autor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='artigos_news',db_column='news_artigo_fk_autor'); categoria=models.ForeignKey(CategoriaNoticia,on_delete=models.PROTECT,related_name='artigos',db_column='news_artigo_fk_categoria'); revisado_por=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='artigos_revisados',db_column='news_artigo_fk_revisor'); publicador=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='artigos_publicados',db_column='news_artigo_fk_publicador'); campeonato=models.ForeignKey('sports.Campeonato',on_delete=models.SET_NULL,null=True,blank=True,related_name='artigos',db_column='news_artigo_fk_campeonato'); acao_publica=models.ForeignKey('government.AcaoPublica',on_delete=models.SET_NULL,null=True,blank=True,related_name='artigos',db_column='news_artigo_fk_acao'); episodio=models.ForeignKey('media.Episodio',on_delete=models.SET_NULL,null=True,blank=True,related_name='artigos',db_column='news_artigo_fk_episodio'); titulo=models.CharField(max_length=220,db_column='news_artigo_titulo'); subtitulo=models.CharField(max_length=250,blank=True,db_column='news_artigo_subtitulo'); slug=models.SlugField(max_length=250,unique=True,blank=True,db_column='news_artigo_slug'); resumo=models.TextField(blank=True,db_column='news_artigo_resumo'); conteudo=models.TextField(db_column='news_artigo_conteudo'); imagem_capa=models.ImageField(upload_to='news/artigos/',blank=True,db_column='news_artigo_imagem'); credito_imagem=models.CharField(max_length=180,blank=True,db_column='news_artigo_credito'); fonte=models.CharField(max_length=180,blank=True,db_column='news_artigo_fonte'); url_fonte=models.URLField(blank=True,max_length=500,db_column='news_artigo_url_fonte'); data_fato=models.DateTimeField(null=True,blank=True,db_column='news_artigo_data_fato'); status=models.CharField(max_length=20,choices=EditorialStatus.choices,default=EditorialStatus.RASCUNHO,db_column='news_artigo_status'); motivo_rejeicao=models.TextField(blank=True,db_column='news_artigo_motivo_rejeicao'); destaque=models.BooleanField(default=False,db_column='news_artigo_destaque'); urgente=models.BooleanField(default=False,db_column='news_artigo_urgente'); titulo_seo=models.CharField(max_length=70,blank=True,db_column='news_artigo_titulo_seo'); descricao_seo=models.CharField(max_length=160,blank=True,db_column='news_artigo_descricao_seo'); imagem_social=models.ImageField(upload_to='news/social/',blank=True,db_column='news_artigo_imagem_social'); publicado_em=models.DateTimeField(null=True,blank=True,db_column='news_artigo_publicado_em'); revisado_em=models.DateTimeField(null=True,blank=True,db_column='news_artigo_revisado_em'); ativo=models.BooleanField(default=True,db_column='news_artigo_ativo'); criado_em=models.DateTimeField(auto_now_add=True,db_column='news_artigo_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='news_artigo_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='news_artigo_excluido_em')
    class Meta: db_table='"news"."news_artigo_tb"'; ordering=['-publicado_em','-criado_em']; indexes=[models.Index(fields=['status','publicado_em'],name='news_artigo_status_idx'),models.Index(fields=['categoria','status'],name='news_artigo_categoria_idx')]
    def clean(self):
        self.conteudo=texto_sem_html(self.conteudo)
        validar_imagem_publica(self.imagem_capa)
        validar_imagem_publica(self.imagem_social)
    def save(self,*a,**kw):
        if not self.slug:self.slug=gerar_slug_unico(self,self.titulo)
        if self.status==EditorialStatus.PUBLICADO and not self.publicado_em:self.publicado_em=timezone.now()
        self.full_clean();super().save(*a,**kw)
    def __str__(self):return self.titulo

class ArtigoBloco(SoftDeleteMixin):
    class Tipo(models.TextChoices): TEXTO='TEXTO','Texto'; IMAGEM='IMAGEM','Imagem'; VIDEO='VIDEO_YOUTUBE','Vídeo YouTube'; CITACAO='CITACAO','Citação'; GALERIA='GALERIA','Galeria'; LINK='LINK','Link'; SUBTITULO='SUBTITULO','Subtítulo'
    id=models.BigAutoField(primary_key=True,db_column='news_bloco_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='news_bloco_uuid'); artigo=models.ForeignKey(Artigo,on_delete=models.CASCADE,related_name='blocos',db_column='news_bloco_fk_artigo'); tipo=models.CharField(max_length=20,choices=Tipo.choices,db_column='news_bloco_tipo'); titulo=models.CharField(max_length=220,blank=True,db_column='news_bloco_titulo'); conteudo=models.TextField(blank=True,db_column='news_bloco_conteudo'); url=models.URLField(blank=True,max_length=500,db_column='news_bloco_url'); identificador_externo=models.CharField(max_length=120,blank=True,db_column='news_bloco_identificador'); ordem=models.PositiveIntegerField(default=0,db_column='news_bloco_ordem'); ativo=models.BooleanField(default=True,db_column='news_bloco_ativo'); criado_em=models.DateTimeField(auto_now_add=True,db_column='news_bloco_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='news_bloco_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='news_bloco_excluido_em')
    class Meta: db_table='"news"."news_artigo_bloco_tb"'; ordering=['ordem','id']
    def clean(self):
        self.titulo=texto_sem_html(self.titulo);self.conteudo=texto_sem_html(self.conteudo)
        if self.tipo==self.Tipo.VIDEO:
            self.url,self.identificador_externo=normalizar_link_publico(TipoLink.YOUTUBE,self.url)
            if not self.identificador_externo:raise ValidationError({'url':'Informe um vídeo válido do YouTube.'})
    def save(self,*a,**kw):self.full_clean();super().save(*a,**kw)

class ArtigoFonte(SoftDeleteMixin):
    id=models.BigAutoField(primary_key=True,db_column='news_fonte_id'); uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False,db_column='news_fonte_uuid'); artigo=models.ForeignKey(Artigo,on_delete=models.CASCADE,related_name='fontes',db_column='news_fonte_fk_artigo'); titulo=models.CharField(max_length=180,db_column='news_fonte_titulo'); url=models.URLField(max_length=500,db_column='news_fonte_url'); veiculo=models.CharField(max_length=160,blank=True,db_column='news_fonte_veiculo'); data_acesso=models.DateField(db_column='news_fonte_data_acesso'); ordem=models.PositiveIntegerField(default=0,db_column='news_fonte_ordem'); ativo=models.BooleanField(default=True,db_column='news_fonte_ativo'); criado_em=models.DateTimeField(auto_now_add=True,db_column='news_fonte_criado_em'); atualizado_em=models.DateTimeField(auto_now=True,db_column='news_fonte_atualizado_em'); excluido_em=models.DateTimeField(null=True,blank=True,db_column='news_fonte_excluido_em')
    class Meta: db_table='"news"."news_artigo_fonte_tb"'; ordering=['ordem','id']
