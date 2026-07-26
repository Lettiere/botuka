from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.domain import auditar

from .models import (
    Canal,
    CanalUsuario,
    HistoricoEditorial,
    HomologacaoVideoMigrado,
    Playlist,
    PlaylistVideo,
    Transmissao,
    Video,
)
from .permissions import e_administrador, exigir, pode_editar_video, pode_publicar, possui


def _ip(request):
    return request.META.get('REMOTE_ADDR') if request else None


def _registrar(video, user, acao, anterior, novo, request=None, descricao=''):
    HistoricoEditorial.objects.create(
        video=video, usuario=user, acao=acao,
        status_anterior=anterior or '', status_novo=novo or '',
        descricao=descricao, ip=_ip(request),
    )
    if request:
        auditar(
            request, acao, video,
            antes={'status': anterior}, depois={'status': novo},
            motivo=descricao,
        )


@transaction.atomic
def enviar_para_analise(video, user, request=None):
    video = Video.objects.select_for_update().get(pk=video.pk)
    exigir(user, 'yubotuka.video.enviar_analise')
    if not pode_editar_video(user, video):
        raise PermissionDenied('Somente o autor ou um editor autorizado pode enviar este vídeo.')
    if video.status not in {Video.Status.RASCUNHO, Video.Status.CORRECAO, Video.Status.REJEITADO}:
        raise ValidationError('Este vídeo não pode ser enviado para análise no estado atual.')
    if not video.youtube_url or not video.video_id:
        raise ValidationError('Informe uma URL válida do YouTube antes de enviar para análise.')
    anterior = video.status
    video.status = Video.Status.EM_ANALISE
    video.motivo_rejeicao = None
    video.observacao_rejeicao = ''
    video.save(update_fields=[
        'status', 'motivo_rejeicao', 'observacao_rejeicao', 'atualizado_em',
    ])
    _registrar(video, user, HistoricoEditorial.Acao.ENVIADO_ANALISE, anterior, video.status, request)
    return video


@transaction.atomic
def aprovar_video(video, user, request=None):
    exigir(user, 'yubotuka.video.aprovar', aceitar_legado=False)
    video = Video.objects.select_for_update().get(pk=video.pk)
    if video.status != Video.Status.EM_ANALISE:
        raise ValidationError('Somente vídeos em análise podem ser aprovados.')
    anterior = video.status
    video.status = Video.Status.APROVADO
    video.moderado_por = user
    video.save(update_fields=['status', 'moderado_por', 'atualizado_em'])
    _registrar(video, user, HistoricoEditorial.Acao.APROVADO, anterior, video.status, request)
    return video


@transaction.atomic
def rejeitar_video(video, user, motivo, observacao='', request=None):
    exigir(user, 'yubotuka.video.rejeitar', aceitar_legado=False)
    if not motivo:
        raise ValidationError('O motivo da rejeição é obrigatório.')
    video = Video.objects.select_for_update().get(pk=video.pk)
    if video.status != Video.Status.EM_ANALISE:
        raise ValidationError('Somente vídeos em análise podem ser rejeitados.')
    anterior = video.status
    video.status = Video.Status.REJEITADO
    video.moderado_por = user
    video.motivo_rejeicao = motivo
    video.observacao_rejeicao = observacao.strip()
    video.save(update_fields=[
        'status', 'moderado_por', 'motivo_rejeicao',
        'observacao_rejeicao', 'atualizado_em',
    ])
    _registrar(
        video, user, HistoricoEditorial.Acao.REJEITADO,
        anterior, video.status, request, video.observacao_rejeicao,
    )
    return video


