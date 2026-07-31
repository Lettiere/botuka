import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.domain import (
    EditorialStatus as LegacyEditorialStatus,
    SoftDeleteMixin,
    texto_sem_html,
    validar_imagem_publica,
)
from apps.core.public_links import TipoLink, normalizar_link_publico, url_embed_youtube
from apps.core.utils import gerar_slug_unico
from .sanitizers import sanitizar_html_editorial


TERMOS_PROIBIDOS = {
    "policial", "polícia", "criminal", "crime", "violência", "ocorrência",
}


class EditorialStatus(models.TextChoices):
    RASCUNHO = "RASCUNHO", "Rascunho"
    ENVIADO_REVISAO = "ENVIADO_REVISAO", "Enviado para revisão"
    EM_REVISAO = "EM_REVISAO", "Em revisão"
    CORRECAO_SOLICITADA = "CORRECAO_SOLICITADA", "Correção solicitada"
    APROVADO = "APROVADO", "Aprovado"
    AGENDADO = "AGENDADO", "Agendado"
    PUBLICADO = "PUBLICADO", "Publicado"
    REJEITADO = "REJEITADO", "Rejeitado"
    DESPUBLICADO = "DESPUBLICADO", "Despublicado"
    ARQUIVADO = "ARQUIVADO", "Arquivado"


class TipoEditorial(models.TextChoices):
    NOTICIA = "NOTICIA", "Notícia"
    REPORTAGEM = "REPORTAGEM", "Reportagem"
    ARTIGO = "ARTIGO", "Artigo"
    COLUNA = "COLUNA", "Coluna"
    OPINIAO = "OPINIAO", "Opinião"
    EDITORIAL = "EDITORIAL", "Editorial"
    ENTREVISTA = "ENTREVISTA", "Entrevista"
    NOTA = "NOTA", "Nota"


class SlugModelMixin:
    slug_source = "nome"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = gerar_slug_unico(self, getattr(self, self.slug_source))
        self.full_clean()
        return super().save(*args, **kwargs)


class CategoriaNoticia(SlugModelMixin, SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column="news_categoria_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_categoria_uuid")
    nome = models.CharField(max_length=120, db_column="news_categoria_nome")
    slug = models.SlugField(max_length=150, unique=True, blank=True, db_column="news_categoria_slug")
    descricao = models.TextField(blank=True, db_column="news_categoria_descricao")
    categoria_pai = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="filhas", db_column="news_categoria_fk_pai")
    ordem = models.PositiveIntegerField(default=0, db_column="news_categoria_ordem")
    ativo = models.BooleanField(default=True, db_column="news_categoria_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_categoria_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_categoria_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_categoria_excluido_em")

    class Meta:
        db_table = '"news"."news_categoria_tb"'
        ordering = ["ordem", "nome"]

    def clean(self):
        if any(termo in self.nome.lower() for termo in TERMOS_PROIBIDOS):
            raise ValidationError({"nome": "Esta categoria não faz parte da linha editorial do BOTUKA Notícias."})

    def __str__(self):
        return self.nome


class EspecialidadeAutor(SlugModelMixin, SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column="news_especialidade_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_especialidade_uuid")
    nome = models.CharField(max_length=120, db_column="news_especialidade_nome")
    slug = models.SlugField(max_length=150, unique=True, blank=True, db_column="news_especialidade_slug")
    descricao = models.TextField(blank=True, db_column="news_especialidade_descricao")
    ativo = models.BooleanField(default=True, db_column="news_especialidade_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_especialidade_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_especialidade_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_especialidade_excluido_em")

    class Meta:
        db_table = '"news"."news_especialidade_autor_tb"'
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Autor(SlugModelMixin, SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column="news_autor_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_autor_uuid")
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="autor_news", db_column="news_autor_fk_usuario")
    nome = models.CharField(max_length=160, db_column="news_autor_nome")
    slug = models.SlugField(max_length=180, unique=True, blank=True, db_column="news_autor_slug")
    foto = models.ImageField(upload_to="news/autores/", blank=True, db_column="news_autor_foto")
    mini_bio = models.CharField(max_length=280, blank=True, db_column="news_autor_mini_bio")
    biografia = models.TextField(blank=True, db_column="news_autor_biografia")
    site = models.URLField(max_length=500, blank=True, db_column="news_autor_site")
    instagram = models.URLField(max_length=500, blank=True, db_column="news_autor_instagram")
    facebook = models.URLField(max_length=500, blank=True, db_column="news_autor_facebook")
    linkedin = models.URLField(max_length=500, blank=True, db_column="news_autor_linkedin")
    x = models.URLField(max_length=500, blank=True, db_column="news_autor_x")
    tiktok = models.URLField(max_length=500, blank=True, db_column="news_autor_tiktok")
    youtube = models.URLField(max_length=500, blank=True, db_column="news_autor_youtube")
    especialidades = models.ManyToManyField(EspecialidadeAutor, blank=True, related_name="autores", through="AutorEspecialidade")
    ativo = models.BooleanField(default=True, db_column="news_autor_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_autor_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_autor_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_autor_excluido_em")

    class Meta:
        db_table = '"news"."news_autor_tb"'
        ordering = ["nome"]

    def clean(self):
        self.biografia = texto_sem_html(self.biografia)
        validar_imagem_publica(self.foto)

    def __str__(self):
        return self.nome


