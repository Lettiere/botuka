from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.core.domain import auditar

from .forms import (
    AgendamentoForm,
    ApresentadorForm,
    ArquivamentoForm,
    BannerForm,
    CanalForm,
    CategoriaForm,
    ConfiguracaoForm,
    ConvidadoForm,
    DestaqueEditorialForm,
    MotivoRejeicaoForm,
    PatrocinadorForm,
    PlaylistForm,
    RejeicaoForm,
    TagForm,
    VideoForm,
)
from .models import (
    Apresentador,
    BannerYuBotuka,
    Canal,
    CategoriaYuBotuka,
    ConfiguracaoYuBotuka,
    Convidado,
    DestaqueEditorial,
    HistoricoEditorial,
    MotivoRejeicao,
    Patrocinador,
    Playlist,
    PlaylistVideo,
    TagYuBotuka,
    Video,
)
from .permissions import exigir, pode_editar_video, pode_moderar, pode_publicar, possui
from .selectors import (
    categorias_ativas,
    canais_permitidos,
    filtrar_videos,
    playlists_visiveis,
    videos_para_moderacao,
    videos_visiveis_no_painel,
)
from .services import (
    agendar_video,
    aprovar_video,
    arquivar_video,
    devolver_para_correcao,
    enviar_para_analise,
    publicar_video,
    reordenar_playlist,
    rejeitar_video,
    restaurar_video,
)


def _contexto_base(request):
    return {
        'pode_moderar': pode_moderar(request.user),
        'pode_publicar': pode_publicar(request.user),
        'pode_criar_video': possui(request.user, 'yubotuka.video.criar'),
        'pode_gerenciar_categoria': possui(request.user, 'yubotuka.categoria.gerenciar'),
        'pode_gerenciar_playlist': possui(request.user, 'yubotuka.playlist.gerenciar'),
        'pode_gerenciar_canal': possui(request.user, 'yubotuka.canal.gerenciar'),
        'pode_arquivar': possui(request.user, 'yubotuka.video.arquivar', aceitar_legado=False),
        'pode_ver_auditoria': possui(request.user, 'yubotuka.auditoria.visualizar', aceitar_legado=False),
        'auxiliares_menu': [
            {'tipo': tipo, 'titulo': titulo}
            for tipo, (_, _, permissao, titulo) in AUXILIARES.items()
            if possui(request.user, permissao, aceitar_legado=False)
        ] if 'AUXILIARES' in globals() else [],
        'pode_configurar': possui(request.user, 'yubotuka.config.gerenciar', aceitar_legado=False),
        'pode_gerenciar_programa': possui(request.user, 'yubotuka.programa.gerenciar'),
        'pode_gerenciar_temporada': possui(request.user, 'yubotuka.temporada.gerenciar'),
        'pode_gerenciar_episodio': possui(request.user, 'yubotuka.episodio.gerenciar'),
        'pode_ver_transmissao': possui(request.user, 'yubotuka.transmissao.criar') or possui(request.user, 'yubotuka.transmissao.editar_todas'),
        'pode_atribuir_canal': possui(request.user, 'yubotuka.canal.atribuir', aceitar_legado=False),
        'pode_homologar_legado': possui(request.user, 'yubotuka.legado.homologar', aceitar_legado=False),
    }


@login_required
def dashboard(request):
    exigir(request.user, 'yubotuka.dashboard.visualizar')
    videos = videos_visiveis_no_painel(request.user)
    canal = request.GET.get('canal', '')
    categoria = request.GET.get('categoria', '')
    status = request.GET.get('status', '')
    autor = request.GET.get('autor', '')
    periodo = request.GET.get('periodo', '')
    if canal:
        videos = videos.filter(canal__uuid=canal)
    if categoria:
        videos = videos.filter(categoria__uuid=categoria)
    if status in Video.Status.values:
        videos = videos.filter(status=status)
    if autor:
        videos = videos.filter(autor__uuid=autor)
    if periodo.isdigit():
        videos = videos.filter(criado_em__gte=timezone.now() - timezone.timedelta(days=int(periodo)))
    contagens = {
        item['status']: item['total']
        for item in videos.values('status').annotate(total=Count('id'))
    }
    pendentes = videos_para_moderacao(request.user).order_by('atualizado_em')[:8]
    incompletos = videos.filter(
        Q(youtube_url='') | Q(video_id='') | Q(categoria__isnull=True),
    ).exclude(status=Video.Status.PUBLICADO).order_by('-atualizado_em')[:8]
    contexto = {
        **_contexto_base(request),
        'contagens': contagens,
        'status': Video.Status,
        'pendentes': pendentes,
        'incompletos': incompletos,
        'total_videos': videos.count(),
        'total_categorias': categorias_ativas().count(),
        'total_playlists': playlists_visiveis(request.user).count(),
        'total_canais': canais_permitidos(request.user).count(),
        'ultimos': videos.order_by('-criado_em')[:6],
        'rejeitados': videos.filter(status=Video.Status.REJEITADO).order_by('-atualizado_em')[:6],
        'agendados': videos.filter(status=Video.Status.AGENDADO).order_by('data_agendamento')[:6],
        'publicados_recentes': videos.filter(status=Video.Status.PUBLICADO).order_by('-publicado_em')[:6],
        'canais_filtro': canais_permitidos(request.user),
        'categorias_filtro': categorias_ativas(),
        'autores_filtro': videos.exclude(autor=None).values('autor__uuid', 'autor__username').distinct(),
        'filtros': request.GET,
    }
    return render(request, 'painel/yubotuka/dashboard.html', contexto)


