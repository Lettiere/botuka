from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_datetime

from apps.core.domain import auditar

from .forms import (
    CanalAtribuicaoForm,
    EpisodioEditorialForm,
    HomologacaoLegadoForm,
    ProgramaForm,
    TemporadaForm,
    TransmissaoForm,
)
from .models import (
    Canal,
    Episodio,
    HomologacaoVideoMigrado,
    Programa,
    Temporada,
    Transmissao,
)
from .permissions import exigir, possui
from .selectors import (
    canais_permitidos,
    programas_permitidos,
    transmissoes_visiveis_painel,
)
from .services import (
    agendar_transmissao,
    aprovar_transmissao,
    atribuir_canal,
    cancelar_transmissao,
    encerrar_transmissao,
    enviar_transmissao_analise,
    homologar_video_migrado,
    iniciar_transmissao,
    pode_editar_transmissao,
    publicar_transmissao,
)
from .yubotuka_views import _contexto_base


@login_required
def programa_lista(request):
    exigir(request.user, 'yubotuka.programa.gerenciar')
    programas = programas_permitidos(request.user, somente_ativos=False).annotate(
        total_temporadas=Count('temporadas', distinct=True),
        total_episodios=Count('episodios', distinct=True),
        total_publicados=Count(
            'videos_editoriais',
            filter=Q(videos_editoriais__status='PUBLICADO'),
            distinct=True,
        ),
    ).order_by('ordem', 'nome')
    return render(request, 'painel/yubotuka/program_list.html', {
        **_contexto_base(request), 'programas': programas,
    })


@login_required
def programa_form(request, uuid=None):
    exigir(request.user, 'yubotuka.programa.gerenciar')
    programa = get_object_or_404(programas_permitidos(request.user, somente_ativos=False), uuid=uuid) if uuid else None
    form = ProgramaForm(request.POST or None, request.FILES or None, instance=programa, user=request.user)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            programa = form.save()
            form.save_relacoes(programa)
            auditar(request, 'PROGRAMA_EDITADO' if uuid else 'PROGRAMA_CRIADO', programa)
        messages.success(request, 'Programa salvo.')
        return redirect('painel:yubotuka_programa_detalhe', uuid=programa.uuid)
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form,
        'titulo': 'Editar programa' if uuid else 'Novo programa',
        'subtitulo': 'Identidade editorial, canal, categoria e participantes.',
        'cancelar_url': 'painel:yubotuka_programas',
    })


@login_required
def programa_detalhe(request, uuid):
    exigir(request.user, 'yubotuka.programa.gerenciar')
    programa = get_object_or_404(programas_permitidos(request.user, somente_ativos=False), uuid=uuid)
    return render(request, 'painel/yubotuka/program_detail.html', {
        **_contexto_base(request), 'programa': programa,
        'temporadas': programa.temporadas.filter(excluido_em__isnull=True).order_by('ordem', 'numero'),
        'episodios': programa.episodios.filter(excluido_em__isnull=True).select_related('temporada', 'video_editorial')[:20],
    })


@login_required
def programa_alternar(request, uuid):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    exigir(request.user, 'yubotuka.programa.gerenciar')
    programa = get_object_or_404(programas_permitidos(request.user, somente_ativos=False), uuid=uuid)
    programa.ativo = not programa.ativo
    programa.save(update_fields=['ativo', 'atualizado_em'])
    auditar(request, 'PROGRAMA_ATIVADO' if programa.ativo else 'PROGRAMA_DESATIVADO', programa)
    return redirect('painel:yubotuka_programa_detalhe', uuid=programa.uuid)


@login_required
def temporada_lista(request):
    exigir(request.user, 'yubotuka.temporada.gerenciar')
    temporadas = Temporada.all_objects.filter(
        programa__in=programas_permitidos(request.user),
        excluido_em__isnull=True,
    ).select_related('programa', 'programa__canal').annotate(
        total_episodios=Count('episodios', distinct=True),
    ).order_by('programa__nome', 'ordem', 'numero')
    return render(request, 'painel/yubotuka/season_list.html', {
        **_contexto_base(request), 'temporadas': temporadas,
    })


@login_required
def temporada_form(request, uuid=None):
    exigir(request.user, 'yubotuka.temporada.gerenciar')
    queryset = Temporada.all_objects.filter(programa__in=programas_permitidos(request.user, somente_ativos=False))
    temporada = get_object_or_404(queryset, uuid=uuid) if uuid else None
    form = TemporadaForm(request.POST or None, request.FILES or None, instance=temporada, user=request.user)
    if request.method == 'POST' and form.is_valid():
        temporada = form.save()
        auditar(request, 'TEMPORADA_EDITADA' if uuid else 'TEMPORADA_CRIADA', temporada)
        messages.success(request, 'Temporada salva.')
        return redirect('painel:yubotuka_temporada_detalhe', uuid=temporada.uuid)
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form,
        'titulo': 'Editar temporada' if uuid else 'Nova temporada',
        'subtitulo': 'Defina número, período, capa e situação da temporada.',
        'cancelar_url': 'painel:yubotuka_temporadas',
    })