class Colunista(SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column="news_colunista_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_colunista_uuid")
    autor = models.OneToOneField(Autor, on_delete=models.PROTECT, related_name="perfil_colunista", db_column="news_colunista_fk_autor")
    titulo = models.CharField(max_length=140, blank=True, db_column="news_colunista_titulo")
    ordem = models.PositiveIntegerField(default=0, db_column="news_colunista_ordem")
    destaque = models.BooleanField(default=False, db_column="news_colunista_destaque")
    ativo = models.BooleanField(default=True, db_column="news_colunista_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_colunista_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_colunista_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_colunista_excluido_em")

    class Meta:
        db_table = '"news"."news_colunista_tb"'
        ordering = ["ordem", "autor__nome"]

    def __str__(self):
        return str(self.autor)


class Coluna(SlugModelMixin, SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column="news_coluna_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_coluna_uuid")
    autor = models.ForeignKey(Autor, on_delete=models.PROTECT, related_name="colunas", db_column="news_coluna_fk_autor")
    nome = models.CharField(max_length=160, db_column="news_coluna_nome")
    slug = models.SlugField(max_length=180, unique=True, blank=True, db_column="news_coluna_slug")
    descricao = models.TextField(blank=True, db_column="news_coluna_descricao")
    imagem = models.ImageField(upload_to="news/colunas/", blank=True, db_column="news_coluna_imagem")
    ordem = models.PositiveIntegerField(default=0, db_column="news_coluna_ordem")
    ativo = models.BooleanField(default=True, db_column="news_coluna_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_coluna_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_coluna_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_coluna_excluido_em")

    class Meta:
        db_table = '"news"."news_coluna_tb"'
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome


class TaxonomiaEditorialBase(SlugModelMixin, SoftDeleteMixin):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nome = models.CharField(max_length=120)
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    excluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Tema(TaxonomiaEditorialBase):
    id = models.BigAutoField(primary_key=True, db_column="news_tema_id")

    class Meta(TaxonomiaEditorialBase.Meta):
        db_table = '"news"."news_tema_tb"'


class Tag(TaxonomiaEditorialBase):
    id = models.BigAutoField(primary_key=True, db_column="news_tag_id")

    class Meta(TaxonomiaEditorialBase.Meta):
        db_table = '"news"."news_tag_tb"'


class SerieEditorial(SlugModelMixin, SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column="news_serie_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_serie_uuid")
    nome = models.CharField(max_length=120, db_column="news_serie_nome")
    slug = models.SlugField(max_length=150, unique=True, blank=True, db_column="news_serie_slug")
    descricao = models.TextField(blank=True, db_column="news_serie_descricao")
    imagem = models.ImageField(upload_to="news/series/", blank=True)
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True, db_column="news_serie_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_serie_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_serie_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_serie_excluido_em")

    class Meta:
        db_table = '"news"."news_serie_editorial_tb"'
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome


