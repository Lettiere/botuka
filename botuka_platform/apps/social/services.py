from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import hashlib
import logging
import uuid

from django.conf import settings
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.analytics.services import register_event
from apps.core.seo.context import _consent


logger = logging.getLogger(__name__)

from .models import (
    EmpresaSeguidor, SocialBlock, SocialConversation, SocialConversationParticipant,
    SocialConversationRequest, SocialConversationRequestMessage,
    SocialFollow, SocialFollowRequest, SocialMessage,
    SocialNotification, SocialPost, SocialPostComment, SocialPostLike,
    SocialPostSave, SocialProfile, SocialReport, SocialStory, SocialStoryLike,
    SocialStoryReaction, SocialStoryView,
)


def _authenticated(usuario):
    if not usuario or not usuario.is_authenticated:
        raise PermissionDenied('Autenticação necessária.')


def _profile(alvo):
    return alvo if isinstance(alvo, SocialProfile) else get_or_create_social_profile(alvo)


def _slug_for(usuario):
    base = slugify(usuario.get_username())[:140] or f'usuario-{str(usuario.uuid)[:8]}'
    if not SocialProfile.objects.filter(slug=base).exists():
        return base
    candidate = f'{base[:131]}-{str(usuario.uuid)[:8]}'
    if not SocialProfile.objects.filter(slug=candidate).exists():
        return candidate
    return f'{base[:122]}-{usuario.pk}-{str(usuario.uuid)[:8]}'


@transaction.atomic
def get_or_create_social_profile(usuario):
    if not usuario or not usuario.pk:
        raise ValueError('Usuário persistido é obrigatório.')
    existing = SocialProfile.objects.filter(usuario=usuario).first()
    if existing:
        return existing
    defaults = {
        'slug': _slug_for(usuario),
        'nome_exibicao': usuario.nome_exibicao or usuario.get_full_name() or usuario.get_username(),
        'biografia': usuario.biografia,
    }
    try:
        with transaction.atomic():
            return SocialProfile.objects.create(usuario=usuario, **defaults)
    except IntegrityError:
        return SocialProfile.objects.get(usuario=usuario)


@transaction.atomic
def sincronizar_perfil_publico(usuario, origem='platform', *, nome_exibicao=None, biografia=None, avatar=None):
    if origem not in {'platform', 'social'}:
        raise ValueError('Origem de sincronização inválida.')
    profile = get_or_create_social_profile(usuario)
    if origem == 'social':
        usuario.nome_exibicao = nome_exibicao if nome_exibicao is not None else usuario.nome_exibicao
        usuario.biografia = biografia if biografia is not None else usuario.biografia
        update_fields = ['nome_exibicao', 'biografia', 'atualizado_em']
        if avatar is not None:
            usuario.foto = avatar
            update_fields.append('foto')
        usuario.save(update_fields=update_fields)
    profile.nome_exibicao = usuario.nome_exibicao or usuario.get_full_name() or usuario.get_username()
    profile.biografia = usuario.biografia
    profile.avatar = usuario.foto.name if usuario.foto else None
    profile.save(update_fields=['nome_exibicao', 'biografia', 'avatar', 'atualizado_em'])
    return profile


def _blocked(a, b):
    return SocialBlock.objects.filter(
        models.Q(bloqueador=a, bloqueado=b) | models.Q(bloqueador=b, bloqueado=a)
    ).exists()


def _rate_limit(usuario, action, *, limit=20, window=60):
    key = f'social:rate:{action}:{usuario.pk}'
    try:
        value = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)
        value = 1
    if value > limit:
        raise PermissionDenied('Muitas tentativas. Aguarde e tente novamente.')


def _interaction_allowed(actor, target, policy):
    if policy == SocialProfile.InteracaoPrivada.NINGUEM:
        return False
    if policy == SocialProfile.InteracaoPrivada.TODOS:
        return True
    actor_profile = get_or_create_social_profile(actor)
    target_profile = get_or_create_social_profile(target)
    if policy == SocialProfile.InteracaoPrivada.SEGUIDORES:
        return SocialFollow.objects.filter(seguidor=actor_profile, seguido=target_profile).exists()
    return SocialFollow.objects.filter(seguidor=target_profile, seguido=actor_profile).exists()


