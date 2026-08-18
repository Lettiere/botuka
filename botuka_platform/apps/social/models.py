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

    class InteracaoPrivada(models.TextChoices):
        TODOS = 'TODOS', 'Todos'
        SEGUIDORES = 'SEGUIDORES', 'Seguidores'
        SEGUINDO = 'SEGUINDO', 'Pessoas que sigo'
        NINGUEM = 'NINGUEM', 'Ninguém'

    id = models.BigAutoField(primary_key=True)
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='social_profile')
    slug = models.SlugField(max_length=160, unique=True)
    nome_exibicao = models.CharField(max_length=120, blank=True)
    biografia = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='social/avatars/%Y/%m/', blank=True, null=True)
    visibilidade = models.CharField(max_length=10, choices=Visibilidade.choices, default=Visibilidade.PUBLICO, db_index=True)
    ativo = models.BooleanField(default=True, db_index=True)
    quem_pode_solicitar_mensagem = models.CharField(max_length=12, choices=InteracaoPrivada.choices, default=InteracaoPrivada.TODOS)
    quem_pode_responder_story = models.CharField(max_length=12, choices=InteracaoPrivada.choices, default=InteracaoPrivada.TODOS)
    permitir_reacoes = models.BooleanField(default=True)
    confirmacao_leitura = models.BooleanField(default=True)

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


class SocialStoryLike(UUIDModel):
    story = models.ForeignKey(SocialStory, on_delete=models.CASCADE, related_name='curtidas')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='curtidas_stories')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'social_story_like_tb'
        constraints = [models.UniqueConstraint(fields=['story', 'usuario'], name='social_story_like_unique')]
        indexes = [models.Index(fields=['story', 'criado_em'], name='social_story_like_idx')]


class SocialStoryReaction(UUIDModel, TimeStampedModel):
    class Tipo(models.TextChoices):
        LOVE = 'LOVE', 'Amei'
        HAHA = 'HAHA', 'Engraçado'
        HEART_EYES = 'HEART_EYES', 'Apaixonado'
        WOW = 'WOW', 'Surpreso'
        SAD = 'SAD', 'Triste'
        CLAP = 'CLAP', 'Aplausos'
        FIRE = 'FIRE', 'Incrível'

    story = models.ForeignKey(SocialStory, on_delete=models.CASCADE, related_name='reacoes')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reacoes_stories')
    tipo = models.CharField(max_length=12, choices=Tipo.choices)

    class Meta:
        db_table = 'social_story_reaction_tb'
        constraints = [models.UniqueConstraint(fields=['story', 'usuario'], name='social_story_reaction_unique')]
        indexes = [models.Index(fields=['story', 'tipo'], name='social_story_reaction_idx')]


class SocialStoryView(UUIDModel):
    story = models.ForeignKey(SocialStory, on_delete=models.CASCADE, related_name='visualizacoes')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stories_visualizados')
    quantidade = models.PositiveIntegerField(default=1)
    criado_em = models.DateTimeField(auto_now_add=True)
    ultima_visualizacao_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'social_story_view_tb'
        constraints = [models.UniqueConstraint(fields=['story', 'usuario'], name='social_story_view_unique')]
        indexes = [models.Index(fields=['story', 'criado_em'], name='social_story_view_idx')]


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


class SocialConversationRequestMessage(UUIDModel, TimeStampedModel):
    solicitacao = models.ForeignKey(
        SocialConversationRequest,
        on_delete=models.CASCADE,
        related_name='mensagens',
    )
    remetente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='mensagens_solicitacao_conversa',
    )
    texto = models.TextField(
        max_length=2000,
        blank=True,
        validators=[texto_sem_html],
    )
    post = models.ForeignKey(
        SocialPost,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mensagens_solicitacao_conversa',
    )
    story = models.ForeignKey(
        SocialStory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mensagens_solicitacao_conversa',
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'social_conversation_request_message_tb'
        ordering = ['criado_em']
        indexes = [
            models.Index(
                fields=['solicitacao', 'criado_em'],
                name='social_conv_req_msg_date_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(texto__gt='')
                    | models.Q(post__isnull=False)
                    | models.Q(story__isnull=False)
                ),
                name='social_conv_req_msg_content',
            ),
        ]

    def clean(self):
        if (
            self.solicitacao_id
            and self.remetente_id
            and self.remetente_id != self.solicitacao.solicitante_id
        ):
            raise ValidationError({
                'remetente': 'Somente o solicitante pode enviar mensagens enquanto a solicitação estiver pendente.'
            })

        if (
            self.solicitacao_id
            and self.solicitacao.status != SocialConversationRequest.Status.PENDENTE
        ):
            raise ValidationError({
                'solicitacao': 'Só é possível adicionar mensagens a uma solicitação pendente.'
            })

