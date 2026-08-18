import hashlib
import uuid

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.analytics.services import register_event
from apps.core.seo.context import _consent

from .models import (
    EmpresaSeguidor, SocialBlock, SocialConversation, SocialConversationParticipant,
    SocialConversationRequest, SocialFollow, SocialFollowRequest, SocialMessage, SocialPost, SocialPostComment, SocialPostLike,
    SocialPostSave, SocialProfile, SocialStory,
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
        return request, created
    return SocialFollow.objects.get_or_create(seguidor=seguidor, seguido=seguido)


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
def curtir_post(usuario, post):
    _authenticated(usuario)
    if not pode_ver_post(usuario, post):
        raise PermissionDenied
    return SocialPostLike.objects.get_or_create(usuario=usuario, post=post)


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


@transaction.atomic
def enviar_mensagem(usuario, conversa, *, texto='', post=None, story=None):
    _authenticated(usuario)
    if not conversa.ativo or not conversa.participantes.filter(pk=usuario.pk).exists():
        raise PermissionDenied('Conversa indisponível.')
    message = SocialMessage(conversa=conversa, remetente=usuario, texto=(texto or '').strip(), post=post, story=story)
    message.full_clean()
    message.save()
    return message


def _conversation_between(a, b):
    return SocialConversation.objects.filter(ativo=True, participantes=a).filter(participantes=b).distinct().first()


@transaction.atomic
def solicitar_ou_enviar_conversa(usuario, destinatario, *, texto='', post=None, story=None):
    _authenticated(usuario)
    if usuario.pk == destinatario.pk:
        raise ValidationError('Escolha outra pessoa.')
    origem = get_or_create_social_profile(usuario)
    destino = get_or_create_social_profile(destinatario)
    if _blocked(origem, destino):
        raise PermissionDenied('Esta interação não está disponível.')
    conversa = _conversation_between(usuario, destinatario)
    if conversa:
        return enviar_mensagem(usuario, conversa, texto=texto, post=post, story=story), False
    if SocialConversationRequest.objects.filter(solicitante=usuario, destinatario=destinatario, status=SocialConversationRequest.Status.RECUSADA).exists():
        raise PermissionDenied('Uma solicitação anterior foi recusada.')
    pedido, created = SocialConversationRequest.objects.get_or_create(
        solicitante=usuario, destinatario=destinatario,
        status=SocialConversationRequest.Status.PENDENTE,
        defaults={'mensagem_inicial': (texto or '').strip(), 'post': post, 'story': story},
    )
    if not created:
        raise ValidationError('Já existe uma solicitação pendente.')
    pedido.full_clean()
    pedido.save()
    return pedido, True


@transaction.atomic
def decidir_solicitacao_conversa(usuario, pedido, aceitar):
    _authenticated(usuario)
    pedido = SocialConversationRequest.objects.select_for_update().get(pk=pedido.pk)
    if pedido.destinatario_id != usuario.pk or pedido.status != SocialConversationRequest.Status.PENDENTE:
        raise PermissionDenied
    pedido.decidido_em = timezone.now()
    if not aceitar:
        pedido.status = SocialConversationRequest.Status.RECUSADA
        pedido.save(update_fields=['status', 'decidido_em', 'atualizado_em'])
        return pedido
    if _blocked(get_or_create_social_profile(pedido.solicitante), get_or_create_social_profile(usuario)):
        raise PermissionDenied
    conversa = _conversation_between(pedido.solicitante, usuario) or SocialConversation.objects.create()
    SocialConversationParticipant.objects.bulk_create([
        SocialConversationParticipant(conversa=conversa, usuario=pedido.solicitante),
        SocialConversationParticipant(conversa=conversa, usuario=usuario),
    ], ignore_conflicts=True)
    pedido.status = SocialConversationRequest.Status.ACEITA
    pedido.conversa = conversa
    pedido.save(update_fields=['status', 'conversa', 'decidido_em', 'atualizado_em'])
    enviar_mensagem(pedido.solicitante, conversa, texto=pedido.mensagem_inicial, post=pedido.post, story=pedido.story)
    return pedido
