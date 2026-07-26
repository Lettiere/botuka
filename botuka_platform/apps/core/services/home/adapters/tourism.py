from django.urls import reverse

from apps.tourism.models import (
    EmpresaTuristica, ExperienciaTuristica, GuiaTuristico, LocalTuristico,
    RoteiroTuristico, TurismoPlaylist, TurismoStatus, TurismoVideo,
)

from .dto import ConteudoCidadeDTO


def _dto(obj, titulo, resumo, categoria, local='', imagem_url='', url=None):
    return ConteudoCidadeDTO(
        uuid=obj.uuid, titulo=titulo, resumo=resumo, categoria=categoria,
        local=local, imagem_url=imagem_url,
        url=url or reverse('tourism_public:home'), origem='Turismo BOTUKA',
    )


def obter_turismo():
    locais = LocalTuristico.objects.filter(
        status=TurismoStatus.PUBLICADO,
    ).exclude(
        imagem_principal='',
    ).order_by('-destaque_home', '-publicado_em')[:5]
    resultado = []
    for local in locais:
        if local.visibilidade_localizacao == 'PRIVADA':
            local_publico = ''
        elif local.visibilidade_localizacao == 'APROXIMADA' and local.bairro:
            local_publico = f'{local.bairro} · {local.cidade}'
        else:
            local_publico = f'{local.bairro} · {local.cidade}' if local.bairro else local.cidade
        resultado.append(_dto(
            local, local.nome, local.descricao_curta, local.categoria,
            local_publico,
            local.imagem_thumbnail.url if local.imagem_thumbnail else local.imagem_principal.url,
            reverse('tourism_public:local', args=[local.slug]),
        ))
    return resultado


def obter_secoes_turismo():
    publicado = {'status': TurismoStatus.PUBLICADO}
    return {
        'guias': [
            _dto(item, item.nome_profissional, item.apresentacao[:180], 'Guia oficial',
                 item.regioes_atendidas, item.foto.url if item.foto else '',
                 reverse('tourism_public:guia', args=[item.slug]))
            for item in GuiaTuristico.objects.filter(**publicado, verificado=True)[:4]
        ],
        'empresas': [
            _dto(item, item.empresa.nome_exibicao, item.apresentacao[:180], item.get_tipo_atuacao_display(),
                 item.regioes_atendidas, item.empresa.logo.url if item.empresa.logo else '')
            for item in EmpresaTuristica.objects.filter(**publicado).select_related('empresa')[:4]
        ],
        'roteiros': [
            _dto(item, item.titulo, item.resumo, 'Roteiro', item.duracao,
                 url=reverse('tourism_public:roteiro', args=[item.slug]))
            for item in RoteiroTuristico.objects.filter(**publicado)[:4]
        ],
        'experiencias': [
            _dto(item, item.titulo, item.resumo, 'Experiência', item.duracao)
            for item in ExperienciaTuristica.objects.filter(**publicado)[:4]
        ],
        'videos': [
            _dto(item, item.titulo, item.descricao[:180], 'Vídeo', '',
                 item.thumbnail, f'https://www.youtube.com/watch?v={item.youtube_video_id}')
            for item in TurismoVideo.objects.filter(**publicado)[:4]
        ],
        'playlists': [
            _dto(item, item.titulo, item.descricao[:180], 'Playlist', item.cidade,
                 item.capa.url if item.capa else '', item.url_youtube or None)
            for item in TurismoPlaylist.objects.filter(**publicado)[:4]
        ],
    }