class Artigo(SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column="news_artigo_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_artigo_uuid")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="artigos_news", db_column="news_artigo_fk_autor")
    autor_editorial = models.ForeignKey(Autor, on_delete=models.PROTECT, null=True, blank=True, related_name="artigos", db_column="news_artigo_fk_autor_editorial")
    categoria = models.ForeignKey(CategoriaNoticia, on_delete=models.PROTECT, related_name="artigos", db_column="news_artigo_fk_categoria")
    coluna = models.ForeignKey(Coluna, on_delete=models.SET_NULL, null=True, blank=True, related_name="artigos", db_column="news_artigo_fk_coluna")
    serie = models.ForeignKey(SerieEditorial, on_delete=models.SET_NULL, null=True, blank=True, related_name="artigos", db_column="news_artigo_fk_serie")
    temas = models.ManyToManyField(Tema, blank=True, related_name="artigos", through="ArtigoTema")
    tags = models.ManyToManyField(Tag, blank=True, related_name="artigos", through="ArtigoTag")
    revisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="artigos_revisados", db_column="news_artigo_fk_revisor")
    publicador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="artigos_publicados", db_column="news_artigo_fk_publicador")
    campeonato = models.ForeignKey("sports.Campeonato", on_delete=models.SET_NULL, null=True, blank=True, related_name="artigos", db_column="news_artigo_fk_campeonato")
    acao_publica = models.ForeignKey("government.AcaoPublica", on_delete=models.SET_NULL, null=True, blank=True, related_name="artigos", db_column="news_artigo_fk_acao")
    episodio = models.ForeignKey("media.Episodio", on_delete=models.SET_NULL, null=True, blank=True, related_name="artigos", db_column="news_artigo_fk_episodio")
    titulo = models.CharField(max_length=220, db_column="news_artigo_titulo")
    subtitulo = models.CharField(max_length=250, blank=True, db_column="news_artigo_subtitulo")
    slug = models.SlugField(max_length=250, unique=True, blank=True, db_column="news_artigo_slug")
    resumo = models.TextField(blank=True, db_column="news_artigo_resumo")
    conteudo = models.TextField(db_column="news_artigo_conteudo")
    tipo_editorial = models.CharField(max_length=20, choices=TipoEditorial.choices, default=TipoEditorial.NOTICIA, db_column="news_artigo_tipo_editorial")
    imagem_capa = models.ImageField(upload_to="news/artigos/", blank=True, db_column="news_artigo_imagem")
    legenda_imagem = models.CharField(max_length=280, blank=True, db_column="news_artigo_legenda_imagem")
    credito_imagem = models.CharField(max_length=180, blank=True, db_column="news_artigo_credito")
    fonte_imagem = models.CharField(max_length=180, blank=True, db_column="news_artigo_fonte_imagem")
    texto_alternativo_imagem = models.CharField(max_length=220, blank=True, db_column="news_artigo_alt_imagem")
    fonte = models.CharField(max_length=180, blank=True, db_column="news_artigo_fonte")
    url_fonte = models.URLField(blank=True, max_length=500, db_column="news_artigo_url_fonte")
    data_fato = models.DateTimeField(null=True, blank=True, db_column="news_artigo_data_fato")
    status = models.CharField(max_length=24, choices=EditorialStatus.choices, default=EditorialStatus.RASCUNHO, db_column="news_artigo_status")
    motivo_rejeicao = models.TextField(blank=True, db_column="news_artigo_motivo_rejeicao")
    destaque = models.BooleanField(default=False, db_column="news_artigo_destaque")
    urgente = models.BooleanField(default=False, db_column="news_artigo_urgente")
    titulo_seo = models.CharField(max_length=70, blank=True, db_column="news_artigo_titulo_seo")
    descricao_seo = models.CharField(max_length=160, blank=True, db_column="news_artigo_descricao_seo")
    imagem_social = models.ImageField(upload_to="news/social/", blank=True, db_column="news_artigo_imagem_social")
    comentarios_permitidos = models.BooleanField(default=True, db_column="news_artigo_comentarios_permitidos")
    comentarios_moderados = models.BooleanField(default=False, db_column="news_artigo_comentarios_moderados")
    comentarios_encerrados = models.BooleanField(default=False, db_column="news_artigo_comentarios_encerrados")
    agendado_para = models.DateTimeField(null=True, blank=True, db_column="news_artigo_agendado_para")
    publicado_em = models.DateTimeField(null=True, blank=True, db_column="news_artigo_publicado_em")
    revisado_em = models.DateTimeField(null=True, blank=True, db_column="news_artigo_revisado_em")
    ativo = models.BooleanField(default=True, db_column="news_artigo_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_artigo_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_artigo_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_artigo_excluido_em")

    class Meta:
        db_table = '"news"."news_artigo_tb"'
        ordering = ["-publicado_em", "-criado_em"]
        indexes = [
            models.Index(fields=["status", "publicado_em"], name="news_artigo_status_idx"),
            models.Index(fields=["categoria", "status"], name="news_artigo_categoria_idx"),
            models.Index(fields=["status", "agendado_para"], name="news_artigo_agenda_idx"),
            models.Index(fields=["autor_editorial", "status"], name="news_artigo_autor_ed_idx"),
            models.Index(fields=["destaque", "publicado_em"], name="news_artigo_destaque_idx"),
        ]

    def clean(self):
        self.conteudo = sanitizar_html_editorial(self.conteudo)
        if not self.conteudo:
            raise ValidationError({"conteudo": "Informe o conteúdo da notícia."})
        validar_imagem_publica(self.imagem_capa)
        validar_imagem_publica(self.imagem_social)
        if self.status == EditorialStatus.AGENDADO and not self.agendado_para:
            raise ValidationError({"agendado_para": "Informe a data e hora da publicação."})
        if self.pk and self.status in {EditorialStatus.APROVADO, EditorialStatus.AGENDADO, EditorialStatus.PUBLICADO}:
            for imagem in self.imagens.filter(ativo=True, excluido_em__isnull=True):
                imagem.validar_direitos_publicacao()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = gerar_slug_unico(self, self.titulo)
        if self.status == EditorialStatus.PUBLICADO and not self.publicado_em:
            self.publicado_em = timezone.now()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.titulo

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("news_public:artigo", args=[self.slug])


