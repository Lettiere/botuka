from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.domain import texto_sem_html, validar_imagem_publica
from apps.core.models import TimeStampedModel, UUIDModel


class SocialProfile(UUIDModel, TimeStampedModel):
    class Visibilidade(models.TextChoices):
        PUBLICO = 'PUBLICO', 'Público'
        RESTRITO = 'RESTRITO', 'Restrito'
        PRIVADO = 'PRIVADO', 'Privado'

    id = models.BigAutoField(primary_key=True)
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='social_profile')
    slug = models.SlugField(max_length=160, unique=True)
    nome_exibicao = models.CharField(max_length=120, blank=True)
    biografia = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='social/avatars/%Y/%m/', blank=True, null=True)
    visibilidade = models.CharField(max_length=10, choices=Visibilidade.choices, default=Visibilidade.PUBLICO, db_index=True)
    ativo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'social_profile_tb'
        ordering = ['nome_exibicao', 'slug']
        indexes = [models.Index(fields=['slug'], name='social_profile_slug_idx')]

    @property
    def nome_publico(self):
        return self.nome_exibicao or self.usuario.nome_exibicao or self.usuario.get_full_name() or self.usuario.get_username()

    @property
    def avatar_publico(self):
        return self.avatar or self.usuario.foto

    def get_absolute_url(self):
        return reverse('social:profile', kwargs={'slug': self.slug})

    def __str__(self):
        return self.nome_publico


class SocialFollow(UUIDModel):
    id = models.BigAutoField(primary_key=True)
    seguidor = models.ForeignKey(SocialProfile, on_delete=models.CASCADE, related_name='seguindo_relacoes')
    seguido = models.ForeignKey(SocialProfile, on_delete=models.CASCADE, related_name='seguidores_relacoes')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'social_follow_tb'
        constraints = [
            models.UniqueConstraint(fields=['seguidor', 'seguido'], name='social_follow_unique'),
            models.CheckConstraint(condition=~models.Q(seguidor=models.F('seguido')), name='social_follow_not_self'),
        ]
        indexes = [
            models.Index(fields=['seguidor', 'criado_em'], name='social_following_date_idx'),
            models.Index(fields=['seguido', 'criado_em'], name='social_followers_date_idx'),
        ]


class EmpresaSeguidor(UUIDModel):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='empresas_seguidas')
    empresa = models.ForeignKey('organizations.Empresa', on_delete=models.CASCADE, related_name='seguidores_sociais')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'social_empresa_seguidor_tb'
        constraints = [models.UniqueConstraint(fields=['usuario', 'empresa'], name='social_company_follow_unique')]
        indexes = [
            models.Index(fields=['usuario', 'criado_em'], name='social_user_company_date_idx'),
            models.Index(fields=['empresa', 'criado_em'], name='social_company_follow_date_idx'),
        ]


class SocialBlock(UUIDModel, TimeStampedModel):
    bloqueador = models.ForeignKey(SocialProfile, on_delete=models.CASCADE, related_name='bloqueios_feitos')
    bloqueado = models.ForeignKey(SocialProfile, on_delete=models.CASCADE, related_name='bloqueios_recebidos')

    class Meta:
        db_table = 'social_block_tb'
        constraints = [
            models.UniqueConstraint(fields=['bloqueador', 'bloqueado'], name='social_block_unique'),
            models.CheckConstraint(condition=~models.Q(bloqueador=models.F('bloqueado')), name='social_block_not_self'),
        ]


class SocialFollowRequest(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        APROVADO = 'APROVADO', 'Aprovado'
        RECUSADO = 'RECUSADO', 'Recusado'

    solicitante = models.ForeignKey(SocialProfile, on_delete=models.CASCADE, related_name='solicitacoes_enviadas')
    destinatario = models.ForeignKey(SocialProfile, on_delete=models.CASCADE, related_name='solicitacoes_recebidas')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE, db_index=True)
    decidido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'social_follow_request_tb'
        constraints = [
            models.UniqueConstraint(fields=['solicitante', 'destinatario'], condition=models.Q(status='PENDENTE'), name='social_follow_request_pending_unique'),
            models.CheckConstraint(condition=~models.Q(solicitante=models.F('destinatario')), name='social_follow_request_not_self'),
        ]