def criar_notificacao(destinatario, tipo, *, ator=None, objeto=None, destino='', metadata=None, chave_dedupe=''):
    if ator and ator.pk == destinatario.pk:
        return None, False
    defaults = {'ator': ator, 'tipo': tipo, 'destino': destino, 'metadata': metadata or {}}
    if objeto is not None:
        defaults.update({'objeto_tipo': ContentType.objects.get_for_model(objeto), 'objeto_id': objeto.pk})
    if chave_dedupe:
        return SocialNotification.objects.get_or_create(destinatario=destinatario, chave_dedupe=chave_dedupe, defaults=defaults)
    return SocialNotification.objects.create(destinatario=destinatario, **defaults), True


@transaction.atomic
def seguir_usuario(usuario, alvo):
    _authenticated(usuario)
    seguidor = get_or_create_social_profile(usuario)
    seguido = _profile(alvo)
    if seguidor.pk == seguido.pk:
        raise ValidationError('Não é possível seguir a si mesmo.')
    if _blocked(seguidor, seguido):
        raise PermissionDenied('Esta interação não está disponível.')
    if seguido.visibilidade == SocialProfile.Visibilidade.PRIVADO:
        request, created = SocialFollowRequest.objects.get_or_create(
            solicitante=seguidor, destinatario=seguido,
            status=SocialFollowRequest.Status.PENDENTE,
        )
        if created:
            criar_notificacao(seguido.usuario, SocialNotification.Tipo.FOLLOW_REQUEST, ator=usuario, objeto=request, destino=seguidor.get_absolute_url(), chave_dedupe=f'follow-request:{request.pk}')
        return request, created
    follow, created = SocialFollow.objects.get_or_create(seguidor=seguidor, seguido=seguido)
    if created:
        criar_notificacao(seguido.usuario, SocialNotification.Tipo.NEW_FOLLOWER, ator=usuario, objeto=follow, destino=seguidor.get_absolute_url(), chave_dedupe=f'new-follower:{follow.pk}')
    return follow, created


@transaction.atomic
def deixar_de_seguir_usuario(usuario, alvo):
    _authenticated(usuario)
    seguidor = get_or_create_social_profile(usuario)
    seguido = _profile(alvo)
    return SocialFollow.objects.filter(seguidor=seguidor, seguido=seguido).delete()[0]


def usuario_segue_usuario(usuario, alvo):
    if not usuario or not usuario.is_authenticated:
        return False
    try:
        seguidor = usuario.social_profile
    except SocialProfile.DoesNotExist:
        return False
    return SocialFollow.objects.filter(seguidor=seguidor, seguido=_profile(alvo)).exists()


@transaction.atomic
def seguir_empresa(usuario, empresa):
    _authenticated(usuario)
    return EmpresaSeguidor.objects.get_or_create(usuario=usuario, empresa=empresa)


@transaction.atomic
def deixar_de_seguir_empresa(usuario, empresa):
    _authenticated(usuario)
    return EmpresaSeguidor.objects.filter(usuario=usuario, empresa=empresa).delete()[0]


def usuario_segue_empresa(usuario, empresa):
    return bool(usuario and usuario.is_authenticated and EmpresaSeguidor.objects.filter(usuario=usuario, empresa=empresa).exists())


def registrar_evento_social(request, event_name, object_type, object_id, context):
    if not settings.ENABLE_ANALYTICS or not _consent(request).get('analytics'):
        return None
    identity = str(request.user.uuid)
    session = request.session.session_key or identity
    digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
    return register_event(request, {
        'event_name': event_name,
        'visitor_id': digest(f'user:{identity}'),
        'session_id': digest(f'session:{session}'),
        'object_type': object_type,
        'object_id': object_id,
        'path': request.path,
        'metadata': {'context': context, 'page_type': 'social_action'},
        'dedupe_key': str(uuid.uuid4()),
    })


def pode_ver_post(usuario, post):
    if not post.ativo:
        return False
    viewer = get_or_create_social_profile(usuario) if usuario and usuario.is_authenticated else None
    if viewer and viewer.pk == post.autor_id:
        return True
    if viewer and _blocked(viewer, post.autor):
        return False
    follows = viewer and SocialFollow.objects.filter(seguidor=viewer, seguido=post.autor).exists()
    author_visibility = SocialProfile.objects.filter(pk=post.autor_id).values_list('visibilidade', flat=True).get()
    if author_visibility == SocialProfile.Visibilidade.PRIVADO:
        return bool(follows)
    if post.visibilidade == SocialPost.Visibilidade.SOMENTE_EU:
        return False
    if post.visibilidade == SocialPost.Visibilidade.SEGUIDORES:
        return bool(follows)
    return True


