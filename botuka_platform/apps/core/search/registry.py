from dataclasses import dataclass

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


@dataclass(frozen=True)
class SearchSpec:
    key: str
    label: str
    icon: str
    queryset: callable
    title_field: str
    summary_fields: tuple[str, ...]
    content_fields: tuple[str, ...]
    related_fields: tuple[str, ...]
    presenter: callable
    aliases: tuple[str, ...] = ()

    @property
    def fields(self):
        return (self.title_field, *self.summary_fields, *self.content_fields, *self.related_fields)


def _file_url(value):
    try:
        return value.url if value else ''
    except (ValueError, AttributeError):
        return ''


def _empresa():
    from apps.organizations.models import Empresa
    return Empresa.objects.filter(
        ativo=True, perfil_publico=True, status=Empresa.Status.ATIVA,
        excluido_em__isnull=True,
    ).select_related('categoria_empresa', 'cidade', 'estado')


def _servico():
    from apps.organizations.models import Empresa
    from apps.services.models import Servico
    return Servico.objects.filter(
        ativo=True, status=Servico.Status.PUBLICADO, excluido_em__isnull=True,
        publicado_em__isnull=False,
    ).filter(
        Q(empresa__isnull=True) | Q(
            empresa__ativo=True, empresa__perfil_publico=True,
            empresa__status=Empresa.Status.ATIVA, empresa__excluido_em__isnull=True,
        )
    ).select_related('empresa', 'setor', 'area', 'profissao', 'tipo_servico')


def _produto():
    from apps.products.public_catalog import produtos_publicos
    return produtos_publicos().select_related(
        'empresa_proprietaria', 'categoria_taxonomia', 'familia',
        'tipo_produto', 'segmento',
    )


def _evento():
    from apps.events.models import Evento
    return Evento.objects.filter(
        ativo=True, removido_em__isnull=True, publico=True,
        status=Evento.Status.PUBLICADO, publicado_em__isnull=False,
    ).select_related('empresa_promotora', 'proprietario')


def _artigo():
    from apps.news.selectors import artigos_publicos
    return artigos_publicos().prefetch_related('tags')


def _vaga():
    from apps.organizations.models import Empresa
    from apps.recruitment.models import Vaga
    return Vaga.objects.filter(
        Q(empresa__isnull=False, empresa__ativo=True, empresa__perfil_publico=True,
          empresa__status=Empresa.Status.ATIVA, empresa__excluido_em__isnull=True)
        | Q(perfil_pessoa_fisica__isnull=False, perfil_pessoa_fisica__is_active=True),
        status=Vaga.Status.PUBLICADA, publicado_em__isnull=False,
    ).filter(
        Q(encerramento__isnull=True) | Q(encerramento__gte=timezone.localdate())
    ).select_related('empresa', 'perfil_pessoa_fisica')


def _curriculo():
    from apps.recruitment.models import Curriculo
    return Curriculo.objects.filter(
        ativo=True, excluido_em__isnull=True, publico=True,
        status=Curriculo.Status.CONCLUIDO,
        visibilidade=Curriculo.Visibilidade.PUBLICO,
        usuario__is_active=True,
    ).select_related('usuario')


def _local():
    from apps.tourism.models import LocalTuristico, TurismoStatus
    return LocalTuristico.objects.filter(
        ativo=True, removido_em__isnull=True, status=TurismoStatus.PUBLICADO,
    ).select_related('categoria', 'empresa_responsavel')


def _guia():
    from apps.tourism.models import GuiaTuristico, TurismoStatus
    return GuiaTuristico.objects.filter(
        ativo=True, removido_em__isnull=True, status=TurismoStatus.PUBLICADO,
        verificado=True, usuario__is_active=True,
    ).select_related('usuario', 'empresa')


def _acao():
    from apps.government.views import _public_actions
    return _public_actions()


def _campeonato():
    from apps.sports.views import _public_championships
    return _public_championships().select_related('organizacao', 'modalidade', 'categoria')


def _episodio():
    from apps.media.selectors import videos_publicos
    return videos_publicos()


def _equipe():
    from apps.sports.models import Equipe
    return Equipe.objects.filter(
        ativo=True, excluido_em__isnull=True, organizacao__ativo=True,
        organizacao__verificado=True, organizacao__excluido_em__isnull=True,
    ).select_related('organizacao', 'modalidade', 'estilo', 'categoria')