@login_required
def video_lista(request):
    exigir(request.user, 'yubotuka.dashboard.visualizar')
    termo = request.GET.get('q', '').strip()[:100]
    status = request.GET.get('status', '').strip()
    videos = filtrar_videos(videos_visiveis_no_painel(request.user), termo, status)
    return render(request, 'painel/yubotuka/video_list.html', {
        **_contexto_base(request), 'videos': videos,
        'status_choices': Video.Status.choices, 'termo': termo, 'status_atual': status,
    })


@login_required
def video_novo(request):
    exigir(request.user, 'yubotuka.video.criar')
    form = VideoForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            video = form.save(commit=False)
            video.autor = request.user
            video.status = Video.Status.RASCUNHO
            video.save()
            form.save_playlists(video)
            HistoricoEditorial.objects.create(
                video=video, usuario=request.user,
                acao=HistoricoEditorial.Acao.CRIADO,
                status_novo=video.status,
                ip=request.META.get('REMOTE_ADDR'),
            )
            auditar(request, 'CRIADO', video, depois={'status': video.status})
        messages.success(request, 'Vídeo salvo como rascunho.')
        return redirect('painel:yubotuka_video_editar', uuid=video.uuid)
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form, 'titulo': 'Novo vídeo',
        'subtitulo': 'O slug será gerado automaticamente a partir do título.',
        'cancelar_url': 'painel:yubotuka_videos',
    })


@login_required
def video_editar(request, uuid):
    video = get_object_or_404(videos_visiveis_no_painel(request.user), uuid=uuid)
    if not pode_editar_video(request.user, video):
        raise PermissionDenied('Você não pode editar este vídeo.')
    if request.method == 'POST' and video.status == Video.Status.REJEITADO:
        video = devolver_para_correcao(video, request.user, request)
    form = VideoForm(request.POST or None, instance=video, user=request.user)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            video = form.save()
            form.save_playlists(video)
            HistoricoEditorial.objects.create(
                video=video, usuario=request.user,
                acao=HistoricoEditorial.Acao.EDITADO,
                status_anterior=video.status, status_novo=video.status,
                ip=request.META.get('REMOTE_ADDR'),
            )
            auditar(request, 'EDITADO', video, depois={'status': video.status})
        messages.success(request, 'Vídeo atualizado.')
        return redirect('painel:yubotuka_video_editar', uuid=video.uuid)
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form, 'video': video,
        'titulo': 'Editar vídeo', 'subtitulo': f'Status atual: {video.get_status_display()}',
        'cancelar_url': 'painel:yubotuka_videos',
    })


@login_required
def video_detalhe(request, uuid):
    video = get_object_or_404(videos_visiveis_no_painel(request.user), uuid=uuid)
    historico = video.historico_editorial.select_related('usuario').all()
    return render(request, 'painel/yubotuka/video_detail.html', {
        **_contexto_base(request), 'video': video, 'historico': historico,
        'pode_editar': pode_editar_video(request.user, video),
        'agendamento_form': AgendamentoForm(),
    })


def _acao_post(request, uuid, servico, sucesso, *args):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    video = get_object_or_404(Video, uuid=uuid, excluido_em__isnull=True)
    try:
        servico(video, request.user, *args, request=request)
    except (ValidationError, PermissionDenied) as exc:
        if isinstance(exc, PermissionDenied):
            raise
        messages.error(request, '; '.join(exc.messages))
    else:
        messages.success(request, sucesso)
    return redirect(request.POST.get('next') or 'painel:yubotuka_videos')