class SocialPost(UUIDModel, TimeStampedModel):
    class Visibilidade(models.TextChoices):
        PUBLICO = 'PUBLICO', 'Público'
        SEGUIDORES = 'SEGUIDORES', 'Seguidores'
        SOMENTE_EU = 'SOMENTE_EU', 'Somente eu'

    autor = models.ForeignKey(SocialProfile, on_delete=models.CASCADE, related_name='posts')
    imagem = models.ImageField(upload_to='social/posts/%Y/%m/', blank=True, validators=[validar_imagem_publica])
    legenda = models.TextField(blank=True, max_length=2200, validators=[texto_sem_html])
    visibilidade = models.CharField(max_length=12, choices=Visibilidade.choices, default=Visibilidade.PUBLICO, db_index=True)
    publicado_em = models.DateTimeField(default=timezone.now, db_index=True)
    feed_ate = models.DateTimeField(blank=True, db_index=True)
    ativo = models.BooleanField(default=True, db_index=True)
    conteudo_tipo = models.ForeignKey(ContentType, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    conteudo_id = models.PositiveBigIntegerField(null=True, blank=True)
    conteudo = GenericForeignKey('conteudo_tipo', 'conteudo_id')

    class Meta:
        db_table = 'social_post_tb'
        ordering = ['-publicado_em']
        indexes = [models.Index(fields=['ativo', 'feed_ate', 'publicado_em'], name='social_post_feed_idx')]
        constraints = [
            models.CheckConstraint(condition=(models.Q(imagem__gt='') | (models.Q(conteudo_tipo__isnull=False) & models.Q(conteudo_id__isnull=False))), name='social_post_has_content'),
        ]

    def save(self, *args, **kwargs):
        if not self.feed_ate:
            self.feed_ate = self.publicado_em + timedelta(days=7)
        self.full_clean()
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('social:post_detail', kwargs={'uuid': self.uuid})


class SocialStory(UUIDModel, TimeStampedModel):
    autor = models.ForeignKey(SocialProfile, on_delete=models.CASCADE, related_name='stories')
    imagem = models.ImageField(upload_to='social/stories/%Y/%m/', validators=[validar_imagem_publica])
    visibilidade = models.CharField(max_length=12, choices=SocialPost.Visibilidade.choices, default=SocialPost.Visibilidade.PUBLICO, db_index=True)
    publicado_em = models.DateTimeField(default=timezone.now, db_index=True)
    expira_em = models.DateTimeField(blank=True, db_index=True)
    ativo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'social_story_tb'
        ordering = ['-publicado_em']
        indexes = [models.Index(fields=['ativo', 'expira_em'], name='social_story_active_idx')]

    def save(self, *args, **kwargs):
        if not self.expira_em:
            self.expira_em = self.publicado_em + timedelta(hours=24)
        self.full_clean()
        return super().save(*args, **kwargs)


class SocialPostLike(UUIDModel):
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='curtidas')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='curtidas_sociais')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'social_post_like_tb'
        constraints = [models.UniqueConstraint(fields=['post', 'usuario'], name='social_post_like_unique')]


class SocialPostComment(UUIDModel, TimeStampedModel):
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='comentarios')
    autor = models.ForeignKey(SocialProfile, on_delete=models.CASCADE, related_name='comentarios')
    texto = models.TextField(max_length=1000, validators=[texto_sem_html])
    ativo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'social_post_comment_tb'
        ordering = ['criado_em']


class SocialPostSave(UUIDModel):
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='salvamentos')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts_sociais_salvos')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'social_post_save_tb'
        constraints = [models.UniqueConstraint(fields=['post', 'usuario'], name='social_post_save_unique')]


class SocialConversation(UUIDModel, TimeStampedModel):
    participantes = models.ManyToManyField(settings.AUTH_USER_MODEL, through='SocialConversationParticipant', related_name='conversas_sociais')
    ativo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'social_conversation_tb'
        ordering = ['-atualizado_em']


class SocialConversationParticipant(UUIDModel):
    conversa = models.ForeignKey(SocialConversation, on_delete=models.CASCADE, related_name='vinculos_participantes')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vinculos_conversas_sociais')
    entrou_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'social_conversation_participant_tb'
        constraints = [models.UniqueConstraint(fields=['conversa', 'usuario'], name='social_conversation_participant_unique')]


class SocialConversationRequest(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        ACEITA = 'ACEITA', 'Aceita'
        RECUSADA = 'RECUSADA', 'Recusada'

    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='solicitacoes_conversa_enviadas')
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='solicitacoes_conversa_recebidas')
    mensagem_inicial = models.TextField(max_length=2000, blank=True, validators=[texto_sem_html])
    post = models.ForeignKey(SocialPost, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitacoes_conversa')
    story = models.ForeignKey(SocialStory, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitacoes_conversa')
    conversa = models.OneToOneField(SocialConversation, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitacao_origem')
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDENTE, db_index=True)
    decidido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'social_conversation_request_tb'
        constraints = [
            models.UniqueConstraint(fields=['solicitante', 'destinatario'], condition=models.Q(status='PENDENTE'), name='social_conv_request_pending_unique'),
            models.CheckConstraint(condition=~models.Q(solicitante=models.F('destinatario')), name='social_conv_request_not_self'),
            models.CheckConstraint(condition=(models.Q(mensagem_inicial__gt='') | models.Q(post__isnull=False) | models.Q(story__isnull=False)), name='social_conv_request_has_content'),
        ]
        indexes = [models.Index(fields=['destinatario', 'status', 'criado_em'], name='social_conv_req_inbox_idx')]


class SocialMessage(UUIDModel, TimeStampedModel):
    conversa = models.ForeignKey(SocialConversation, on_delete=models.CASCADE, related_name='mensagens')
    remetente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='mensagens_sociais')
    texto = models.TextField(max_length=2000, blank=True, validators=[texto_sem_html])
    post = models.ForeignKey(SocialPost, on_delete=models.SET_NULL, null=True, blank=True, related_name='mensagens')
    story = models.ForeignKey(SocialStory, on_delete=models.SET_NULL, null=True, blank=True, related_name='mensagens')
    lida_em = models.DateTimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'social_message_tb'
        ordering = ['criado_em']
        constraints = [models.CheckConstraint(condition=(models.Q(texto__gt='') | models.Q(post__isnull=False) | models.Q(story__isnull=False)), name='social_message_has_content')]

    def clean(self):
        if self.conversa_id and self.remetente_id and not self.conversa.participantes.filter(pk=self.remetente_id).exists():
            raise ValidationError({'remetente': 'Somente participantes podem enviar mensagens.'})