@transaction.atomic
def devolver_para_correcao(video, user, request=None):
    video = Video.objects.select_for_update().get(pk=video.pk)
    if video.autor_id != user.pk and not pode_editar_video(user, video):
        raise PermissionDenied('Somente o autor ou um editor autorizado pode corrigir este vídeo.')
    if video.status != Video.Status.REJEITADO:
        raise ValidationError('Somente vídeos rejeitados podem voltar para correção.')
    anterior = video.status
    video.status = Video.Status.CORRECAO
    video.save(update_fields=['status', 'atualizado_em'])
    _registrar(video, user, HistoricoEditorial.Acao.DEVOLVIDO, anterior, video.status, request)
    return video


@transaction.atomic
def agendar_video(video, user, data_agendamento, request=None):
    exigir(user, 'yubotuka.video.agendar', aceitar_legado=False)
    video = Video.objects.select_for_update().get(pk=video.pk)
    if video.status != Video.Status.APROVADO:
        raise ValidationError('Somente vídeos aprovados podem ser agendados.')
    if not data_agendamento or data_agendamento <= timezone.now():
        raise ValidationError('Informe uma data futura para o agendamento.')
    anterior = video.status
    video.status = Video.Status.AGENDADO
    video.data_agendamento = data_agendamento
    video.save(update_fields=['status', 'data_agendamento', 'atualizado_em'])
    _registrar(video, user, HistoricoEditorial.Acao.AGENDADO, anterior, video.status, request)
    return video


@transaction.atomic
def publicar_video(video, user, request=None):
    if not pode_publicar(user):
        raise PermissionDenied('A publicação exige autorização explícita.')
    video = Video.objects.select_for_update().get(pk=video.pk)
    if video.status not in {Video.Status.APROVADO, Video.Status.AGENDADO}:
        raise ValidationError('Somente vídeos aprovados ou agendados podem ser publicados.')
    anterior = video.status
    video.status = Video.Status.PUBLICADO
    video.publicado_em = timezone.now()
    video.moderado_por = user
    video.save(update_fields=['status', 'publicado_em', 'moderado_por', 'atualizado_em'])
    _registrar(video, user, HistoricoEditorial.Acao.PUBLICADO, anterior, video.status, request)
    return video


@transaction.atomic
def arquivar_video(video, user, motivo, request=None):
    exigir(user, 'yubotuka.video.arquivar', aceitar_legado=False)
    video = Video.objects.select_for_update().get(pk=video.pk)
    pode_atuar = (
        e_administrador(user)
        or possui(user, 'yubotuka.video.editar_todos')
        or video.autor_id == user.pk
    )
    if not pode_atuar:
        raise PermissionDenied('Você não pode arquivar conteúdo de outro autor.')
    if video.status == Video.Status.ARQUIVADO:
        raise ValidationError('Este vídeo já está arquivado.')
    if not (motivo or '').strip():
        raise ValidationError('Informe o motivo do arquivamento.')
    anterior = video.status
    video.status_antes_arquivamento = anterior
    video.status = Video.Status.ARQUIVADO
    video.motivo_arquivamento = motivo.strip()
    video.arquivado_por = user
    video.save(update_fields=[
        'status_antes_arquivamento', 'status', 'motivo_arquivamento',
        'arquivado_por', 'atualizado_em',
    ])
    _registrar(
        video, user, HistoricoEditorial.Acao.ARQUIVADO,
        anterior, video.status, request, video.motivo_arquivamento,
    )
    return video


@transaction.atomic
def restaurar_video(video, user, request=None):
    exigir(user, 'yubotuka.video.arquivar', aceitar_legado=False)
    video = Video.objects.select_for_update().get(pk=video.pk)
    pode_atuar = (
        e_administrador(user)
        or possui(user, 'yubotuka.video.editar_todos')
        or video.autor_id == user.pk
    )
    if not pode_atuar:
        raise PermissionDenied('Você não pode restaurar conteúdo de outro autor.')
    if video.status != Video.Status.ARQUIVADO:
        raise ValidationError('Somente vídeos arquivados podem ser restaurados.')
    anterior = video.status
    destino = video.status_antes_arquivamento
    if destino not in {
        Video.Status.RASCUNHO, Video.Status.CORRECAO, Video.Status.REJEITADO,
        Video.Status.APROVADO, Video.Status.AGENDADO, Video.Status.PUBLICADO,
    }:
        destino = Video.Status.RASCUNHO
    video.status = destino
    video.status_antes_arquivamento = ''
    video.motivo_arquivamento = ''
    video.arquivado_por = None
    video.save(update_fields=[
        'status', 'status_antes_arquivamento', 'motivo_arquivamento',
        'arquivado_por', 'atualizado_em',
    ])
    _registrar(
        video, user, HistoricoEditorial.Acao.RESTAURADO,
        anterior, video.status, request,
    )
    return video


