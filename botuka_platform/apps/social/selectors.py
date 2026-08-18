from django.db import models
from django.db.models import Count, Q
from django.utils import timezone

from apps.organizations.models import Empresa

from .models import (
    EmpresaSeguidor, SocialBlock, SocialConversation, SocialConversationRequest,
    SocialFollow, SocialFollowRequest, SocialPost, SocialPostComment, SocialPostSave, SocialProfile, SocialStory,
)


def seguidores_do_perfil(profile):
    return SocialProfile.objects.filter(seguindo_relacoes__seguido=profile, ativo=True).select_related('usuario').annotate(total_seguidores=Count('seguidores_relacoes')).order_by('-seguindo_relacoes__criado_em')


def perfis_seguidos_por(profile):
    return SocialProfile.objects.filter(seguidores_relacoes__seguidor=profile, ativo=True).select_related('usuario').annotate(total_seguidores=Count('seguidores_relacoes')).order_by('-seguidores_relacoes__criado_em')


def empresas_seguidas_por(usuario):
    return Empresa.objects.filter(seguidores_sociais__usuario=usuario).annotate(total_seguidores=Count('seguidores_sociais')).order_by('-seguidores_sociais__criado_em')


def seguidores_da_empresa(empresa):
    return EmpresaSeguidor.objects.filter(empresa=empresa).select_related('usuario').order_by('-criado_em')


def contagem_seguidores_perfil(profile):
    return SocialFollow.objects.filter(seguido=profile).count()


def contagem_seguidores_empresa(empresa):
    return EmpresaSeguidor.objects.filter(empresa=empresa).count()


def perfis_sugeridos_para(usuario=None, limite=8):
    queryset = SocialProfile.objects.filter(
        ativo=True, usuario__is_active=True,
    ).exclude(visibilidade=SocialProfile.Visibilidade.PRIVADO)
    if usuario and usuario.is_authenticated:
        queryset = queryset.exclude(usuario=usuario).exclude(
            seguidores_relacoes__seguidor__usuario=usuario,
        )
    return queryset.select_related('usuario', 'usuario__cidade', 'usuario__estado').annotate(
        total_seguidores=Count('seguidores_relacoes'),
    ).order_by('-atualizado_em', 'id')[:limite]


def empresas_sugeridas_para(usuario=None, limite=8):
    queryset = Empresa.objects.filter(
        ativo=True, perfil_publico=True, status=Empresa.Status.ATIVA,
        excluido_em__isnull=True,
    )
    if usuario and usuario.is_authenticated:
        queryset = queryset.exclude(seguidores_sociais__usuario=usuario)
    return queryset.select_related('categoria_empresa', 'cidade', 'estado').annotate(
        total_seguidores=Count('seguidores_sociais'),
    ).order_by('-atualizado_em', 'id')[:limite]


def conteudo_publico_para_descoberta(limite_por_tipo=2):
    from apps.core.search.registry import default_registry

    selected = {'eventos', 'noticias', 'servicos', 'turismo', 'vagas'}
    items = []
    path_builders = {
        'eventos': lambda obj: f'/eventos/{obj.slug}/',
        'noticias': lambda obj: f'/noticias/{obj.slug}/',
        'servicos': lambda obj: f'/servicos/{obj.slug}/',
        'turismo': lambda obj: f'/turismo/locais/{obj.slug}/',
        'vagas': lambda obj: f'/vagas/{obj.slug}/',
    }
    for spec in default_registry():
        if spec.key not in selected:
            continue
        for obj in spec.queryset()[:limite_por_tipo]:
            summary = next((getattr(obj, field, '') for field in spec.summary_fields if '__' not in field and getattr(obj, field, '')), '')
            data = {
                'title': getattr(obj, spec.title_field, str(obj)),
                'summary': summary,
                'description': summary,
                'category': '', 'owner': '', 'location': '', 'image': '', 'extra': '',
                'url': path_builders[spec.key](obj),
            }
            items.append({'kind': spec.key, 'label': spec.label, **data})
    return items