@transaction.atomic
def criar_post(usuario, *, imagem=None, legenda='', visibilidade=SocialPost.Visibilidade.PUBLICO):
    _authenticated(usuario)
    if not imagem:
        raise ValidationError({'imagem': 'Selecione uma imagem.'})
    post = SocialPost(autor=get_or_create_social_profile(usuario), imagem=imagem, legenda=legenda, visibilidade=visibilidade)
    post.save()
    return post


@transaction.atomic
def criar_story(usuario, *, imagem, visibilidade=SocialPost.Visibilidade.PUBLICO):
    _authenticated(usuario)
    story = SocialStory(autor=get_or_create_social_profile(usuario), imagem=imagem, visibilidade=visibilidade)
    story.save()
    return story


@transaction.atomic
def alternar_curtida_story(usuario, story):
    _authenticated(usuario)
    _rate_limit(usuario, 'story-like', limit=30)
    from .selectors import story_visivel_para
    if not story_visivel_para(usuario, story.uuid):
        raise PermissionDenied
    like, created = SocialStoryLike.objects.get_or_create(story=story, usuario=usuario)
    if not created:
        like.delete()
        return False
    criar_notificacao(story.autor.usuario, SocialNotification.Tipo.STORY_LIKE, ator=usuario, objeto=story, destino=story.get_absolute_url() if hasattr(story, 'get_absolute_url') else f'/social/story/{story.uuid}/', chave_dedupe=f'story-like:{story.pk}:{usuario.pk}')
    return True


@transaction.atomic
def reagir_story(usuario, story, tipo=None):
    _authenticated(usuario)
    _rate_limit(usuario, 'story-reaction', limit=20)
    from .selectors import story_visivel_para
    if not story_visivel_para(usuario, story.uuid) or not story.autor.permitir_reacoes:
        raise PermissionDenied
    if not tipo:
        SocialStoryReaction.objects.filter(story=story, usuario=usuario).delete()
        return None
    if tipo not in SocialStoryReaction.Tipo.values:
        raise ValidationError('Reação inválida.')
    reaction, _ = SocialStoryReaction.objects.update_or_create(story=story, usuario=usuario, defaults={'tipo': tipo})
    criar_notificacao(story.autor.usuario, SocialNotification.Tipo.STORY_REACTION, ator=usuario, objeto=story, destino=f'/social/story/{story.uuid}/', metadata={'reaction': tipo}, chave_dedupe=f'story-reaction:{story.pk}:{usuario.pk}:{tipo}')
    return reaction


@transaction.atomic
def registrar_visualizacao_story(usuario, story):
    if not usuario or not usuario.is_authenticated or usuario.pk == story.autor.usuario_id:
        return None, False

    visualizacao, criada = SocialStoryView.objects.select_for_update().get_or_create(
        story=story,
        usuario=usuario,
        defaults={'quantidade': 1},
    )

    if not criada:
        SocialStoryView.objects.filter(pk=visualizacao.pk).update(
            quantidade=models.F('quantidade') + 1,
            ultima_visualizacao_em=timezone.now(),
        )
        visualizacao.refresh_from_db(
            fields=['quantidade', 'ultima_visualizacao_em']
        )

    return visualizacao, criada


def insights_story(usuario, story):
    _authenticated(usuario)

    if story.autor.usuario_id != usuario.pk:
        raise PermissionDenied

    visualizacoes = (
        story.visualizacoes.aggregate(
            total=models.Sum('quantidade')
        )['total']
        or 0
    )

    return {
        'visualizacoes': visualizacoes,
        'alcance': story.visualizacoes.count(),
        'curtidas': story.curtidas.count(),
        'reacoes': story.reacoes.count(),
        'respostas': story.mensagens.filter(
            tipo=SocialMessage.Tipo.STORY_REPLY
        ).count(),
        'novas_conversas': story.solicitacoes_conversa.filter(
            status=SocialConversationRequest.Status.ACEITA
        ).count(),
    }


@transaction.atomic
def curtir_post(usuario, post):
    _authenticated(usuario)
    if not pode_ver_post(usuario, post):
        raise PermissionDenied
    like, created = SocialPostLike.objects.get_or_create(usuario=usuario, post=post)
    if created:
        criar_notificacao(post.autor.usuario, SocialNotification.Tipo.POST_LIKE, ator=usuario, objeto=post, destino=post.get_absolute_url(), chave_dedupe=f'post-like:{post.pk}:{usuario.pk}')
    return like, created


