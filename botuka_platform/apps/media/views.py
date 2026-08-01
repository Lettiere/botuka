from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.accounts.permissions import usuario_tem_permissao
from apps.core.domain_views import crud_views
from apps.core.seo.page_builders import listing_seo, media_seo

from .models import (
    Canal,
    CategoriaYuBotuka,
    ConfiguracaoYuBotuka,
    Episodio,
    Pauta,
    Playlist,
    Programa,
    Temporada,
    Transmissao,
    Video,
)
from .selectors import transmissoes_publicas, videos_em_destaque, videos_publicos


def _manager(user):
    return usuario_tem_permissao(user, "media.gerenciar")


def filtrar_fks_media(user, form):
    if "canal" in form.fields:
        form.fields["canal"].queryset = Canal.objects.all()
    if "programa" in form.fields:
        form.fields["programa"].queryset = Programa.objects.filter(canal__ativo=True, canal__excluido_em__isnull=True)
    if "temporada" in form.fields:
        form.fields["temporada"].queryset = Temporada.objects.filter(programa__ativo=True, programa__excluido_em__isnull=True)
    if "episodio" in form.fields:
        form.fields["episodio"].queryset = Episodio.objects.filter(programa__ativo=True, programa__canal__ativo=True)
    if "oficial" in form.fields and not _manager(user):
        form.fields["oficial"].disabled = True


def validar_estado_episodio(user, anterior, novo, obj):
    allowed = {
        None: {Episodio.Status.PAUTA, Episodio.Status.PRODUCAO},
        Episodio.Status.PAUTA: {Episodio.Status.PAUTA, Episodio.Status.PRODUCAO, Episodio.Status.CANCELADO},
        Episodio.Status.PRODUCAO: {Episodio.Status.PRODUCAO, Episodio.Status.GRAVADO, Episodio.Status.CANCELADO},
        Episodio.Status.GRAVADO: {Episodio.Status.GRAVADO, Episodio.Status.EDITANDO, Episodio.Status.CANCELADO},
        Episodio.Status.EDITANDO: {Episodio.Status.EDITANDO, Episodio.Status.AGENDADO, Episodio.Status.PUBLICADO, Episodio.Status.CANCELADO},
        Episodio.Status.AGENDADO: {Episodio.Status.AGENDADO, Episodio.Status.AO_VIVO, Episodio.Status.PUBLICADO, Episodio.Status.CANCELADO},
        Episodio.Status.AO_VIVO: {Episodio.Status.AO_VIVO, Episodio.Status.PUBLICADO, Episodio.Status.CANCELADO},
        Episodio.Status.PUBLICADO: {Episodio.Status.PUBLICADO, Episodio.Status.CANCELADO},
        Episodio.Status.CANCELADO: {Episodio.Status.CANCELADO},
    }
    if novo not in allowed.get(anterior, set()):
        raise PermissionDenied("Transição de episódio inválida.")
    if novo in {Episodio.Status.AGENDADO, Episodio.Status.AO_VIVO, Episodio.Status.PUBLICADO} and not (usuario_tem_permissao(user, "media.publicar") or _manager(user)):
        raise PermissionDenied


def _crud(model, fields, transition=None, permissions=None):
    return crud_views(model, "media", fields, filter_form=filtrar_fks_media, permissions=permissions or {}, validate_transition=transition)