@transaction.atomic
def reordenar_playlist(playlist, user, video_ids, request=None):
    exigir(user, 'yubotuka.playlist.gerenciar')
    playlist = Playlist.objects.select_for_update().get(pk=playlist.pk)
    ids = [int(item) for item in video_ids]
    if len(ids) != len(set(ids)):
        raise ValidationError('A ordenação contém vídeos duplicados.')
    itens = list(
        PlaylistVideo.objects.select_for_update()
        .filter(playlist=playlist, video_id__in=ids)
    )
    if len(itens) != len(ids) or PlaylistVideo.objects.filter(playlist=playlist).count() != len(ids):
        raise ValidationError('A ordenação deve conter exatamente todos os vídeos da playlist.')
    por_video = {item.video_id: item for item in itens}
    PlaylistVideo.objects.filter(playlist=playlist).update(ordem=models.F('ordem') + 100000)
    for ordem, video_id in enumerate(ids, start=1):
        PlaylistVideo.objects.filter(pk=por_video[video_id].pk).update(ordem=ordem)
    if request:
        auditar(
            request, HistoricoEditorial.Acao.ORDEM_ALTERADA, playlist,
            depois={'videos': ids},
        )
    return playlist


def pode_editar_transmissao(user, transmissao):
    return (
        possui(user, 'yubotuka.transmissao.editar_todas')
        or (
            transmissao.autor_id == user.pk
            and possui(user, 'yubotuka.transmissao.editar_propria')
            and transmissao.status in {
                Transmissao.Status.RASCUNHO,
                Transmissao.Status.CANCELADA,
            }
        )
    )


@transaction.atomic
def enviar_transmissao_analise(transmissao, user, request=None):
    exigir(user, 'yubotuka.transmissao.enviar_analise')
    transmissao = Transmissao.objects.select_for_update().get(pk=transmissao.pk)
    if not pode_editar_transmissao(user, transmissao):
        raise PermissionDenied('Você não pode enviar esta transmissão para análise.')
    if transmissao.status not in {Transmissao.Status.RASCUNHO, Transmissao.Status.CANCELADA}:
        raise ValidationError('A transmissão não pode ser enviada no estado atual.')
    if not transmissao.url_ao_vivo or not transmissao.video_id or not transmissao.data_prevista:
        raise ValidationError('Informe URL válida e data prevista antes do envio.')
    anterior = transmissao.status
    transmissao.status = Transmissao.Status.EM_ANALISE
    transmissao.save(update_fields=['status', 'atualizado_em'])
    if request:
        auditar(request, 'TRANSMISSAO_ENVIADA_ANALISE', transmissao, antes={'status': anterior}, depois={'status': transmissao.status})
    return transmissao


@transaction.atomic
def aprovar_transmissao(transmissao, user, request=None):
    exigir(user, 'yubotuka.transmissao.aprovar', aceitar_legado=False)
    transmissao = Transmissao.objects.select_for_update().get(pk=transmissao.pk)
    if transmissao.status != Transmissao.Status.EM_ANALISE:
        raise ValidationError('Somente transmissões em análise podem ser aprovadas.')
    anterior = transmissao.status
    transmissao.status = Transmissao.Status.APROVADO
    transmissao.moderado_por = user
    transmissao.save(update_fields=['status', 'moderado_por', 'atualizado_em'])
    if request:
        auditar(request, 'TRANSMISSAO_APROVADA', transmissao, antes={'status': anterior}, depois={'status': transmissao.status})
    return transmissao