def descurtir_post(usuario, post):
    _authenticated(usuario)
    return SocialPostLike.objects.filter(usuario=usuario, post=post).delete()[0]


@transaction.atomic
def comentar_post(usuario, post, texto):
    _authenticated(usuario)
    if not pode_ver_post(usuario, post):
        raise PermissionDenied
    comment = SocialPostComment(post=post, autor=get_or_create_social_profile(usuario), texto=(texto or '').strip())
    comment.full_clean()
    comment.save()
    criar_notificacao(post.autor.usuario, SocialNotification.Tipo.POST_COMMENT, ator=usuario, objeto=comment, destino=post.get_absolute_url(), chave_dedupe=f'post-comment:{comment.pk}')
    return comment


def salvar_post(usuario, post):
    _authenticated(usuario)
    if not pode_ver_post(usuario, post):
        raise PermissionDenied
    return SocialPostSave.objects.get_or_create(usuario=usuario, post=post)


def remover_post_salvo(usuario, post):
    _authenticated(usuario)
    return SocialPostSave.objects.filter(usuario=usuario, post=post).delete()[0]


@transaction.atomic
def remover_post(usuario, post):
    _authenticated(usuario)
    if post.autor.usuario_id != usuario.pk:
        raise PermissionDenied('Somente o autor pode remover esta publicação.')
    post.ativo = False
    post.save(update_fields=['ativo', 'atualizado_em'])
    return post


@transaction.atomic
def remover_story(usuario, story):
    # BOTUKA_STORY_DELETE_AUDIT
    logger.warning(
        "BOTUKA_STORY_DELETE_AUDIT story=%s pk=%s autor=%s ativo_antes=%s expira=%s",
        getattr(story, "uuid", None),
        getattr(story, "pk", None),
        getattr(getattr(story, "autor", None), "usuario_id", None),
        getattr(story, "ativo", None),
        getattr(story, "expira_em", None),
    )

    _authenticated(usuario)
    if story.autor.usuario_id != usuario.pk:
        raise PermissionDenied('Somente o autor pode remover este Story.')
    story.ativo = False
    story.save(update_fields=['ativo', 'atualizado_em'])
    return story


@transaction.atomic
def decidir_follow_request(usuario, solicitacao, aprovar):
    _authenticated(usuario)
    if solicitacao.destinatario.usuario_id != usuario.pk or solicitacao.status != SocialFollowRequest.Status.PENDENTE:
        raise PermissionDenied
    solicitacao.status = SocialFollowRequest.Status.APROVADO if aprovar else SocialFollowRequest.Status.RECUSADO
    solicitacao.decidido_em = timezone.now()
    solicitacao.save(update_fields=['status', 'decidido_em', 'atualizado_em'])
    if aprovar and not _blocked(solicitacao.solicitante, solicitacao.destinatario):
        SocialFollow.objects.get_or_create(seguidor=solicitacao.solicitante, seguido=solicitacao.destinatario)
        criar_notificacao(solicitacao.solicitante.usuario, SocialNotification.Tipo.FOLLOW_REQUEST_ACCEPTED, ator=usuario, objeto=solicitacao, destino=solicitacao.destinatario.get_absolute_url(), chave_dedupe=f'follow-request-accepted:{solicitacao.pk}')
    return solicitacao


@transaction.atomic
def bloquear_perfil(usuario, alvo):
    _authenticated(usuario)
    ator = get_or_create_social_profile(usuario)
    alvo = _profile(alvo)
    if ator.pk == alvo.pk:
        raise ValidationError('Não é possível bloquear a si mesmo.')
    block, created = SocialBlock.objects.get_or_create(bloqueador=ator, bloqueado=alvo)
    SocialFollow.objects.filter(models.Q(seguidor=ator, seguido=alvo) | models.Q(seguidor=alvo, seguido=ator)).delete()
    SocialFollowRequest.objects.filter(models.Q(solicitante=ator, destinatario=alvo) | models.Q(solicitante=alvo, destinatario=ator), status='PENDENTE').update(status='RECUSADO', decidido_em=timezone.now())
    return block, created