@login_required
def video_enviar_analise(request, uuid):
    return _acao_post(request, uuid, enviar_para_analise, 'Vídeo enviado para análise.')


@login_required
def video_aprovar(request, uuid):
    return _acao_post(request, uuid, aprovar_video, 'Vídeo aprovado.')


@login_required
def video_publicar(request, uuid):
    return _acao_post(request, uuid, publicar_video, 'Vídeo publicado.')


@login_required
def video_agendar(request, uuid):
    data = parse_datetime(request.POST.get('data_agendamento', '')) if request.method == 'POST' else None
    return _acao_post(request, uuid, agendar_video, 'Vídeo agendado.', data)


@login_required
def video_arquivar(request, uuid):
    video = get_object_or_404(videos_visiveis_no_painel(request.user), uuid=uuid)
    form = ArquivamentoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        arquivar_video(video, request.user, form.cleaned_data['motivo'], request)
        messages.success(request, 'Vídeo arquivado sem exclusão física.')
        return redirect('painel:yubotuka_video_detalhe', uuid=video.uuid)
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form,
        'titulo': f'Arquivar: {video.titulo}',
        'subtitulo': 'O conteúdo deixará de ser público, mas seus dados serão preservados.',
        'cancelar_url': 'painel:yubotuka_video_detalhe', 'cancelar_uuid': video.uuid,
    })


@login_required
def video_restaurar(request, uuid):
    return _acao_post(request, uuid, restaurar_video, 'Vídeo restaurado.')


@login_required
def fila_aprovacao(request):
    if not pode_moderar(request.user):
        raise PermissionDenied('Você não possui acesso à fila de aprovação.')
    videos = videos_para_moderacao(request.user)
    termo = request.GET.get('q', '').strip()[:100]
    canal = request.GET.get('canal', '')
    categoria = request.GET.get('categoria', '')
    if termo:
        videos = videos.filter(Q(titulo__icontains=termo) | Q(autor__username__icontains=termo))
    if canal:
        videos = videos.filter(canal__uuid=canal)
    if categoria:
        videos = videos.filter(categoria__uuid=categoria)
    return render(request, 'painel/yubotuka/fila.html', {
        **_contexto_base(request),
        'videos': videos.annotate(total_rejeicoes=Count(
            'historico_editorial',
            filter=Q(historico_editorial__acao=HistoricoEditorial.Acao.REJEITADO),
        )).order_by('atualizado_em'),
        'canais': canais_permitidos(request.user),
        'categorias': categorias_ativas(),
    })


@login_required
def revisao_detalhe(request, uuid):
    if not pode_moderar(request.user):
        raise PermissionDenied('Você não possui acesso à revisão.')
    video = get_object_or_404(
        videos_para_moderacao(request.user), uuid=uuid,
    )
    return render(request, 'painel/yubotuka/review_detail.html', {
        **_contexto_base(request), 'video': video,
        'historico': video.historico_editorial.select_related('usuario'),
    })


@login_required
def video_rejeitar(request, uuid):
    if not pode_moderar(request.user):
        raise PermissionDenied('Você não pode rejeitar vídeos.')
    video = get_object_or_404(Video, uuid=uuid, status=Video.Status.EM_ANALISE)
    form = RejeicaoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        rejeitar_video(
            video, request.user, form.cleaned_data['motivo_rejeicao'],
            form.cleaned_data['observacao'], request,
        )
        messages.success(request, 'Vídeo rejeitado e devolvido ao autor.')
        return redirect('painel:yubotuka_fila')
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form,
        'titulo': f'Rejeitar: {video.titulo}',
        'subtitulo': 'Informe claramente o motivo e os ajustes necessários.',
        'cancelar_url': 'painel:yubotuka_fila',
    })


@login_required
def categoria_lista(request):
    exigir(request.user, 'yubotuka.categoria.gerenciar')
    return render(request, 'painel/yubotuka/category_list.html', {
        **_contexto_base(request), 'categorias': categorias_ativas(),
    })