class SocialMessage(UUIDModel, TimeStampedModel):
    class Tipo(models.TextChoices):
        TEXT = 'TEXT', 'Texto'
        STORY_REPLY = 'STORY_REPLY', 'Resposta a Story'
        STORY_REACTION = 'STORY_REACTION', 'Reação a Story'
        SYSTEM = 'SYSTEM', 'Sistema'
    conversa = models.ForeignKey(SocialConversation, on_delete=models.CASCADE, related_name='mensagens')
    remetente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='mensagens_sociais')
    texto = models.TextField(max_length=2000, blank=True, validators=[texto_sem_html])
    post = models.ForeignKey(SocialPost, on_delete=models.SET_NULL, null=True, blank=True, related_name='mensagens')
    story = models.ForeignKey(SocialStory, on_delete=models.SET_NULL, null=True, blank=True, related_name='mensagens')
    tipo = models.CharField(max_length=16, choices=Tipo.choices, default=Tipo.TEXT, db_index=True)
    contexto_tipo = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    contexto_id = models.PositiveBigIntegerField(null=True, blank=True)
    contexto = GenericForeignKey('contexto_tipo', 'contexto_id')
    entregue_em = models.DateTimeField(null=True, blank=True)
    lida_em = models.DateTimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'social_message_tb'
        ordering = ['criado_em']
        indexes = [models.Index(fields=['conversa', 'criado_em'], name='social_message_conv_date_idx'), models.Index(fields=['conversa', 'lida_em'], name='social_message_unread_idx')]
        constraints = [models.CheckConstraint(condition=(models.Q(texto__gt='') | models.Q(post__isnull=False) | models.Q(story__isnull=False)), name='social_message_has_content')]

    def clean(self):
        if self.conversa_id and self.remetente_id and not self.conversa.participantes.filter(pk=self.remetente_id).exists():
            raise ValidationError({'remetente': 'Somente participantes podem enviar mensagens.'})


class SocialNotification(UUIDModel, TimeStampedModel):
    class Tipo(models.TextChoices):
        STORY_LIKE = 'STORY_LIKE', 'Curtida em Story'
        STORY_REACTION = 'STORY_REACTION', 'Reação em Story'
        STORY_REPLY = 'STORY_REPLY', 'Resposta a Story'
        MESSAGE_REQUEST = 'MESSAGE_REQUEST', 'Solicitação de mensagem'
        MESSAGE_REQUEST_ACCEPTED = 'MESSAGE_REQUEST_ACCEPTED', 'Solicitação aceita'
        NEW_MESSAGE = 'NEW_MESSAGE', 'Nova mensagem'
        NEW_FOLLOWER = 'NEW_FOLLOWER', 'Novo seguidor'
        FOLLOW_REQUEST = 'FOLLOW_REQUEST', 'Solicitação para seguir'
        FOLLOW_REQUEST_ACCEPTED = 'FOLLOW_REQUEST_ACCEPTED', 'Solicitação para seguir aceita'
        POST_LIKE = 'POST_LIKE', 'Curtida em post'
        POST_COMMENT = 'POST_COMMENT', 'Comentário em post'
        SYSTEM = 'SYSTEM', 'Sistema'

    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificacoes_sociais')
    ator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='notificacoes_sociais_geradas')
    tipo = models.CharField(max_length=32, choices=Tipo.choices, db_index=True)
    objeto_tipo = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    objeto_id = models.PositiveBigIntegerField(null=True, blank=True)
    objeto = GenericForeignKey('objeto_tipo', 'objeto_id')
    destino = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    lida_em = models.DateTimeField(null=True, blank=True, db_index=True)
    chave_dedupe = models.CharField(max_length=160, blank=True)

    class Meta:
        db_table = 'social_notification_tb'
        ordering = ['-criado_em']
        indexes = [models.Index(fields=['destinatario', 'lida_em', 'criado_em'], name='social_notification_inbox_idx')]
        constraints = [models.UniqueConstraint(fields=['destinatario', 'chave_dedupe'], condition=~models.Q(chave_dedupe=''), name='social_notification_dedupe_unique')]


class SocialReport(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        ABERTA = 'ABERTA', 'Aberta'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        ENCERRADA = 'ENCERRADA', 'Encerrada'

    denunciante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='denuncias_sociais')
    alvo_tipo = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name='+')
    alvo_id = models.PositiveBigIntegerField()
    alvo = GenericForeignKey('alvo_tipo', 'alvo_id')
    motivo = models.CharField(max_length=80)
    descricao = models.TextField(max_length=1000, blank=True, validators=[texto_sem_html])
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ABERTA, db_index=True)

    class Meta:
        db_table = 'social_report_tb'
        constraints = [models.UniqueConstraint(fields=['denunciante', 'alvo_tipo', 'alvo_id'], condition=models.Q(status='ABERTA'), name='social_report_open_unique')]
        indexes = [models.Index(fields=['status', 'criado_em'], name='social_report_queue_idx')]