def desbloquear_perfil(usuario, alvo):
    _authenticated(usuario)
    return SocialBlock.objects.filter(bloqueador__usuario=usuario, bloqueado=_profile(alvo)).delete()[0]


def compartilhar_conteudo(usuario, objeto, *, legenda='', visibilidade=SocialPost.Visibilidade.PUBLICO):
    _authenticated(usuario)
    allowed = {'recruitment.vaga', 'events.evento', 'services.servico', 'products.produto', 'news.artigo', 'tourism.localturistico', 'media.video', 'sports.campeonato', 'organizations.empresa'}
    label = objeto._meta.label_lower
    if label not in allowed:
        raise ValidationError('Este tipo de conteúdo não pode ser compartilhado.')
    from apps.core.search.registry import default_registry
    public_queryset = next((spec.queryset() for spec in default_registry() if spec.queryset().model is type(objeto)), None)
    if public_queryset is None or not public_queryset.filter(pk=objeto.pk).exists():
        raise ValidationError('Somente conteúdo público e publicado pode ser compartilhado.')
    post = SocialPost(
        autor=get_or_create_social_profile(usuario), legenda=legenda,
        visibilidade=visibilidade, conteudo_tipo=ContentType.objects.get_for_model(objeto),
        conteudo_id=objeto.pk,
    )
    post.save()
    return post




def _broadcast_social_message(message):
    channel_layer = get_channel_layer()

    if channel_layer is None:
        return

    group_name = (
        f"social_conversation_{str(message.conversa.uuid).replace('-', '_')}"
    )

    try:
        sender_name = message.remetente.social_profile.nome_publico
    except Exception:
        sender_name = (
            message.remetente.nome_exibicao
            or message.remetente.get_full_name()
            or message.remetente.get_username()
        )

    payload = {
        "id": str(message.uuid),
        "conversation": str(message.conversa.uuid),
        "sender_id": str(message.remetente_id),
        "sender_name": sender_name,
        "text": message.texto or "",
        "created_at": message.criado_em.isoformat(),
        "status": (
            "read"
            if message.lida_em
            else "delivered"
            if message.entregue_em
            else "sent"
        ),
    }

    def publish():

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "chat.message",
                "message": payload,
            },
        )

    transaction.on_commit(publish)


@transaction.atomic
def enviar_mensagem(usuario, conversa, *, texto='', post=None, story=None):
    _authenticated(usuario)
    if not conversa.ativo or not conversa.participantes.filter(pk=usuario.pk).exists():
        raise PermissionDenied('Conversa indisponível.')
    _rate_limit(usuario, 'message', limit=30)
    other = conversa.participantes.exclude(pk=usuario.pk).first()
    if other and _blocked(get_or_create_social_profile(usuario), get_or_create_social_profile(other)):
        raise PermissionDenied('Esta interação não está disponível.')
    message_type = SocialMessage.Tipo.STORY_REPLY if story else SocialMessage.Tipo.TEXT
    message = SocialMessage(conversa=conversa, remetente=usuario, texto=(texto or '').strip(), post=post, story=story, tipo=message_type, entregue_em=timezone.now())
    message.full_clean()
    message.save()

    SocialConversation.objects.filter(
        pk=conversa.pk,
    ).update(
        atualizado_em=timezone.now(),
    )
    if other:
        criar_notificacao(other, SocialNotification.Tipo.STORY_REPLY if story else SocialNotification.Tipo.NEW_MESSAGE, ator=usuario, objeto=story or message, destino=f'/social/mensagens/{conversa.uuid}/', chave_dedupe=f'message:{message.pk}')
    _broadcast_social_message(message)

    return message


def _conversation_between(a, b):
    return SocialConversation.objects.filter(ativo=True, participantes=a).filter(participantes=b).distinct().first()