class ComentarioArtigo(SoftDeleteMixin):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        PUBLICADO = "PUBLICADO", "Publicado"
        OCULTO = "OCULTO", "Oculto"
        REJEITADO = "REJEITADO", "Rejeitado"

    id = models.BigAutoField(primary_key=True, db_column="news_comentario_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_comentario_uuid")
    artigo = models.ForeignKey(Artigo, on_delete=models.CASCADE, related_name="comentarios", db_column="news_comentario_fk_artigo")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="comentarios_news", db_column="news_comentario_fk_usuario")
    comentario_raiz = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="respostas", db_column="news_comentario_fk_raiz")
    respondendo_a = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="respostas_diretas", db_column="news_comentario_fk_respondido")
    usuario_mencionado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="mencoes_news", db_column="news_comentario_fk_mencionado")
    texto = models.TextField(max_length=1000, db_column="news_comentario_texto")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PUBLICADO, db_column="news_comentario_status")
    moderado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="comentarios_news_moderados", db_column="news_comentario_fk_moderador")
    moderado_em = models.DateTimeField(null=True, blank=True, db_column="news_comentario_moderado_em")
    motivo_moderacao = models.CharField(max_length=500, blank=True, db_column="news_comentario_motivo")
    editado_em = models.DateTimeField(null=True, blank=True, db_column="news_comentario_editado_em")
    ativo = models.BooleanField(default=True, db_column="news_comentario_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_comentario_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_comentario_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_comentario_excluido_em")

    class Meta:
        db_table = '"news"."news_comentario_artigo_tb"'
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["artigo", "status", "criado_em"], name="news_coment_art_status_idx")]

    def clean(self):
        self.texto = (self.texto or "").strip()
        if not self.texto:
            raise ValidationError({"texto": "Escreva um comentário."})
        self.texto = texto_sem_html(self.texto)
        if len(self.texto) > 1000:
            raise ValidationError({"texto": "O comentário deve ter no máximo 1.000 caracteres."})
        if self.comentario_raiz_id and self.comentario_raiz.comentario_raiz_id:
            self.comentario_raiz = self.comentario_raiz.comentario_raiz
        if self.comentario_raiz_id and self.comentario_raiz.artigo_id != self.artigo_id:
            raise ValidationError("A resposta não pertence a esta notícia.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class CurtidaComentario(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="news_curtida_comentario_id")
    comentario = models.ForeignKey(ComentarioArtigo, on_delete=models.CASCADE, related_name="curtidas", db_column="news_curtida_fk_comentario")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="curtidas_comentarios_news", db_column="news_curtida_fk_usuario")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_curtida_criado_em")

    class Meta:
        db_table = '"news"."news_curtida_comentario_tb"'
        constraints = [models.UniqueConstraint(fields=["comentario", "usuario"], name="news_curtida_comentario_uk")]


class DenunciaComentario(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="news_denuncia_comentario_id")
    comentario = models.ForeignKey(ComentarioArtigo, on_delete=models.CASCADE, related_name="denuncias", db_column="news_denuncia_fk_comentario")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="denuncias_comentarios_news", db_column="news_denuncia_fk_usuario")
    motivo = models.CharField(max_length=500, db_column="news_denuncia_motivo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_denuncia_criado_em")

    class Meta:
        db_table = '"news"."news_denuncia_comentario_tb"'
        constraints = [models.UniqueConstraint(fields=["comentario", "usuario"], name="news_denuncia_comentario_uk")]