canal_lista, canal_novo, canal_editar = _crud(Canal, ["nome", "descricao", "plataforma", "identificador_externo", "url", "logotipo", "capa", "oficial", "ativo"])
programa_lista, programa_novo, programa_editar = _crud(Programa, ["canal", "nome", "descricao", "categoria", "apresentador", "produtor", "imagem", "frequencia", "duracao_media", "ativo"], permissions={"listar": ("media.apresentar",)})
temporada_lista, temporada_novo, temporada_editar = _crud(Temporada, ["programa", "numero", "titulo", "descricao", "data_inicial", "data_final", "ativo"])
episodio_lista, episodio_novo, episodio_editar = _crud(Episodio, ["programa", "temporada", "titulo", "descricao", "numero", "tipo", "youtube_url", "thumbnail", "duracao", "data_gravacao", "data_programada", "status", "destaque", "ativo"], validar_estado_episodio, {"listar": ("media.apresentar",)})
transmissao_lista, transmissao_novo, transmissao_editar = _crud(Transmissao, ["episodio", "disputa", "acao_publica", "data_prevista", "inicio", "fim", "url_ao_vivo", "status", "ativo"], permissions={"listar": ("media.transmitir",), "criar": ("media.transmitir",), "editar": ("media.transmitir",), "publicar": ("media.transmitir",)})
pauta_lista, pauta_novo, pauta_editar = _crud(Pauta, ["titulo", "descricao", "programa", "convidados", "roteiro", "data_prevista", "status", "observacoes", "ativo"])


def _public_episodes():
    return Episodio.objects.filter(status=Episodio.Status.PUBLICADO, publicado_em__isnull=False, publicado_em__lte=timezone.now(), programa__ativo=True, programa__excluido_em__isnull=True, programa__canal__ativo=True, programa__canal__excluido_em__isnull=True).select_related("programa", "programa__canal")


def _visible_episodes():
    return Episodio.objects.filter(status__in=[Episodio.Status.PUBLICADO, Episodio.Status.AO_VIVO], programa__ativo=True, programa__excluido_em__isnull=True, programa__canal__ativo=True, programa__canal__excluido_em__isnull=True).select_related("programa", "programa__canal")


def home(request):
    return public_home(request)


def public_home(request):
    videos = videos_publicos().order_by("-destaque", "-publicado_em")
    q = request.GET.get("q", "").strip()[:100]
    categoria = request.GET.get("categoria", "").strip()[:80]
    if q:
        videos = videos.filter(
            Q(titulo__icontains=q) | Q(descricao__icontains=q)
            | Q(programa__nome__icontains=q) | Q(canal__nome__icontains=q)
        )
    if categoria:
        videos = videos.filter(categoria__slug=categoria)
    configuracao = ConfiguracaoYuBotuka.objects.first()
    titulo_publico = configuracao.titulo_publico if configuracao else 'YoBotuka'
    if titulo_publico == 'YuBotuka':
        titulo_publico = 'YoBotuka'
    por_pagina = configuracao.quantidade_pagina if configuracao else 12
    page = Paginator(videos, por_pagina).get_page(request.GET.get("page"))
    categorias = CategoriaYuBotuka.objects.filter(
        ativo=True, excluido_em__isnull=True, videos__in=videos_publicos(),
    ).annotate(total_videos=Count('videos', distinct=True)).distinct().order_by('ordem', 'nome')
    playlists = Playlist.objects.filter(
        ativo=True, excluido_em__isnull=True,
        canal__ativo=True, itens__video__in=videos_publicos(),
    ).annotate(total_videos=Count('itens', distinct=True)).distinct().order_by('ordem', 'nome')[:8]
    canais = Canal.objects.filter(
        ativo=True, excluido_em__isnull=True,
        videos_editoriais__in=videos_publicos(),
    ).annotate(total_videos=Count('videos_editoriais', distinct=True)).distinct().order_by('ordem', 'nome')[:8]
    programas = Programa.objects.filter(
        ativo=True, excluido_em__isnull=True,
        videos_editoriais__in=videos_publicos(),
    ).select_related('canal').annotate(total_videos=Count('videos_editoriais', distinct=True)).distinct()[:8]
    shorts = videos_publicos().filter(tipo=Video.Tipo.SHORT).order_by('-publicado_em')[:6]
    recentes_por_categoria = [
        (item, list(videos_publicos().filter(categoria=item).order_by('-publicado_em')[:4]))
        for item in categorias[:4]
    ]
    seo = listing_seo(
        request, 'YoBotuka | Vídeos de Botucatu',
        'Vídeos, programas, entrevistas e transmissões de Botucatu.',
    )
    destaque_editorial = videos_em_destaque('YUBOTUKA').first()
    return render(request, "publico/yubotuka/home.html", {
        "videos": page.object_list, "page_obj": page, "total": page.paginator.count,
        "categorias": categorias, "playlists": playlists, "canais": canais,
        "programas": programas, "shorts": shorts,
        "recentes_por_categoria": recentes_por_categoria,
        "destaque": destaque_editorial or (page.object_list[0] if page.object_list else None),
        "configuracao": configuracao, "titulo_publico": titulo_publico, "seo": seo,
    })


