from django.db.models import Q

from django.utils import timezone

from .models import Canal, CategoriaYuBotuka, DestaqueEditorial, Playlist, Programa, Transmissao, Video
from .permissions import pode_moderar, possui


def videos_visiveis_no_painel(user):
    queryset = Video.objects.select_related(
        'autor', 'canal', 'programa', 'categoria', 'motivo_rejeicao',
    ).filter(excluido_em__isnull=True)
    if possui(user, 'yubotuka.video.editar_todos') or pode_moderar(user):
        return queryset
    if possui(user, 'yubotuka.video.editar_proprio'):
        return queryset.filter(autor=user)
    return queryset.none()


def videos_para_moderacao(user):
    if not pode_moderar(user):
        return Video.objects.none()
    return Video.objects.filter(
        status=Video.Status.EM_ANALISE, ativo=True, excluido_em__isnull=True,
    ).select_related('autor', 'canal', 'programa', 'categoria')


def filtrar_videos(queryset, termo='', status=''):
    if termo:
        queryset = queryset.filter(
            Q(titulo__icontains=termo)
            | Q(descricao_curta__icontains=termo)
            | Q(canal__nome__icontains=termo)
        )
    if status in Video.Status.values:
        queryset = queryset.filter(status=status)
    return queryset


def categorias_ativas():
    return CategoriaYuBotuka.objects.filter(
        ativo=True, excluido_em__isnull=True,
    ).select_related('categoria_pai')


def playlists_visiveis(user):
    queryset = Playlist.objects.filter(
        ativo=True, excluido_em__isnull=True,
    ).select_related('canal', 'categoria', 'playlist_pai', 'proprietario')
    if possui(user, 'yubotuka.playlist.gerenciar'):
        return queryset
    return queryset.filter(proprietario=user)


def canais_permitidos(user):
    queryset = Canal.objects.filter(ativo=True, excluido_em__isnull=True)
    if possui(user, 'yubotuka.canal.gerenciar'):
        return queryset
    return queryset.filter(
        Q(proprietario=user)
        | Q(
            usuarios_autorizados__usuario=user,
            usuarios_autorizados__ativo=True,
            usuarios_autorizados__revogado_em__isnull=True,
        ),
    ).distinct()


def programas_permitidos(user, somente_ativos=True):
    queryset = Programa.all_objects.filter(
        excluido_em__isnull=True, canal__in=canais_permitidos(user),
    ).select_related('canal', 'categoria_editorial')
    return queryset.filter(ativo=True) if somente_ativos else queryset


def transmissoes_visiveis_painel(user):
    queryset = Transmissao.objects.filter(
        excluido_em__isnull=True,
    ).select_related('canal', 'programa', 'categoria', 'autor', 'video_resultante')
    if any(
        possui(user, permissao, aceitar_legado=False)
        for permissao in (
            'yubotuka.transmissao.editar_todas',
            'yubotuka.transmissao.aprovar',
            'yubotuka.transmissao.publicar',
            'yubotuka.transmissao.cancelar',
        )
    ):
        return queryset
    if possui(user, 'yubotuka.transmissao.editar_propria'):
        return queryset.filter(autor=user)
    return queryset.none()


def transmissoes_publicas():
    agora = timezone.now()
    return Transmissao.objects.filter(
        ativo=True,
        excluido_em__isnull=True,
        canal__ativo=True,
        canal__excluido_em__isnull=True,
        status__in=[
            Transmissao.Status.AGENDADA,
            Transmissao.Status.AO_VIVO,
            Transmissao.Status.ENCERRADA,
            Transmissao.Status.PUBLICADA,
        ],
    ).filter(
        Q(status=Transmissao.Status.AO_VIVO, inicio__lte=agora, fim__isnull=True)
        | Q(status=Transmissao.Status.AO_VIVO, inicio__lte=agora, fim__gt=agora)
        | Q(status=Transmissao.Status.AGENDADA, data_prevista__gte=agora)
        | Q(status__in=[Transmissao.Status.ENCERRADA, Transmissao.Status.PUBLICADA])
    ).select_related('canal', 'programa', 'categoria', 'video_resultante')


def videos_publicos():
    return Video.objects.filter(
        status=Video.Status.PUBLICADO,
        ativo=True,
        publico=True,
        excluido_em__isnull=True,
        publicado_em__isnull=False,
        publicado_em__lte=timezone.now(),
        canal__ativo=True,
        canal__excluido_em__isnull=True,
    ).filter(
        Q(categoria__isnull=True)
        | Q(
            categoria__ativo=True,
            categoria__excluido_em__isnull=True,
            categoria__categoria_pai__isnull=True,
        )
        | Q(
            categoria__ativo=True,
            categoria__excluido_em__isnull=True,
            categoria__categoria_pai__ativo=True,
            categoria__categoria_pai__excluido_em__isnull=True,
        ),
    ).filter(
        Q(programa__isnull=True)
        | Q(programa__ativo=True, programa__excluido_em__isnull=True),
    ).filter(
        Q(temporada__isnull=True)
        | Q(temporada__ativo=True, temporada__excluido_em__isnull=True),
    ).select_related(
        'canal', 'categoria', 'programa', 'temporada', 'autor',
    ).prefetch_related(
        'itens_playlist__playlist',
        'videos_tags__tag',
    )


def videos_em_destaque(posicao, **escopo):
    agora = timezone.now()
    filtros = {
        'posicoes_destaque__posicao': posicao,
        'posicoes_destaque__ativo': True,
    }
    for campo, valor in escopo.items():
        filtros[f'posicoes_destaque__{campo}'] = valor
    return videos_publicos().filter(
        **filtros,
    ).filter(
        Q(posicoes_destaque__inicio__isnull=True)
        | Q(posicoes_destaque__inicio__lte=agora),
    ).filter(
        Q(posicoes_destaque__fim__isnull=True)
        | Q(posicoes_destaque__fim__gt=agora),
    ).order_by('posicoes_destaque__ordem', '-publicado_em').distinct()