class ArtigoBloco(SoftDeleteMixin):
    class Tipo(models.TextChoices):
        TEXTO = "TEXTO", "Texto"
        IMAGEM = "IMAGEM", "Imagem"
        VIDEO = "VIDEO_YOUTUBE", "Vídeo YouTube"
        CITACAO = "CITACAO", "Citação"
        GALERIA = "GALERIA", "Galeria"
        LINK = "LINK", "Link"
        SUBTITULO = "SUBTITULO", "Subtítulo"

    id = models.BigAutoField(primary_key=True, db_column="news_bloco_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_bloco_uuid")
    artigo = models.ForeignKey(Artigo, on_delete=models.CASCADE, related_name="blocos", db_column="news_bloco_fk_artigo")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, db_column="news_bloco_tipo")
    titulo = models.CharField(max_length=220, blank=True, db_column="news_bloco_titulo")
    conteudo = models.TextField(blank=True, db_column="news_bloco_conteudo")
    url = models.URLField(blank=True, max_length=500, db_column="news_bloco_url")
    identificador_externo = models.CharField(max_length=120, blank=True, db_column="news_bloco_identificador")
    ordem = models.PositiveIntegerField(default=0, db_column="news_bloco_ordem")
    ativo = models.BooleanField(default=True, db_column="news_bloco_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_bloco_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_bloco_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_bloco_excluido_em")

    class Meta:
        db_table = '"news"."news_artigo_bloco_tb"'
        ordering = ["ordem", "id"]

    def clean(self):
        self.titulo = texto_sem_html(self.titulo)
        self.conteudo = texto_sem_html(self.conteudo)
        if self.tipo == self.Tipo.VIDEO:
            self.url, self.identificador_externo = normalizar_link_publico(TipoLink.YOUTUBE, self.url)
            if not self.identificador_externo:
                raise ValidationError({"url": "Informe um vídeo válido do YouTube."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ArtigoFonte(SoftDeleteMixin):
    class Tipo(models.TextChoices):
        SITE_OFICIAL = "SITE_OFICIAL", "Site oficial"
        ORGAO_PUBLICO = "ORGAO_PUBLICO", "Órgão público"
        UNIVERSIDADE = "UNIVERSIDADE", "Universidade"
        ARTIGO_CIENTIFICO = "ARTIGO_CIENTIFICO", "Artigo científico"
        EMPRESA = "EMPRESA", "Empresa"
        ENTREVISTA = "ENTREVISTA", "Entrevista"
        REDE_SOCIAL_OFICIAL = "REDE_SOCIAL_OFICIAL", "Rede social oficial"
        DOCUMENTO_PUBLICO = "DOCUMENTO_PUBLICO", "Documento público"
        ASSESSORIA = "ASSESSORIA", "Assessoria"
        OUTRO = "OUTRO", "Outro"

    id = models.BigAutoField(primary_key=True, db_column="news_fonte_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_fonte_uuid")
    artigo = models.ForeignKey(Artigo, on_delete=models.CASCADE, related_name="fontes", db_column="news_fonte_fk_artigo")
    organizacao = models.ForeignKey("organizations.Empresa", on_delete=models.SET_NULL, null=True, blank=True, related_name="fontes_news", db_column="news_fonte_fk_organizacao")
    nome_fonte = models.CharField(max_length=180, blank=True, db_column="news_fonte_nome")
    titulo = models.CharField(max_length=180, db_column="news_fonte_titulo")
    url = models.URLField(max_length=500, db_column="news_fonte_url")
    tipo = models.CharField(max_length=30, choices=Tipo.choices, default=Tipo.OUTRO, db_column="news_fonte_tipo")
    autor_externo = models.CharField(max_length=180, blank=True, db_column="news_fonte_autor_externo")
    veiculo = models.CharField(max_length=160, blank=True, db_column="news_fonte_veiculo")
    data_original = models.DateField(null=True, blank=True, db_column="news_fonte_data_original")
    data_acesso = models.DateField(db_column="news_fonte_data_acesso")
    observacao = models.TextField(blank=True, db_column="news_fonte_observacao")
    principal = models.BooleanField(default=False, db_column="news_fonte_principal")
    verificada = models.BooleanField(default=False, db_column="news_fonte_verificada")
    ordem = models.PositiveIntegerField(default=0, db_column="news_fonte_ordem")
    exibir_publicamente = models.BooleanField(default=True, db_column="news_fonte_exibir_publicamente")
    ativo = models.BooleanField(default=True, db_column="news_fonte_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_fonte_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_fonte_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_fonte_excluido_em")

    class Meta:
        db_table = '"news"."news_artigo_fonte_tb"'
        ordering = ["ordem", "id"]

    def clean(self):
        self.url, _ = normalizar_link_publico(TipoLink.SITE, self.url)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class LinkRelacionado(SoftDeleteMixin):
    class Tipo(models.TextChoices):
        SITE = "SITE", "Site"
        REDE_SOCIAL = "REDE_SOCIAL", "Rede social"
        YOUTUBE = "YOUTUBE", "YouTube"
        DOCUMENTO = "DOCUMENTO", "Documento"
        REFERENCIA = "REFERENCIA", "Referência"
        FONTE = "FONTE", "Fonte"
        LINK_OFICIAL = "LINK_OFICIAL", "Link oficial"

    id = models.BigAutoField(primary_key=True, db_column="news_link_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_link_uuid")
    artigo = models.ForeignKey(Artigo, on_delete=models.CASCADE, related_name="links_relacionados", db_column="news_link_fk_artigo")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, db_column="news_link_tipo")
    rede = models.CharField(max_length=20, choices=TipoLink.choices, default=TipoLink.SITE, db_column="news_link_rede")
    titulo = models.CharField(max_length=180, db_column="news_link_titulo")
    url = models.URLField(max_length=500, db_column="news_link_url")
    identificador_externo = models.CharField(max_length=120, blank=True, db_column="news_link_identificador")
    nofollow = models.BooleanField(default=True, db_column="news_link_nofollow")
    ordem = models.PositiveIntegerField(default=0, db_column="news_link_ordem")
    ativo = models.BooleanField(default=True, db_column="news_link_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_link_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_link_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_link_excluido_em")

    class Meta:
        db_table = '"news"."news_link_relacionado_tb"'
        ordering = ["ordem", "id"]

    def clean(self):
        tipo_link = TipoLink.YOUTUBE if self.tipo == self.Tipo.YOUTUBE else self.rede
        self.url, self.identificador_externo = normalizar_link_publico(tipo_link, self.url)
        if self.tipo == self.Tipo.YOUTUBE and not self.identificador_externo:
            raise ValidationError({"url": "Informe um vídeo válido do YouTube."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class MidiaIncorporada(SoftDeleteMixin):
    class Tipo(models.TextChoices):
        YOUTUBE = "YOUTUBE", "YouTube"
        YUBOTUKA = "YUBOTUKA", "YuBotuka"

    id = models.BigAutoField(primary_key=True, db_column="news_midia_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_midia_uuid")
    artigo = models.ForeignKey(Artigo, on_delete=models.CASCADE, related_name="midias", db_column="news_midia_fk_artigo")
    episodio = models.ForeignKey("media.Episodio", on_delete=models.SET_NULL, null=True, blank=True, related_name="midias_news", db_column="news_midia_fk_episodio")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.YOUTUBE, db_column="news_midia_tipo")
    titulo = models.CharField(max_length=180, blank=True, db_column="news_midia_titulo")
    url = models.URLField(max_length=500, blank=True, db_column="news_midia_url")
    identificador_externo = models.CharField(max_length=120, blank=True, db_column="news_midia_identificador")
    ordem = models.PositiveIntegerField(default=0, db_column="news_midia_ordem")
    ativo = models.BooleanField(default=True, db_column="news_midia_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_midia_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_midia_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_midia_excluido_em")

    class Meta:
        db_table = '"news"."news_midia_incorporada_tb"'
        ordering = ["ordem", "id"]

    def clean(self):
        if self.tipo == self.Tipo.YOUTUBE:
            self.url, self.identificador_externo = normalizar_link_publico(TipoLink.YOUTUBE, self.url)
            if not self.identificador_externo:
                raise ValidationError({"url": "Informe um vídeo válido do YouTube."})
        elif not self.episodio_id:
            raise ValidationError({"episodio": "Selecione um conteúdo do YuBotuka."})

    @property
    def embed_url(self):
        return url_embed_youtube(self.identificador_externo) if self.tipo == self.Tipo.YOUTUBE else ""

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ImagemPublicacao(SoftDeleteMixin):
    class Tipo(models.TextChoices):
        CAPA = "CAPA", "Capa"
        GALERIA = "GALERIA", "Galeria"
        INFOGRAFICO = "INFOGRAFICO", "Infográfico"
        DOCUMENTO = "DOCUMENTO", "Documento"
        ILUSTRACAO = "ILUSTRACAO", "Ilustração"
        IMAGEM_EXTERNA = "IMAGEM_EXTERNA", "Imagem externa"

    class Licenca(models.TextChoices):
        PROPRIA = "PROPRIA", "Própria"
        CEDIDA_AUTOR = "CEDIDA_AUTOR", "Cedida pelo autor"
        ASSESSORIA = "ASSESSORIA", "Assessoria"
        DOMINIO_PUBLICO = "DOMINIO_PUBLICO", "Domínio público"
        CREATIVE_COMMONS = "CREATIVE_COMMONS", "Creative Commons"
        BANCO_LICENCIADO = "BANCO_LICENCIADO", "Banco licenciado"
        USO_AUTORIZADO = "USO_AUTORIZADO", "Uso autorizado"
        FONTE_EXTERNA = "FONTE_EXTERNA", "Fonte externa"
        DESCONHECIDA = "DESCONHECIDA", "Desconhecida"

    id = models.BigAutoField(primary_key=True, db_column="news_imagem_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_imagem_uuid")
    artigo = models.ForeignKey(Artigo, on_delete=models.CASCADE, related_name="imagens", db_column="news_imagem_fk_artigo")
    arquivo = models.ImageField(upload_to="news/publicacoes/", blank=True, db_column="news_imagem_arquivo")
    url_externa = models.URLField(max_length=500, blank=True, db_column="news_imagem_url_externa")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.GALERIA, db_column="news_imagem_tipo")
    titulo = models.CharField(max_length=180, blank=True, db_column="news_imagem_titulo")
    legenda = models.TextField(blank=True, db_column="news_imagem_legenda")
    texto_alternativo = models.CharField(max_length=250, db_column="news_imagem_texto_alternativo")
    credito = models.CharField(max_length=180, db_column="news_imagem_credito")
    autor_imagem = models.CharField(max_length=180, blank=True, db_column="news_imagem_autor")
    fonte = models.CharField(max_length=180, blank=True, db_column="news_imagem_fonte")
    url_fonte = models.URLField(max_length=500, blank=True, db_column="news_imagem_url_fonte")
    licenca = models.CharField(max_length=24, choices=Licenca.choices, db_column="news_imagem_licenca")
    url_licenca = models.URLField(max_length=500, blank=True, db_column="news_imagem_url_licenca")
    ordem = models.PositiveIntegerField(default=0, db_column="news_imagem_ordem")
    capa = models.BooleanField(default=False, db_column="news_imagem_capa")
    direitos_confirmados = models.BooleanField(default=False, db_column="news_imagem_direitos_confirmados")
    ativo = models.BooleanField(default=True, db_column="news_imagem_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_imagem_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_imagem_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_imagem_excluido_em")

    class Meta:
        db_table = '"news"."news_imagem_publicacao_tb"'
        ordering = ["ordem", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(arquivo__gt="") | models.Q(url_externa__gt=""), name="news_imagem_origem_ck"),
        ]

    def validar_direitos_publicacao(self):
        erros = {}
        if not self.credito:
            erros["credito"] = "Informe o crédito da imagem."
        if not self.texto_alternativo:
            erros["texto_alternativo"] = "Informe o texto alternativo."
        if self.url_externa and (not self.fonte or not self.url_fonte):
            erros["url_fonte"] = "Imagem externa exige fonte e URL de origem."
        if not self.licenca or self.licenca == self.Licenca.DESCONHECIDA:
            erros["licenca"] = "Selecione uma licença conhecida."
        if not self.direitos_confirmados:
            erros["direitos_confirmados"] = "Confirme os direitos de uso."
        if erros:
            raise ValidationError(erros)

    def clean(self):
        if bool(self.arquivo) == bool(self.url_externa):
            raise ValidationError("Informe um arquivo ou uma URL externa, não ambos.")
        validar_imagem_publica(self.arquivo)
        if self.url_externa:
            self.url_externa, _ = normalizar_link_publico(TipoLink.SITE, self.url_externa)
        if self.url_fonte:
            self.url_fonte, _ = normalizar_link_publico(TipoLink.SITE, self.url_fonte)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class HistoricoEditorial(SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column="news_historico_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_historico_uuid")
    artigo = models.ForeignKey(Artigo, on_delete=models.CASCADE, related_name="historico_editorial", db_column="news_historico_fk_artigo")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="historicos_news", db_column="news_historico_fk_usuario")
    status_anterior = models.CharField(max_length=24, blank=True, db_column="news_historico_status_anterior")
    status_novo = models.CharField(max_length=24, blank=True, db_column="news_historico_status_novo")
    acao = models.CharField(max_length=40, db_column="news_historico_acao")
    observacao = models.TextField(blank=True, db_column="news_historico_observacao")
    ativo = models.BooleanField(default=True, db_column="news_historico_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_historico_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_historico_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_historico_excluido_em")

    class Meta:
        db_table = '"news"."news_historico_editorial_tb"'
        ordering = ["-criado_em"]