def programa(request, slug):
    return programa_publico(request, slug)


def episodio(request, slug):
    episodio_obj = get_object_or_404(_visible_episodes(), slug=slug)
    if episodio_obj.video_editorial_id:
        video = get_object_or_404(videos_publicos(), pk=episodio_obj.video_editorial_id)
        return _render_video_publico(request, video)
    relacionados = _public_episodes().filter(programa=episodio_obj.programa).exclude(pk=episodio_obj.pk).order_by("-publicado_em")[:4]
    return render(request, "publico/ytv/episodio.html", {"episodio": episodio_obj, "share_object": episodio_obj, "share_type": "episodio", "relacionados": relacionados, "seo": media_seo(request, episodio_obj, kind='episodio')})


def _render_video_publico(request, video):
    relacionados = videos_publicos().filter(
        Q(categoria=video.categoria) | Q(programa=video.programa),
    ).exclude(pk=video.pk).distinct().order_by('-publicado_em')[:6]
    return render(request, 'publico/yubotuka/video.html', {
        'video': video, 'relacionados': relacionados, 'share_object': video, 'share_type': 'video',
        'seo': media_seo(request, video, kind='video'),
    })


def video_publico(request, slug):
    video = get_object_or_404(videos_publicos(), slug=slug)
    return _render_video_publico(request, video)


def categoria_publica(request, slug):
    categoria = get_object_or_404(
        CategoriaYuBotuka.objects.filter(ativo=True, excluido_em__isnull=True),
        slug=slug,
    )
    videos = videos_publicos().filter(
        Q(categoria=categoria) | Q(categoria__categoria_pai=categoria),
    ).order_by('-publicado_em')
    page = Paginator(videos, 12).get_page(request.GET.get('page'))
    return render(request, 'publico/yubotuka/listing.html', {
        'titulo': categoria.nome, 'descricao': f'Vídeos da categoria {categoria.caminho}.',
        'videos': page.object_list, 'page_obj': page,
        'seo': media_seo(request, categoria),
    })


def playlist_publica(request, slug):
    playlist = get_object_or_404(
        Playlist.objects.filter(
            ativo=True, excluido_em__isnull=True, canal__ativo=True,
        ).select_related('canal', 'categoria', 'playlist_pai'),
        slug=slug,
    )
    videos = videos_publicos().filter(
        itens_playlist__playlist=playlist,
    ).order_by('itens_playlist__ordem')
    return render(request, 'publico/yubotuka/listing.html', {
        'titulo': playlist.nome, 'descricao': playlist.descricao,
        'videos': videos, 'playlist': playlist,
        'seo': media_seo(request, playlist),
    })


def canal_publico(request, slug):
    canal = get_object_or_404(
        Canal.objects.filter(ativo=True, excluido_em__isnull=True), slug=slug,
    )
    videos = videos_publicos().filter(canal=canal).order_by('-publicado_em')
    page = Paginator(videos, 12).get_page(request.GET.get('page'))
    return render(request, 'publico/yubotuka/listing.html', {
        'titulo': canal.nome, 'descricao': canal.descricao,
        'videos': page.object_list, 'page_obj': page, 'canal': canal,
        'seo': media_seo(request, canal),
    })