@login_required
def temporada_detalhe(request, uuid):
    exigir(request.user, 'yubotuka.temporada.gerenciar')
    temporada = get_object_or_404(
        Temporada.all_objects.filter(programa__in=programas_permitidos(request.user, somente_ativos=False)).select_related('programa'),
        uuid=uuid,
    )
    return render(request, 'painel/yubotuka/season_detail.html', {
        **_contexto_base(request), 'temporada': temporada,
        'episodios': temporada.episodios.filter(excluido_em__isnull=True).select_related('video_editorial'),
    })


@login_required
def episodio_lista(request):
    exigir(request.user, 'yubotuka.episodio.gerenciar')
    episodios = Episodio.all_objects.filter(
        programa__in=programas_permitidos(request.user),
        excluido_em__isnull=True,
    ).select_related('programa', 'temporada', 'video_editorial').order_by('programa__nome', 'temporada__numero', 'numero')
    return render(request, 'painel/yubotuka/episode_list.html', {
        **_contexto_base(request), 'episodios': episodios,
    })


@login_required
def episodio_form(request, uuid=None):
    exigir(request.user, 'yubotuka.episodio.gerenciar')
    queryset = Episodio.all_objects.filter(programa__in=programas_permitidos(request.user, somente_ativos=False))
    episodio = get_object_or_404(queryset, uuid=uuid) if uuid else None
    form = EpisodioEditorialForm(request.POST or None, instance=episodio, user=request.user)
    if request.method == 'POST' and form.is_valid():
        episodio = form.save()
        auditar(request, 'EPISODIO_EDITADO' if uuid else 'EPISODIO_CRIADO', episodio)
        messages.success(request, 'Episódio editorial salvo sem duplicar o vídeo.')
        return redirect('painel:yubotuka_episodio_detalhe', uuid=episodio.uuid)
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form,
        'titulo': 'Editar episódio' if uuid else 'Novo episódio',
        'subtitulo': 'O episódio organiza o programa e pode apontar para um Video existente.',
        'cancelar_url': 'painel:yubotuka_episodios',
    })


@login_required
def episodio_detalhe(request, uuid):
    exigir(request.user, 'yubotuka.episodio.gerenciar')
    episodio = get_object_or_404(
        Episodio.all_objects.filter(programa__in=programas_permitidos(request.user, somente_ativos=False)).select_related('programa', 'temporada', 'video_editorial'),
        uuid=uuid,
    )
    return render(request, 'painel/yubotuka/episode_detail.html', {
        **_contexto_base(request), 'episodio': episodio,
    })


@login_required
def transmissao_lista(request):
    exigir(request.user, 'yubotuka.dashboard.visualizar')
    transmissoes = transmissoes_visiveis_painel(request.user)
    return render(request, 'painel/yubotuka/transmission_list.html', {
        **_contexto_base(request), 'transmissoes': transmissoes,
        'pode_criar_transmissao': possui(request.user, 'yubotuka.transmissao.criar'),
    })


@login_required
def transmissao_form(request, uuid=None):
    if uuid:
        transmissao = get_object_or_404(transmissoes_visiveis_painel(request.user), uuid=uuid)
        if not pode_editar_transmissao(request.user, transmissao):
            raise PermissionDenied
    else:
        exigir(request.user, 'yubotuka.transmissao.criar')
        transmissao = None
    form = TransmissaoForm(request.POST or None, instance=transmissao, user=request.user)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            transmissao = form.save(commit=False)
            if not transmissao.pk:
                transmissao.autor = request.user
                transmissao.status = Transmissao.Status.RASCUNHO
            transmissao.save()
            form.save_relacoes(transmissao)
            auditar(request, 'TRANSMISSAO_EDITADA' if uuid else 'TRANSMISSAO_CRIADA', transmissao)
        messages.success(request, 'Transmissão salva como conteúdo editorial.')
        return redirect('painel:yubotuka_transmissao_detalhe', uuid=transmissao.uuid)
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form,
        'titulo': 'Editar transmissão' if uuid else 'Nova transmissão',
        'subtitulo': 'O status ao vivo nunca é definido diretamente neste formulário.',
        'cancelar_url': 'painel:yubotuka_transmissoes',
    })


@login_required
def transmissao_detalhe(request, uuid):
    transmissao = get_object_or_404(transmissoes_visiveis_painel(request.user), uuid=uuid)
    return render(request, 'painel/yubotuka/transmission_detail.html', {
        **_contexto_base(request), 'transmissao': transmissao,
        'pode_editar': pode_editar_transmissao(request.user, transmissao),
        'pode_aprovar': possui(request.user, 'yubotuka.transmissao.aprovar', aceitar_legado=False),
        'pode_publicar_transmissao': possui(request.user, 'yubotuka.transmissao.publicar', aceitar_legado=False),
        'pode_cancelar': possui(request.user, 'yubotuka.transmissao.cancelar', aceitar_legado=False),
    })