@transaction.atomic
def agendar_transmissao(transmissao, user, data_prevista, request=None):
    exigir(user, 'yubotuka.transmissao.publicar', aceitar_legado=False)
    transmissao = Transmissao.objects.select_for_update().get(pk=transmissao.pk)
    if transmissao.status != Transmissao.Status.APROVADO:
        raise ValidationError('Somente transmissões aprovadas podem ser agendadas.')
    if not data_prevista or data_prevista <= timezone.now():
        raise ValidationError('Informe uma data futura.')
    anterior = transmissao.status
    transmissao.status = Transmissao.Status.AGENDADA
    transmissao.data_prevista = data_prevista
    transmissao.save(update_fields=['status', 'data_prevista', 'atualizado_em'])
    if request:
        auditar(request, 'TRANSMISSAO_AGENDADA', transmissao, antes={'status': anterior}, depois={'status': transmissao.status})
    return transmissao


@transaction.atomic
def iniciar_transmissao(transmissao, user, request=None):
    exigir(user, 'yubotuka.transmissao.publicar', aceitar_legado=False)
    transmissao = Transmissao.objects.select_for_update().get(pk=transmissao.pk)
    if transmissao.status not in {Transmissao.Status.APROVADO, Transmissao.Status.AGENDADA}:
        raise ValidationError('A transmissão precisa estar aprovada ou agendada.')
    if transmissao.data_prevista and transmissao.data_prevista > timezone.now():
        raise ValidationError('A transmissão ainda não atingiu o horário previsto.')
    if not transmissao.video_id:
        raise ValidationError('Informe uma URL válida antes de iniciar.')
    anterior = transmissao.status
    transmissao.status = Transmissao.Status.AO_VIVO
    transmissao.inicio = timezone.now()
    transmissao.moderado_por = user
    transmissao.save(update_fields=['status', 'inicio', 'moderado_por', 'atualizado_em'])
    if request:
        auditar(request, 'TRANSMISSAO_INICIADA', transmissao, antes={'status': anterior}, depois={'status': transmissao.status})
    return transmissao


@transaction.atomic
def encerrar_transmissao(transmissao, user, request=None):
    exigir(user, 'yubotuka.transmissao.publicar', aceitar_legado=False)
    transmissao = Transmissao.objects.select_for_update().get(pk=transmissao.pk)
    if transmissao.status != Transmissao.Status.AO_VIVO:
        raise ValidationError('Somente transmissões ao vivo podem ser encerradas.')
    anterior = transmissao.status
    transmissao.status = Transmissao.Status.ENCERRADA
    transmissao.fim = timezone.now()
    transmissao.save(update_fields=['status', 'fim', 'atualizado_em'])
    if request:
        auditar(request, 'TRANSMISSAO_ENCERRADA', transmissao, antes={'status': anterior}, depois={'status': transmissao.status})
    return transmissao


@transaction.atomic
def publicar_transmissao(transmissao, user, request=None):
    exigir(user, 'yubotuka.transmissao.publicar', aceitar_legado=False)
    transmissao = Transmissao.objects.select_for_update().get(pk=transmissao.pk)
    if transmissao.status != Transmissao.Status.ENCERRADA:
        raise ValidationError('Somente transmissões encerradas podem ser publicadas.')
    if not transmissao.video_resultante_id and not transmissao.video_id:
        raise ValidationError('Associe uma gravação ou mantenha uma URL válida antes de publicar.')
    anterior = transmissao.status
    transmissao.status = Transmissao.Status.PUBLICADA
    transmissao.save(update_fields=['status', 'atualizado_em'])
    if request:
        auditar(
            request, 'TRANSMISSAO_PUBLICADA', transmissao,
            antes={'status': anterior}, depois={'status': transmissao.status},
        )
    return transmissao