def _atleta():
    from apps.sports.models import Atleta
    return Atleta.objects.filter(
        publico=True, ativo=True, excluido_em__isnull=True,
        equipe__organizacao__ativo=True, equipe__organizacao__verificado=True,
        equipe__organizacao__excluido_em__isnull=True,
    ).select_related('equipe', 'modalidade', 'estilo', 'categoria')


def _jogo():
    from apps.sports.views import _public_disputes
    return _public_disputes().select_related(
        'campeonato', 'campeonato__modalidade', 'participante_a',
        'participante_a__equipe', 'participante_a__atleta', 'participante_b',
        'participante_b__equipe', 'participante_b__atleta',
    )


def _roteiro():
    from apps.tourism.models import RoteiroTuristico, TurismoStatus
    return RoteiroTuristico.objects.filter(
        ativo=True, removido_em__isnull=True, status=TurismoStatus.PUBLICADO,
    ).prefetch_related('locais', 'guias')


def _present(obj, *, title, summary='', category='', owner='', location='', url='', image='', extra=''):
    return {
        'title': title, 'summary': summary, 'category': category, 'owner': owner,
        'location': location, 'url': url, 'image': image, 'extra': extra,
    }


def default_registry():
    return (
        SearchSpec('empresas', 'Empresas', 'bi-buildings', _empresa, 'nome_fantasia',
                   ('descricao_curta',), ('razao_social', 'descricao_completa', 'endereco', 'bairro'),
                   ('categoria_empresa__nome', 'cidade__nome', 'estado__sigla'),
                   lambda o: _present(o, title=o.nome_exibicao, summary=o.descricao_curta,
                       category=str(o.categoria_empresa or ''), location=o.endereco_resumido,
                       url=o.get_absolute_url(), image=_file_url(o.logo or o.imagem_capa)),
                   ('empresa', 'empresas', 'negocio', 'negocios', 'estabelecimento', 'estabelecimentos')),
        SearchSpec('servicos', 'Serviços', 'bi-tools', _servico, 'titulo',
                   ('descricao_curta',), ('descricao_completa', 'experiencia'),
                   ('empresa__nome_fantasia', 'setor__nome', 'area__nome', 'profissao__nome', 'tipo_servico__nome',
                    'atributos_adicionais__tipo', 'atributos_adicionais__nome_personalizado',
                    'atributos_adicionais__valor', 'atributos_adicionais__observacao'),
                   lambda o: _present(o, title=o.titulo, summary=o.descricao_curta,
                       category=str(o.setor), owner=o.empresa.nome_exibicao if o.empresa_id else 'Profissional autônomo',
                       url=reverse('publico:servico', args=[o.slug])),
                   ('servico', 'servicos', 'profissional', 'profissionais')),
        SearchSpec('produtos', 'Produtos', 'bi-bag', _produto, 'nome',
                   ('descricao_curta',), ('descricao_completa', 'tags', 'marca', 'modelo'),
                   ('empresa_proprietaria__nome_fantasia', 'categoria_taxonomia__nome', 'familia__nome', 'tipo_produto__nome', 'segmento__nome'),
                   lambda o: _present(o, title=o.nome, summary=o.descricao_curta,
                       category=str(o.categoria_taxonomia or o.categoria), owner=o.empresa_proprietaria.nome_exibicao if o.empresa_proprietaria_id else '',
                       url=o.get_absolute_url(), image=_file_url(o.imagem_social)),
                   ('produto', 'produtos', 'loja', 'compras')),
        SearchSpec('eventos', 'Eventos', 'bi-calendar-event', _evento, 'titulo',
                   ('resumo',), ('descricao', 'organizador', 'realizador', 'endereco'),
                   ('categoria', 'local', 'empresa_promotora__nome_fantasia'),
                   lambda o: _present(o, title=o.titulo, summary=o.resumo, category=o.categoria,
                       owner=o.organizador or (o.empresa_promotora.nome_exibicao if o.empresa_promotora_id else ''),
                       location=o.local, url=o.get_absolute_url(), image=_file_url(o.imagem_principal),
                       extra=o.inicio), ('evento', 'eventos', 'agenda')),
        SearchSpec('noticias', 'Notícias e artigos', 'bi-newspaper', _artigo, 'titulo',
                   ('subtitulo', 'resumo'), ('conteudo', 'titulo_seo', 'descricao_seo'),
                   ('categoria__nome', 'coluna__nome', 'serie__nome', 'temas__nome', 'tags__nome'),
                   lambda o: _present(o, title=o.titulo, summary=o.resumo,
                       category=str(o.categoria), owner=str(o.autor_editorial or o.autor),
                       url=reverse('news_public:artigo', args=[o.slug]), image=_file_url(o.imagem_capa),
                       extra=o.publicado_em), ('noticia', 'noticias', 'artigo', 'artigos', 'materia', 'materias')),
        SearchSpec('vagas', 'Vagas', 'bi-briefcase', _vaga, 'titulo',
                   ('descricao',), ('requisitos', 'responsabilidades', 'beneficios', 'experiencia'),
                   ('empresa__nome_fantasia', 'categoria', 'area_atuacao', 'cidade', 'estado', 'bairro',
                    'atributos_adicionais__tipo', 'atributos_adicionais__nome_personalizado',
                    'atributos_adicionais__valor', 'atributos_adicionais__observacao'),
                   lambda o: _present(o, title=o.titulo, summary=o.descricao,
                       category=o.categoria or o.tipo_contrato, owner=o.responsavel_publico,
                       location=' / '.join(filter(None, [o.cidade, o.estado])),
                       url=reverse('recruitment_public:vaga', args=[o.slug]), extra=o.encerramento),
                   ('vaga', 'vagas', 'emprego', 'empregos', 'oportunidade', 'oportunidades')),
        SearchSpec('curriculos', 'Profissionais', 'bi-person-badge', _curriculo, 'titulo_profissional',
                   ('resumo', 'objetivo_profissional'), ('disponibilidade',),
                   ('usuario__first_name', 'usuario__last_name', 'area_profissional', 'cidade', 'estado'),
                   lambda o: _present(o, title=o.titulo_profissional,
                       summary=o.resumo or o.objetivo_profissional, category=o.area_profissional,
                       owner=o.usuario.nome_exibicao, location=' / '.join(filter(None, [o.cidade, o.estado])),
                       url=reverse('recruitment_public:curriculo', args=[o.uuid])),
                   ('curriculo', 'curriculos', 'profissional', 'profissionais', 'talento', 'talentos')),
        SearchSpec('turismo', 'Turismo e locais', 'bi-compass', _local, 'nome',
                   ('descricao_curta',), ('descricao_completa', 'historia', 'alimentacao', 'acessibilidade', 'recomendacoes'),
                   ('categoria__nome', 'empresa_responsavel__nome_fantasia', 'logradouro', 'bairro', 'cidade', 'ponto_referencia', 'servicos_disponiveis__nome'),
                   lambda o: _present(o, title=o.nome, summary=o.descricao_curta,
                       category=str(o.categoria or o.categoria_legada), owner=str(o.empresa_responsavel or ''),
                       location=' · '.join(filter(None, [o.bairro, o.cidade])), url=reverse('tourism_public:local', args=[o.slug]),
                       image=_file_url(o.imagem_thumbnail or o.imagem_principal)),
                   ('turismo', 'local', 'locais', 'passeio', 'passeios', 'lugar', 'lugares')),
        SearchSpec('guias', 'Guias turísticos', 'bi-person-walking', _guia, 'nome_profissional',
                   ('apresentacao',), ('idiomas', 'especialidades', 'regioes_atendidas'),
                   ('empresa__nome_fantasia',), lambda o: _present(o, title=o.nome_profissional,
                       summary=o.apresentacao, category='Guia turístico', owner=str(o.empresa or ''),
                       location=o.regioes_atendidas, url=reverse('tourism_public:guia', args=[o.slug]), image=_file_url(o.foto)),
                   ('guia', 'guias', 'turismo')),
        SearchSpec('roteiros', 'Roteiros turísticos', 'bi-map', _roteiro, 'titulo',
                   ('resumo',), ('descricao', 'duracao', 'dificuldade', 'publico_indicado'),
                   ('locais__nome', 'locais__bairro', 'locais__cidade', 'guias__nome_profissional'),
                   lambda o: _present(o, title=o.titulo, summary=o.resumo, category='Roteiro turístico',
                       location=', '.join(item.nome for item in o.locais.all()[:3]),
                       url=reverse('tourism_public:roteiro', args=[o.slug])),
                   ('roteiro', 'roteiros', 'turismo', 'passeio', 'passeios')),
        SearchSpec('governo', 'Conteúdo público', 'bi-bank', _acao, 'titulo',
                   ('resumo',), ('descricao', 'objetivo', 'publico_alvo'),
                   ('orgao__nome', 'orgao__sigla', 'tipo', 'local', 'bairro', 'cidade'),
                   lambda o: _present(o, title=o.titulo, summary=o.resumo, category=o.get_tipo_display(),
                       owner=str(o.orgao), location=o.local or o.bairro, url=reverse('government_public:acao', args=[o.slug]),
                       image=_file_url(o.imagem), extra=o.publicado_em),
                   ('acao', 'acoes', 'governo', 'servico-publico', 'servicos-publicos')),
        SearchSpec('esportes', 'Esportes', 'bi-trophy', _campeonato, 'nome',
                   ('descricao',), ('regulamento', 'formato'),
                   ('organizacao__nome', 'modalidade__nome', 'categoria__nome', 'localidade'),
                   lambda o: _present(o, title=o.nome, summary=o.descricao, category=str(o.modalidade),
                       owner=str(o.organizacao), location=o.localidade, url=reverse('sports_public:campeonato', args=[o.slug]),
                       image=_file_url(o.imagem), extra=o.data_inicial),
                   ('esporte', 'esportes', 'campeonato', 'campeonatos', 'competicao', 'competicoes')),
        SearchSpec('equipes', 'Esportes — equipes', 'bi-people', _equipe, 'nome',
                   (), ('treinador', 'cidade', 'bairro'),
                   ('organizacao__nome', 'modalidade__nome', 'estilo__nome', 'categoria__nome'),
                   lambda o: _present(o, title=o.nome, category=str(o.modalidade),
                       owner=str(o.organizacao), location=' · '.join(filter(None, [o.bairro, o.cidade])),
                       url=reverse('sports_public:equipe', args=[o.slug]), image=_file_url(o.escudo)),
                   ('esporte', 'esportes', 'equipe', 'equipes', 'clube', 'clubes')),
        SearchSpec('atletas', 'Esportes — atletas', 'bi-person', _atleta, 'nome_publico',
                   ('apelido',), ('biografia', 'funcao'),
                   ('equipe__nome', 'modalidade__nome', 'estilo__nome', 'categoria__nome'),
                   lambda o: _present(o, title=o.nome_publico, summary=o.biografia,
                       category=str(o.modalidade), owner=str(o.equipe or ''),
                       url=reverse('sports_public:atleta', args=[o.uuid]), image=_file_url(o.foto)),
                   ('esporte', 'esportes', 'atleta', 'atletas', 'jogador', 'jogadores')),
        SearchSpec('jogos', 'Esportes — jogos', 'bi-calendar2-event', _jogo, 'campeonato__nome',
                   ('resultado_textual',), ('fase', 'rodada', 'tipo', 'local', 'observacoes'),
                   ('campeonato__modalidade__nome', 'participante_a__equipe__nome',
                    'participante_a__atleta__nome_publico', 'participante_b__equipe__nome',
                    'participante_b__atleta__nome_publico'),
                   lambda o: _present(o, title=str(o), summary=o.resultado_textual,
                       category=str(o.campeonato.modalidade), location=o.local,
                       url=reverse('sports_public:jogo', args=[o.uuid]), extra=o.data_hora),
                   ('esporte', 'esportes', 'jogo', 'jogos', 'partida', 'partidas', 'resultado', 'resultados')),
        SearchSpec('videos', 'Vídeos', 'bi-play-btn', _episodio, 'titulo',
                   ('descricao_curta',), ('descricao', 'titulo_seo', 'descricao_seo'),
                   ('programa__nome', 'programa__categoria', 'canal__nome', 'categoria__nome',
                    'categoria__categoria_pai__nome', 'itens_playlist__playlist__nome',
                    'itens_playlist__playlist__categoria__nome', 'videos_tags__tag__nome',
                    'videos_apresentadores__apresentador__nome'),
                   lambda o: _present(o, title=o.titulo, summary=o.descricao_curta or o.descricao,
                       category=str(o.categoria or o.get_tipo_display()), owner=str(o.canal),
                       url=reverse('media_public:video', args=[o.slug]),
                       image=o.thumbnail, extra=o.publicado_em),
                   ('video', 'videos', 'yubotuka')),
    )