def posts_visiveis_para(usuario, *, incluir_fora_feed=False):
    queryset = SocialPost.objects.filter(ativo=True).select_related(
        'autor', 'autor__usuario', 'conteudo_tipo',
    ).prefetch_related('curtidas', 'comentarios', 'salvamentos')
    viewer = None
    if usuario and usuario.is_authenticated:
        from .services import get_or_create_social_profile
        viewer = get_or_create_social_profile(usuario)
        blocked = SocialBlock.objects.filter(Q(bloqueador=viewer) | Q(bloqueado=viewer)).values_list(
            'bloqueado_id', 'bloqueador_id',
        )
        blocked_ids = {value for pair in blocked for value in pair if value != viewer.pk}
        followed = SocialFollow.objects.filter(seguidor=viewer).values_list('seguido_id', flat=True)
        queryset = queryset.exclude(autor_id__in=blocked_ids).filter(
            Q(autor=viewer) |
            (Q(autor__visibilidade=SocialProfile.Visibilidade.PUBLICO) & Q(visibilidade=SocialPost.Visibilidade.PUBLICO)) |
            (Q(autor_id__in=followed) & ~Q(visibilidade=SocialPost.Visibilidade.SOMENTE_EU))
        )
    else:
        queryset = queryset.filter(
            autor__visibilidade=SocialProfile.Visibilidade.PUBLICO,
            visibilidade=SocialPost.Visibilidade.PUBLICO,
        )
    if not incluir_fora_feed:
        queryset = queryset.filter(feed_ate__gt=timezone.now())
    return queryset.order_by('-publicado_em').distinct()


def feed_para(usuario, limite=30):
    queryset = posts_visiveis_para(usuario)
    if usuario and usuario.is_authenticated:
        profile = usuario.social_profile
        followed = SocialFollow.objects.filter(seguidor=profile).values_list('seguido_id', flat=True)
        queryset = queryset.annotate(prioridade=models.Case(
            models.When(autor_id__in=followed, then=models.Value(0)),
            default=models.Value(1), output_field=models.IntegerField(),
        )).order_by('prioridade', '-publicado_em')
    return queryset[:limite]


def posts_do_perfil(profile, usuario=None):
    return posts_visiveis_para(usuario, incluir_fora_feed=True).filter(autor=profile)


def stories_ativos_para(usuario):
    queryset = SocialStory.objects.filter(ativo=True, expira_em__gt=timezone.now()).select_related('autor', 'autor__usuario')
    if usuario and usuario.is_authenticated:
        from .services import get_or_create_social_profile
        viewer = get_or_create_social_profile(usuario)
        followed = SocialFollow.objects.filter(seguidor=viewer).values_list('seguido_id', flat=True)
        blocked = SocialBlock.objects.filter(Q(bloqueador=viewer) | Q(bloqueado=viewer))
        blocked_ids = set(blocked.values_list('bloqueador_id', flat=True)) | set(blocked.values_list('bloqueado_id', flat=True))
        blocked_ids.discard(viewer.pk)
        return queryset.exclude(autor_id__in=blocked_ids).filter(
            Q(autor=viewer) | Q(autor_id__in=followed, visibilidade__in=['PUBLICO', 'SEGUIDORES']) |
            Q(autor__visibilidade='PUBLICO', visibilidade='PUBLICO')
        ).distinct()
    return queryset.filter(autor__visibilidade='PUBLICO', visibilidade='PUBLICO')


def story_visivel_para(usuario, uuid):
    return stories_ativos_para(usuario).filter(uuid=uuid).first()


def conversas_para(usuario):
    return SocialConversation.objects.filter(ativo=True, participantes=usuario).prefetch_related(
        'participantes__social_profile', 'mensagens__remetente',
    ).distinct()


def solicitacoes_conversa_para(usuario):
    return SocialConversationRequest.objects.filter(
        destinatario=usuario, status=SocialConversationRequest.Status.PENDENTE,
    ).select_related('solicitante__social_profile', 'post', 'story')


def solicitacoes_pendentes_para(usuario):
    return SocialFollowRequest.objects.filter(destinatario__usuario=usuario, status='PENDENTE').select_related('solicitante', 'solicitante__usuario')


def comentarios_do_post(post):
    return SocialPostComment.objects.filter(post=post, ativo=True).select_related('autor', 'autor__usuario')


def posts_salvos_por(usuario):
    return SocialPost.objects.filter(salvamentos__usuario=usuario, ativo=True).select_related('autor', 'autor__usuario').order_by('-salvamentos__criado_em')