@transaction.atomic
def solicitar_ou_enviar_conversa(
    usuario,
    destinatario,
    *,
    texto='',
    post=None,
    story=None,
):
    _authenticated(usuario)

    if usuario.pk == destinatario.pk:
        raise ValidationError('Escolha outra pessoa.')

    origem = get_or_create_social_profile(usuario)
    destino = get_or_create_social_profile(destinatario)

    if _blocked(origem, destino):
        raise PermissionDenied(
            'Esta interação não está disponível.'
        )

    if not _interaction_allowed(
        usuario,
        destinatario,
        destino.quem_pode_solicitar_mensagem,
    ):
        raise PermissionDenied(
            'Este perfil não recebe solicitações suas.'
        )

    if story and not _interaction_allowed(
        usuario,
        destinatario,
        destino.quem_pode_responder_story,
    ):
        raise PermissionDenied(
            'Este perfil não recebe respostas suas ao Story.'
        )

    # Se a conversa já foi aceita anteriormente,
    # a mensagem entra diretamente no chat normal.
    conversa = _conversation_between(
        usuario,
        destinatario,
    )

    if conversa:
        return (
            enviar_mensagem(
                usuario,
                conversa,
                texto=texto,
                post=post,
                story=story,
            ),
            False,
        )

    # Mantém a política atual após uma recusa.
    if SocialConversationRequest.objects.filter(
        solicitante=usuario,
        destinatario=destinatario,
        status=SocialConversationRequest.Status.RECUSADA,
    ).exists():
        raise PermissionDenied(
            'Uma solicitação anterior foi recusada.'
        )

    texto_limpo = (texto or '').strip()

    # Limite aplicado aos envios que ainda estão fora
    # de uma conversa aceita.
    _rate_limit(
        usuario,
        'conversation-request',
        limit=5,
        window=3600,
    )

    # Bloqueia a linha quando ela já existe para evitar
    # concorrência criando mensagens simultaneamente.
    pedido = (
        SocialConversationRequest.objects
        .select_for_update()
        .filter(
            solicitante=usuario,
            destinatario=destinatario,
            status=SocialConversationRequest.Status.PENDENTE,
        )
        .first()
    )

    pedido_criado = pedido is None

    if pedido_criado:
        pedido = SocialConversationRequest(
            solicitante=usuario,
            destinatario=destinatario,

            # Campos legados continuam contendo a primeira
            # mensagem para compatibilidade.
            mensagem_inicial=texto_limpo,
            post=post,
            story=story,

            status=SocialConversationRequest.Status.PENDENTE,
        )

        pedido.full_clean()
        pedido.save()

    # Cada envio passa a ser um registro próprio dentro
    # da única solicitação pendente.
    mensagem_pendente = SocialConversationRequestMessage(
        solicitacao=pedido,
        remetente=usuario,
        texto=texto_limpo,
        post=post,
        story=story,
        ativo=True,
    )

    mensagem_pendente.full_clean()
    mensagem_pendente.save()

    # Uma única notificação representa a solicitação.
    # A chave continua deduplicada pelo pedido.
    if pedido_criado:
        criar_notificacao(
            destinatario,
            SocialNotification.Tipo.MESSAGE_REQUEST,
            ator=usuario,
            objeto=pedido,
            destino='/social/mensagens/',
            chave_dedupe=f'message-request:{pedido.pk}',
        )

    # True continua significando:
    # "a mensagem está dentro do fluxo de solicitação",
    # e não "foi criada uma nova solicitação".
    return pedido, True