def programa_publico(request, slug):
    programa_obj = get_object_or_404(
        Programa.objects.filter(
            ativo=True, excluido_em__isnull=True,
            canal__ativo=True, canal__excluido_em__isnull=True,
        ).select_related('canal'),
        slug=slug,
    )
    videos = videos_publicos().filter(programa=programa_obj).order_by('-publicado_em')
    page = Paginator(videos, 12).get_page(request.GET.get('page'))
    return render(request, 'publico/yubotuka/listing.html', {
        'titulo': programa_obj.nome, 'descricao': programa_obj.descricao,
        'videos': page.object_list, 'page_obj': page, 'programa': programa_obj,
        'seo': media_seo(request, programa_obj),
    })


def temporada_publica(request, programa_slug, numero):
    temporada = get_object_or_404(
        Temporada.objects.filter(
            ativo=True, excluido_em__isnull=True,
            programa__slug=programa_slug, programa__ativo=True,
            programa__canal__ativo=True,
        ).select_related('programa', 'programa__canal'),
        numero=numero,
    )
    videos = videos_publicos().filter(temporada=temporada).order_by('numero_episodio', 'publicado_em')
    return render(request, 'publico/yubotuka/listing.html', {
        'titulo': temporada.titulo or f'Temporada {temporada.numero}',
        'descricao': temporada.descricao,
        'videos': videos, 'temporada': temporada,
        'seo': media_seo(request, temporada),
    })


def transmissoes_publicas_lista(request):
    agora = timezone.now()
    transmissoes = transmissoes_publicas()
    return render(request, 'publico/yubotuka/transmissions.html', {
        'ao_vivo': transmissoes.filter(
            status=Transmissao.Status.AO_VIVO,
            inicio__lte=agora,
        ).filter(Q(fim__isnull=True) | Q(fim__gt=agora)),
        'proximas': transmissoes.filter(
            status=Transmissao.Status.AGENDADA, data_prevista__gte=agora,
        ).order_by('data_prevista'),
        'encerradas': transmissoes.filter(
            status__in=[Transmissao.Status.ENCERRADA, Transmissao.Status.PUBLICADA],
        ).order_by('-fim', '-atualizado_em')[:20],
        'seo': listing_seo(
            request, 'Transmissões | YoBotuka',
            'Lives, próximas transmissões e gravações de Botucatu.',
        ),
    })


def transmissao_ao_vivo_publica(request):
    agora = timezone.now()
    transmissao = transmissoes_publicas().filter(
        status=Transmissao.Status.AO_VIVO, inicio__lte=agora,
    ).filter(Q(fim__isnull=True) | Q(fim__gt=agora)).order_by('-inicio').first()
    proximas = transmissoes_publicas().filter(
        status=Transmissao.Status.AGENDADA, data_prevista__gte=agora,
    ).order_by('data_prevista')[:6]
    return render(request, 'publico/yubotuka/live.html', {
        'transmissao': transmissao, 'proximas': proximas,
        'seo': listing_seo(request, 'Ao vivo | YoBotuka', 'Acompanhe transmissões ao vivo de Botucatu.'),
    })


def transmissao_publica(request, slug):
    transmissao = get_object_or_404(transmissoes_publicas(), slug=slug)
    return render(request, 'publico/yubotuka/transmission.html', {
        'transmissao': transmissao,
        'seo': media_seo(request, transmissao, kind='video'),
    })


def ao_vivo(request):
    transmissions = Transmissao.objects.filter(ativo=True, excluido_em__isnull=True, status=Transmissao.Status.AO_VIVO, episodio__ativo=True, episodio__excluido_em__isnull=True, episodio__status=Episodio.Status.AO_VIVO, episodio__video_id__gt="", episodio__programa__ativo=True, episodio__programa__excluido_em__isnull=True, episodio__programa__canal__ativo=True, episodio__programa__canal__excluido_em__isnull=True).select_related("episodio", "episodio__programa").order_by("-inicio")
    recentes = _public_episodes().order_by("-publicado_em")[:4]
    seo = listing_seo(request, 'YoBotuka ao vivo', 'Transmissões e conteúdos audiovisuais locais da YoBotuka.')
    return render(request, "publico/ytv/ao_vivo.html", {"transmissoes": transmissions, "recentes": recentes, "seo": seo})