def _acao_transmissao(request, uuid, servico, sucesso, *args):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    transmissao = get_object_or_404(Transmissao, uuid=uuid, excluido_em__isnull=True)
    try:
        servico(transmissao, request.user, *args, request=request)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    else:
        messages.success(request, sucesso)
    return redirect('painel:yubotuka_transmissao_detalhe', uuid=transmissao.uuid)


@login_required
def transmissao_enviar(request, uuid):
    return _acao_transmissao(request, uuid, enviar_transmissao_analise, 'Transmissão enviada para análise.')


@login_required
def transmissao_aprovar(request, uuid):
    return _acao_transmissao(request, uuid, aprovar_transmissao, 'Transmissão aprovada.')


@login_required
def transmissao_agendar(request, uuid):
    data = parse_datetime(request.POST.get('data_prevista', '')) if request.method == 'POST' else None
    return _acao_transmissao(request, uuid, agendar_transmissao, 'Transmissão agendada.', data)


@login_required
def transmissao_iniciar(request, uuid):
    return _acao_transmissao(request, uuid, iniciar_transmissao, 'Transmissão marcada como ao vivo.')


@login_required
def transmissao_encerrar(request, uuid):
    return _acao_transmissao(request, uuid, encerrar_transmissao, 'Transmissão encerrada.')


@login_required
def transmissao_publicar(request, uuid):
    return _acao_transmissao(request, uuid, publicar_transmissao, 'Gravação da transmissão publicada.')


@login_required
def transmissao_cancelar(request, uuid):
    return _acao_transmissao(request, uuid, cancelar_transmissao, 'Transmissão cancelada.')


@login_required
def atribuicao_canais(request):
    exigir(request.user, 'yubotuka.canal.atribuir', aceitar_legado=False)
    canais = Canal.all_objects.filter(excluido_em__isnull=True).select_related('proprietario').annotate(
        total_autorizados=Count('usuarios_autorizados', filter=Q(usuarios_autorizados__ativo=True)),
    )
    return render(request, 'painel/yubotuka/channel_assignment_list.html', {
        **_contexto_base(request), 'canais': canais,
    })


@login_required
def atribuicao_canal(request, uuid):
    exigir(request.user, 'yubotuka.canal.atribuir', aceitar_legado=False)
    canal = get_object_or_404(Canal.all_objects, uuid=uuid)
    form = CanalAtribuicaoForm(request.POST or None, initial={'proprietario': canal.proprietario})
    if request.method == 'POST' and form.is_valid():
        atribuir_canal(
            canal, request.user, form.cleaned_data['proprietario'],
            form.cleaned_data['usuario_autorizado'], form.cleaned_data['pode_editar'],
            form.cleaned_data['pode_moderar'], form.cleaned_data['motivo'], request,
        )
        messages.success(request, 'Atribuição do canal registrada na auditoria.')
        return redirect('painel:yubotuka_atribuicao_canais')
    return render(request, 'painel/yubotuka/form.html', {
        **_contexto_base(request), 'form': form,
        'titulo': f'Atribuir canal · {canal.nome}',
        'subtitulo': 'Nenhum usuário é atribuído automaticamente.',
        'cancelar_url': 'painel:yubotuka_atribuicao_canais',
    })


@login_required
def homologacao_lista(request):
    exigir(request.user, 'yubotuka.legado.homologar', aceitar_legado=False)
    homologacoes = HomologacaoVideoMigrado.objects.select_related(
        'video', 'video__autor', 'video__canal', 'episodio_legado',
    )
    return render(request, 'painel/yubotuka/legacy_list.html', {
        **_contexto_base(request), 'homologacoes': homologacoes,
    })


@login_required
def homologacao_detalhe(request, uuid):
    exigir(request.user, 'yubotuka.legado.homologar', aceitar_legado=False)
    homologacao = get_object_or_404(
        HomologacaoVideoMigrado.objects.select_related('video', 'episodio_legado'),
        uuid=uuid,
    )
    form = HomologacaoLegadoForm(
        request.POST or None, user=request.user,
        initial={
            'autor': homologacao.video.autor,
            'canal': homologacao.video.canal,
            'categoria': homologacao.video.categoria,
        },
    )
    if request.method == 'POST' and form.is_valid():
        homologar_video_migrado(
            homologacao, request.user, form.cleaned_data['autor'],
            form.cleaned_data['canal'], form.cleaned_data['categoria'],
            form.cleaned_data['playlist'], form.cleaned_data['observacao'], request,
        )
        messages.success(request, 'Vídeo legado homologado sem alterar URL ou slug.')
        return redirect('painel:yubotuka_homologacao_lista')
    return render(request, 'painel/yubotuka/legacy_detail.html', {
        **_contexto_base(request), 'homologacao': homologacao, 'form': form,
    })