@transaction.atomic
def decidir_solicitacao_conversa(
    usuario,
    pedido,
    aceitar,
):
    _authenticated(usuario)

    pedido = (
        SocialConversationRequest.objects
        .select_for_update()
        .select_related(
            'solicitante',
            'destinatario',
        )
        .get(pk=pedido.pk)
    )

    if (
        pedido.destinatario_id != usuario.pk
        or pedido.status
        != SocialConversationRequest.Status.PENDENTE
    ):
        raise PermissionDenied

    pedido.decidido_em = timezone.now()

    if not aceitar:
        pedido.status = (
            SocialConversationRequest.Status.RECUSADA
        )

        pedido.save(
            update_fields=[
                'status',
                'decidido_em',
                'atualizado_em',
            ]
        )

        return pedido

    if _blocked(
        get_or_create_social_profile(
            pedido.solicitante
        ),
        get_or_create_social_profile(usuario),
    ):
        raise PermissionDenied

    conversa = (
        _conversation_between(
            pedido.solicitante,
            usuario,
        )
        or SocialConversation.objects.create()
    )

    SocialConversationParticipant.objects.bulk_create(
        [
            SocialConversationParticipant(
                conversa=conversa,
                usuario=pedido.solicitante,
            ),
            SocialConversationParticipant(
                conversa=conversa,
                usuario=usuario,
            ),
        ],
        ignore_conflicts=True,
    )

    # Captura todas as mensagens enquanto o pedido
    # ainda está PENDENTE, pois o clean() do model
    # proíbe novos itens depois da decisão.
    mensagens_pendentes = list(
        pedido.mensagens
        .filter(ativo=True)
        .select_related(
            'post',
            'story',
        )
        .order_by(
            'criado_em',
            'pk',
        )
    )

    pedido.status = (
        SocialConversationRequest.Status.ACEITA
    )

    pedido.conversa = conversa

    pedido.save(
        update_fields=[
            'status',
            'conversa',
            'decidido_em',
            'atualizado_em',
        ]
    )

    # Converte todas as mensagens pendentes em
    # SocialMessage somente após o aceite.
    #
    # Não usamos enviar_mensagem() aqui porque:
    # - não queremos consumir rate limit durante aceite;
    # - não queremos uma notificação nova por mensagem antiga;
    # - precisamos preservar o horário original.
    for pendente in mensagens_pendentes:
        tipo = (
            SocialMessage.Tipo.STORY_REPLY
            if pendente.story_id
            else SocialMessage.Tipo.TEXT
        )

        mensagem = SocialMessage(
            conversa=conversa,
            remetente=pedido.solicitante,
            texto=pendente.texto,
            post=pendente.post,
            story=pendente.story,
            tipo=tipo,
            entregue_em=timezone.now(),
            ativo=True,
        )

        mensagem.full_clean()
        mensagem.save()

        # Preserva a cronologia real de quando cada
        # mensagem ainda pendente foi enviada.
        SocialMessage.objects.filter(
            pk=mensagem.pk,
        ).update(
            criado_em=pendente.criado_em,
            atualizado_em=pendente.atualizado_em,
        )

    # Compatibilidade defensiva com algum registro legado
    # que eventualmente não tenha sido migrado para
    # SocialConversationRequestMessage.
    if (
        not mensagens_pendentes
        and (
            (pedido.mensagem_inicial or '').strip()
            or pedido.post_id
            or pedido.story_id
        )
    ):
        mensagem = SocialMessage(
            conversa=conversa,
            remetente=pedido.solicitante,
            texto=(pedido.mensagem_inicial or '').strip(),
            post=pedido.post,
            story=pedido.story,
            tipo=(
                SocialMessage.Tipo.STORY_REPLY
                if pedido.story_id
                else SocialMessage.Tipo.TEXT
            ),
            entregue_em=timezone.now(),
            ativo=True,
        )

        mensagem.full_clean()
        mensagem.save()

    criar_notificacao(
        pedido.solicitante,
        SocialNotification.Tipo.MESSAGE_REQUEST_ACCEPTED,
        ator=usuario,
        objeto=pedido,
        destino=f'/social/mensagens/{conversa.uuid}/',
        chave_dedupe=(
            f'message-request-accepted:{pedido.pk}'
        ),
    )

    return pedido


@transaction.atomic
def marcar_conversa_lida(usuario, conversa):
    _authenticated(usuario)
    if not conversa.participantes.filter(pk=usuario.pk).exists():
        raise PermissionDenied
    profile = get_or_create_social_profile(usuario)
    if not profile.confirmacao_leitura:
        return 0
    return conversa.mensagens.filter(lida_em__isnull=True).exclude(remetente=usuario).update(lida_em=timezone.now())


def marcar_notificacao_lida(usuario, notificacao):
    _authenticated(usuario)
    if notificacao.destinatario_id != usuario.pk:
        raise PermissionDenied
    if not notificacao.lida_em:
        notificacao.lida_em = timezone.now()
        notificacao.save(update_fields=['lida_em', 'atualizado_em'])
    return notificacao


def marcar_todas_notificacoes_lidas(usuario):
    _authenticated(usuario)
    return SocialNotification.objects.filter(destinatario=usuario, lida_em__isnull=True).update(lida_em=timezone.now())


@transaction.atomic
def denunciar(usuario, alvo, *, motivo, descricao=''):
    _authenticated(usuario)
    _rate_limit(usuario, 'report', limit=5, window=3600)
    allowed = {SocialProfile, SocialPost, SocialStory, SocialMessage}
    if type(alvo) not in allowed:
        raise ValidationError('Tipo de denúncia inválido.')
    report, created = SocialReport.objects.get_or_create(denunciante=usuario, alvo_tipo=ContentType.objects.get_for_model(alvo), alvo_id=alvo.pk, status=SocialReport.Status.ABERTA, defaults={'motivo': (motivo or '')[:80], 'descricao': descricao or ''})
    if created:
        report.full_clean()
        report.save()
    return report, created