@transaction.atomic
def cancelar_transmissao(transmissao, user, request=None):
    exigir(user, 'yubotuka.transmissao.cancelar', aceitar_legado=False)
    transmissao = Transmissao.objects.select_for_update().get(pk=transmissao.pk)
    if transmissao.status in {Transmissao.Status.ENCERRADA, Transmissao.Status.PUBLICADA, Transmissao.Status.ARQUIVADA}:
        raise ValidationError('Esta transmissão não pode mais ser cancelada.')
    anterior = transmissao.status
    transmissao.status = Transmissao.Status.CANCELADA
    transmissao.save(update_fields=['status', 'atualizado_em'])
    if request:
        auditar(request, 'TRANSMISSAO_CANCELADA', transmissao, antes={'status': anterior}, depois={'status': transmissao.status})
    return transmissao


@transaction.atomic
def atribuir_canal(canal, administrador, proprietario, usuario_autorizado, pode_editar, pode_moderar, motivo, request=None):
    exigir(administrador, 'yubotuka.canal.atribuir', aceitar_legado=False)
    if not (motivo or '').strip():
        raise ValidationError('Informe o motivo da atribuição.')
    canal = Canal.objects.select_for_update().get(pk=canal.pk)
    anterior = canal.proprietario_id
    canal.proprietario = proprietario
    canal.save(update_fields=['proprietario', 'atualizado_em'])
    if usuario_autorizado:
        CanalUsuario.objects.update_or_create(
            canal=canal, usuario=usuario_autorizado,
            ativo=True, revogado_em__isnull=True,
            defaults={
                'pode_editar': pode_editar, 'pode_moderar': pode_moderar,
                'concedido_por': administrador, 'motivo': motivo.strip(),
            },
        )
    if request:
        auditar(
            request, 'CANAL_ATRIBUIDO', canal,
            antes={'proprietario_id': anterior},
            depois={
                'proprietario_id': proprietario.pk if proprietario else None,
                'usuario_autorizado_id': usuario_autorizado.pk if usuario_autorizado else None,
            },
            motivo=motivo,
        )
    return canal


@transaction.atomic
def homologar_video_migrado(homologacao, administrador, autor, canal, categoria, playlist=None, observacao='', request=None):
    exigir(administrador, 'yubotuka.legado.homologar', aceitar_legado=False)
    homologacao = HomologacaoVideoMigrado.objects.select_for_update().select_related('video', 'episodio_legado').get(pk=homologacao.pk)
    video = homologacao.video
    url_preservada = video.youtube_url
    slug_preservado = video.slug
    video.autor = autor
    video.canal = canal
    video.categoria = categoria
    video.save(update_fields=['autor', 'canal', 'categoria', 'atualizado_em'])
    if video.youtube_url != url_preservada or video.slug != slug_preservado:
        raise ValidationError('A homologação não pode alterar URL ou slug.')
    if playlist:
        proxima = PlaylistVideo.objects.filter(playlist=playlist).order_by('-ordem').values_list('ordem', flat=True).first()
        PlaylistVideo.objects.get_or_create(
            playlist=playlist, video=video,
            defaults={'ordem': (proxima or 0) + 1, 'adicionado_por': administrador},
        )
    homologacao.homologado = True
    homologacao.homologado_por = administrador
    homologacao.homologado_em = timezone.now()
    homologacao.observacao = observacao
    homologacao.valores_confirmados = {
        'autor_id': autor.pk if autor else None,
        'canal_id': canal.pk,
        'categoria_id': categoria.pk if categoria else None,
        'playlist_id': playlist.pk if playlist else None,
        'slug': video.slug,
        'youtube_url': video.youtube_url,
    }
    homologacao.save()
    if request:
        auditar(request, 'VIDEO_LEGADO_HOMOLOGADO', video, depois=homologacao.valores_confirmados, motivo=observacao)
    return homologacao