class DestaqueEditorial(SoftDeleteMixin):
    class Posicao(models.TextChoices):
        HOME_PRINCIPAL = "HOME_PRINCIPAL", "Home principal"
        HOME_NOTICIAS = "HOME_NOTICIAS", "Home de notícias"
        CATEGORIA = "CATEGORIA", "Categoria"

    id = models.BigAutoField(primary_key=True, db_column="news_destaque_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_destaque_uuid")
    artigo = models.ForeignKey(Artigo, on_delete=models.CASCADE, related_name="posicoes_destaque", db_column="news_destaque_fk_artigo")
    categoria = models.ForeignKey(CategoriaNoticia, on_delete=models.SET_NULL, null=True, blank=True, related_name="destaques", db_column="news_destaque_fk_categoria")
    posicao = models.CharField(max_length=24, choices=Posicao.choices, db_column="news_destaque_posicao")
    ordem = models.PositiveIntegerField(default=0, db_column="news_destaque_ordem")
    inicio = models.DateTimeField(null=True, blank=True, db_column="news_destaque_inicio")
    fim = models.DateTimeField(null=True, blank=True, db_column="news_destaque_fim")
    ativo = models.BooleanField(default=True, db_column="news_destaque_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_destaque_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_destaque_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_destaque_excluido_em")

    class Meta:
        db_table = '"news"."news_destaque_editorial_tb"'
        ordering = ["ordem", "id"]
        indexes = [models.Index(fields=["posicao", "inicio", "fim"], name="news_destaque_periodo_idx")]