@login_required
def categoria_form(request, uuid=None):
    exigir(request.user, 'yubotuka.categoria.gerenciar')
    categoria = get_object_or_404(CategoriaYuBotuka, uuid=uuid) if uuid else None
    form = CategoriaForm(request.POST or None, instance=categoria)
    if request.method == 'POST' and form.is_valid():
        categoria = form.save()
        auditar(request, 'EDITADO' if uuid else 'CRIADO', categoria)
        messages.success(request, 'Categoria salva.')
        return redirect('painel:yubotuka_categorias')
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form,
        'titulo': 'Editar categoria' if uuid else 'Nova categoria',
        'subtitulo': 'Use uma categoria pai para criar subcategorias.',
        'cancelar_url': 'painel:yubotuka_categorias',
    })


@login_required
def categoria_detalhe(request, uuid):
    exigir(request.user, 'yubotuka.categoria.gerenciar')
    categoria = get_object_or_404(CategoriaYuBotuka, uuid=uuid)
    return render(request, 'painel/yubotuka/category_detail.html', {
        **_contexto_base(request), 'categoria': categoria,
        'subcategorias': categoria.subcategorias.filter(excluido_em__isnull=True),
        'videos': categoria.videos.filter(excluido_em__isnull=True).select_related('canal'),
        'playlists': categoria.playlists.filter(excluido_em__isnull=True).select_related('canal'),
    })


@login_required
def categoria_alternar(request, uuid):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    exigir(request.user, 'yubotuka.categoria.gerenciar')
    categoria = get_object_or_404(CategoriaYuBotuka, uuid=uuid)
    categoria.ativo = not categoria.ativo
    categoria.save(update_fields=['ativo', 'atualizado_em'])
    auditar(request, 'ATIVADO' if categoria.ativo else 'DESATIVADO', categoria)
    messages.success(request, 'Status da categoria atualizado.')
    return redirect('painel:yubotuka_categoria_detalhe', uuid=categoria.uuid)


@login_required
def playlist_lista(request):
    exigir(request.user, 'yubotuka.playlist.gerenciar')
    return render(request, 'painel/yubotuka/playlist_list.html', {
        **_contexto_base(request), 'playlists': playlists_visiveis(request.user),
    })


@login_required
def playlist_form(request, uuid=None):
    exigir(request.user, 'yubotuka.playlist.gerenciar')
    playlist = get_object_or_404(playlists_visiveis(request.user), uuid=uuid) if uuid else None
    form = PlaylistForm(request.POST or None, instance=playlist, user=request.user)
    if request.method == 'POST' and form.is_valid():
        playlist = form.save(commit=False)
        if not playlist.pk:
            playlist.proprietario = request.user
        playlist.save()
        auditar(request, 'EDITADO' if uuid else 'CRIADO', playlist)
        messages.success(request, 'Playlist salva.')
        return redirect('painel:yubotuka_playlists')
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form,
        'titulo': 'Editar playlist' if uuid else 'Nova playlist',
        'subtitulo': 'Use uma playlist pai para organizar níveis como Esporte › Vôlei › Amador.',
        'cancelar_url': 'painel:yubotuka_playlists',
    })


@login_required
def playlist_detalhe(request, uuid):
    exigir(request.user, 'yubotuka.playlist.gerenciar')
    playlist = get_object_or_404(playlists_visiveis(request.user), uuid=uuid)
    return render(request, 'painel/yubotuka/playlist_detail.html', {
        **_contexto_base(request), 'playlist': playlist,
        'itens': playlist.itens.select_related('video').order_by('ordem'),
    })


@login_required
def playlist_reordenar(request, uuid):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    playlist = get_object_or_404(playlists_visiveis(request.user), uuid=uuid)
    try:
        reordenar_playlist(playlist, request.user, request.POST.getlist('video_ids'), request)
    except (ValueError, ValidationError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Ordem dos vídeos atualizada.')
    return redirect('painel:yubotuka_playlist_detalhe', uuid=playlist.uuid)


@login_required
def canal_lista(request):
    exigir(request.user, 'yubotuka.canal.gerenciar')
    canais = canais_permitidos(request.user).annotate(
        total_videos=Count('videos_editoriais', distinct=True),
        total_playlists=Count('playlists', distinct=True),
        total_programas=Count('programas', distinct=True),
    )
    return render(request, 'painel/yubotuka/channel_list.html', {
        **_contexto_base(request), 'canais': canais,
    })


@login_required
def canal_form(request, uuid=None):
    exigir(request.user, 'yubotuka.canal.gerenciar')
    canal = get_object_or_404(canais_permitidos(request.user), uuid=uuid) if uuid else None
    form = CanalForm(request.POST or None, request.FILES or None, instance=canal)
    if request.method == 'POST' and form.is_valid():
        canal = form.save(commit=False)
        if not canal.pk:
            canal.proprietario = request.user
        canal.save()
        auditar(request, 'EDITADO' if uuid else 'CRIADO', canal)
        messages.success(request, 'Canal salvo.')
        return redirect('painel:yubotuka_canais')
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form,
        'titulo': 'Editar canal' if uuid else 'Novo canal',
        'subtitulo': 'Configure a identidade e os links públicos do canal.',
        'cancelar_url': 'painel:yubotuka_canais',
    })