class AutorEspecialidade(SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column="news_autor_especialidade_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_autor_especialidade_uuid")
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE, db_column="news_autor_especialidade_fk_autor")
    especialidade = models.ForeignKey(EspecialidadeAutor, on_delete=models.PROTECT, db_column="news_autor_especialidade_fk_especialidade")
    ativo = models.BooleanField(default=True, db_column="news_autor_especialidade_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_autor_especialidade_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_autor_especialidade_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_autor_especialidade_excluido_em")

    class Meta:
        db_table = '"news"."news_autor_especialidade_rel_tb"'
        constraints = [models.UniqueConstraint(fields=["autor", "especialidade"], name="news_autor_especialidade_uk")]


class ArtigoTema(SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column="news_artigo_tema_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_artigo_tema_uuid")
    artigo = models.ForeignKey(Artigo, on_delete=models.CASCADE, db_column="news_artigo_tema_fk_artigo")
    tema = models.ForeignKey(Tema, on_delete=models.PROTECT, db_column="news_artigo_tema_fk_tema")
    ativo = models.BooleanField(default=True, db_column="news_artigo_tema_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_artigo_tema_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_artigo_tema_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_artigo_tema_excluido_em")

    class Meta:
        db_table = '"news"."news_artigo_tema_rel_tb"'
        constraints = [models.UniqueConstraint(fields=["artigo", "tema"], name="news_artigo_tema_uk")]


class ArtigoTag(SoftDeleteMixin):
    id = models.BigAutoField(primary_key=True, db_column="news_artigo_tag_id")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_column="news_artigo_tag_uuid")
    artigo = models.ForeignKey(Artigo, on_delete=models.CASCADE, db_column="news_artigo_tag_fk_artigo")
    tag = models.ForeignKey(Tag, on_delete=models.PROTECT, db_column="news_artigo_tag_fk_tag")
    ativo = models.BooleanField(default=True, db_column="news_artigo_tag_ativo")
    criado_em = models.DateTimeField(auto_now_add=True, db_column="news_artigo_tag_criado_em")
    atualizado_em = models.DateTimeField(auto_now=True, db_column="news_artigo_tag_atualizado_em")
    excluido_em = models.DateTimeField(null=True, blank=True, db_column="news_artigo_tag_excluido_em")

    class Meta:
        db_table = '"news"."news_artigo_tag_rel_tb"'
        constraints = [models.UniqueConstraint(fields=["artigo", "tag"], name="news_artigo_tag_uk")]