AUXILIARES = {
    'tags': (TagYuBotuka, TagForm, 'yubotuka.tag.gerenciar', 'Tags'),
    'apresentadores': (Apresentador, ApresentadorForm, 'yubotuka.apresentador.gerenciar', 'Apresentadores'),
    'convidados': (Convidado, ConvidadoForm, 'yubotuka.convidado.gerenciar', 'Convidados'),
    'patrocinadores': (Patrocinador, PatrocinadorForm, 'yubotuka.patrocinador.gerenciar', 'Patrocinadores'),
    'banners': (BannerYuBotuka, BannerForm, 'yubotuka.banner.gerenciar', 'Banners'),
    'motivos-rejeicao': (MotivoRejeicao, MotivoRejeicaoForm, 'yubotuka.motivo_rejeicao.gerenciar', 'Motivos de rejeição'),
    'destaques': (DestaqueEditorial, DestaqueEditorialForm, 'yubotuka.video.destacar', 'Destaques editoriais'),
}


@login_required
def auxiliar_lista(request, tipo):
    model, form_class, permissao, titulo = AUXILIARES.get(tipo, (None, None, None, None))
    if not model:
        raise PermissionDenied
    exigir(request.user, permissao, aceitar_legado=False)
    return render(request, 'painel/yubotuka/auxiliary_list.html', {
        **_contexto_base(request), 'objetos': model.objects.all(),
        'titulo': titulo, 'tipo': tipo,
    })


@login_required
def auxiliar_form(request, tipo, uuid=None):
    model, form_class, permissao, titulo = AUXILIARES.get(tipo, (None, None, None, None))
    if not model:
        raise PermissionDenied
    exigir(request.user, permissao, aceitar_legado=False)
    objeto = get_object_or_404(model, uuid=uuid) if uuid else None
    form = form_class(request.POST or None, request.FILES or None, instance=objeto)
    if request.method == 'POST' and form.is_valid():
        objeto = form.save()
        auditar(request, 'EDITADO' if uuid else 'CRIADO', objeto)
        messages.success(request, f'{model._meta.verbose_name.title()} salvo.')
        return redirect('painel:yubotuka_auxiliar_lista', tipo=tipo)
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form,
        'titulo': f'Editar {titulo}' if uuid else f'Novo cadastro · {titulo}',
        'subtitulo': 'Cadastro auxiliar do conteúdo audiovisual.',
        'cancelar_url': 'painel:yubotuka_auxiliar_lista', 'cancelar_tipo': tipo,
    })


@login_required
def configuracao(request):
    exigir(request.user, 'yubotuka.config.gerenciar', aceitar_legado=False)
    objeto, _ = ConfiguracaoYuBotuka.objects.get_or_create(pk=1)
    form = ConfiguracaoForm(request.POST or None, instance=objeto)
    if request.method == 'POST' and form.is_valid():
        objeto = form.save(commit=False)
        objeto.atualizado_por = request.user
        objeto.save()
        auditar(request, 'CONFIGURACAO_ALTERADA', objeto)
        messages.success(request, 'Configurações atualizadas.')
        return redirect('painel:yubotuka_configuracao')
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form,
        'titulo': 'Configurações do YoBotuka',
        'subtitulo': 'Controle a apresentação pública e os limites de conteúdo.',
        'cancelar_url': 'painel:yubotuka_dashboard',
    })


@login_required
def auditoria_lista(request):
    exigir(request.user, 'yubotuka.auditoria.visualizar', aceitar_legado=False)
    eventos = HistoricoEditorial.objects.select_related('video', 'usuario')
    acao = request.GET.get('acao', '')
    if acao in HistoricoEditorial.Acao.values:
        eventos = eventos.filter(acao=acao)
    return render(request, 'painel/yubotuka/audit_list.html', {
        **_contexto_base(request), 'eventos': eventos[:200],
        'acoes': HistoricoEditorial.Acao.choices,
    })
