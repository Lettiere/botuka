from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.search import GlobalSearchService
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Capacidade, Empresa, EmpresaCapacidade
from apps.services.models import AreaProfissional, FormaCobranca, Profissao, ProfissaoTipoServico, Servico, Setor, TipoServico
from apps.media.models import (
    Canal, CategoriaYuBotuka, Playlist, PlaylistVideo, TagYuBotuka, Video, VideoTag,
)
from apps.events.models import Evento
from apps.news.models import Artigo, CategoriaNoticia, EditorialStatus
from apps.recruitment.models import Vaga
from apps.sports.models import Campeonato, Modalidade, OrganizacaoEsportiva
from apps.tourism.models import LocalTuristico, TurismoStatus


class GlobalSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('search-owner', password='safe-pass')
        pais = Pais.objects.create(nome='Brasil Busca', codigo_iso_2='SB', codigo_iso_3='SBR')
        cls.estado = Estado.objects.create(pais=pais, nome='São Paulo Busca', sigla='SX')
        cls.cidade = Cidade.objects.create(estado=cls.estado, nome='Botucatu Busca')
        cls.category_company = cls.company(
            'Consultoria Alimentar',
            descricao_curta='Consultoria especializada em segurança e alimentação para restaurantes',
        )
        cls.description_company = cls.company(
            'Empresa Genérica',
            descricao_curta='Consultoria alimentar para cozinhas',
        )
        cls.private_company = cls.company(
            'Segurança Alimentar Privada', perfil_publico=False,
        )
        cls.sector = Setor.objects.create(nome='Jurídico')
        cls.area = AreaProfissional.objects.create(
            setor=cls.sector, nome='Assessoria jurídica'
        )
        cls.profession = Profissao.objects.create(
            setor=cls.sector, area=cls.area, nome='Advocacia'
        )
        cls.service_type = TipoServico.objects.create(nome='Consultoria trabalhista')
        ProfissaoTipoServico.objects.create(
            profissao=cls.profession, tipo_servico=cls.service_type,
        )
        cls.billing = FormaCobranca.objects.create(nome='Por serviço')
        EmpresaCapacidade.objects.create(
            empresa=cls.category_company,
            capacidade=Capacidade.objects.get(codigo='PRESTAR_SERVICOS'),
            status=EmpresaCapacidade.Status.APROVADA,
        )
        cls.service = Servico.objects.create(
            usuario_responsavel=cls.user, empresa=cls.category_company,
            prestador_tipo=Servico.PrestadorTipo.EMPRESA, setor=cls.sector,
            area=cls.area, profissao=cls.profession, tipo_servico=cls.service_type,
            forma_cobranca=cls.billing, titulo='Assessoria jurídica',
            descricao_curta='Apoio especializado', status=Servico.Status.PUBLICADO,
            ativo=True, publicado_em=timezone.now(),
        )
        cls.channel = Canal.objects.create(nome='YuBotuka Testes', proprietario=cls.user, oficial=True)
        cls.video_category = CategoriaYuBotuka.objects.create(nome='Música', slug='musica-testes')
        cls.video = Video.objects.create(
            titulo='Concerto instrumental botucatuense',
            descricao_curta='Apresentação cultural com música autoral',
            descricao='Artistas locais apresentam repertório independente.',
            youtube_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            canal=cls.channel, categoria=cls.video_category, autor=cls.user,
            status=Video.Status.PUBLICADO, publico=True, ativo=True,
            publicado_em=timezone.now(),
        )
        cls.playlist = Playlist.objects.create(
            nome='YuBotuka — Cultura Musical', slug='cultura-musical-testes',
            canal=cls.channel, categoria=cls.video_category, proprietario=cls.user,
        )
        PlaylistVideo.objects.create(
            playlist=cls.playlist, video=cls.video, ordem=1, adicionado_por=cls.user,
        )
        tag = TagYuBotuka.objects.create(nome='Som independente', slug='som-independente-testes')
        VideoTag.objects.create(video=cls.video, tag=tag)
        now = timezone.now()
        cls.event = Evento.objects.create(
            titulo='Festival de teatro comunitário', resumo='Arte nos bairros',
            descricao='Programação de cultura para toda a cidade.', inicio=now,
            local='Teatro Municipal', categoria='Cultura', proprietario=cls.user,
            responsavel_edicao=cls.user, criador_registro=cls.user,
            status=Evento.Status.PUBLICADO, publicado_em=now,
        )
        cls.tourism = LocalTuristico.objects.create(
            nome='Parque das Trilhas', slug='parque-das-trilhas-testes',
            descricao_curta='Passeio junto à natureza',
            descricao_completa='Local turístico com trilhas ecológicas.',
            usuario_criador=cls.user, usuario_atualizador=cls.user,
            publicado_por=cls.user, publicado_em=now,
            status=TurismoStatus.PUBLICADO, ativo=True,
        )
        news_category = CategoriaNoticia.objects.create(nome='Cultura Testes')
        cls.article = Artigo.objects.create(
            autor=cls.user, categoria=news_category,
            titulo='Mostra de dança regional', resumo='Agenda cultural',
            conteudo='<p>Notícia sobre artistas e apresentações.</p>',
            status=EditorialStatus.PUBLICADO, publicado_em=now,
        )
        modality = Modalidade.objects.create(nome='Futebol de campo testes')
        organization = OrganizacaoEsportiva.objects.create(
            usuario_responsavel=cls.user, tipo=OrganizacaoEsportiva.Tipo.CLUBE,
            nome='Clube Atlético Testes', cidade='Botucatu', verificado=True,
        )
        cls.championship = Campeonato.objects.create(
            organizacao=organization, modalidade=modality,
            nome='Copa Municipal de Futebol', descricao='Competição esportiva local',
            formato='Pontos corridos', data_inicial=timezone.localdate(),
            status=Campeonato.Status.AGENDADO,
        )
        cls.job = Vaga(
            perfil_pessoa_fisica=cls.user, usuario_criador=cls.user,
            usuario_responsavel=cls.user, titulo='Auxiliar administrativo',
            slug='auxiliar-administrativo-testes',
            descricao='Atendimento e organização de documentos',
            requisitos='Conhecimento de escritório', tipo_contrato='CLT',
            modalidade='PRESENCIAL', cidade='Botucatu', estado='SP',
            status=Vaga.Status.PUBLICADA, publicado_em=now,
        )
        Vaga.objects.bulk_create([cls.job])

    @classmethod
    def company(cls, name, **overrides):
        values = {
            'usuario_proprietario': cls.user, 'nome_fantasia': name,
            'cidade': cls.cidade, 'estado': cls.estado,
            'status': Empresa.Status.ATIVA, 'ativo': True, 'perfil_publico': True,
        }
        values.update(overrides)
        return Empresa.objects.create(**values)

    def search(self, query):
        return GlobalSearchService().search(query)[0]

    def test_partial_case_insensitive_and_accent_insensitive_content(self):
        for query in ('SEGURANÇA', 'segurança', 'seguranca', 'ALIMENTACAO'):
            with self.subTest(query=query):
                self.assertIn(self.category_company.nome_fantasia, [r.title for r in self.search(query)])

    def test_multiple_words_may_match_different_fields(self):
        results = self.search('consultoria restaurantes')
        self.assertIn(self.category_company.nome_fantasia, [result.title for result in results])

    def test_company_relationship_finds_related_service(self):
        services = [r for r in self.search('Consultoria Alimentar') if r.kind == 'servicos']
        self.assertEqual([result.title for result in services], ['Assessoria jurídica'])

    def test_private_content_is_never_returned(self):
        self.assertNotIn(self.private_company.nome_fantasia, [r.title for r in self.search('privada')])

    def test_title_match_ranks_above_description_only(self):
        companies = [r for r in self.search('consultoria alimentar') if r.kind == 'empresas']
        self.assertEqual(companies[0].title, self.category_company.nome_fantasia)
        self.assertGreater(companies[0].score, companies[1].score)

    def test_results_are_unique_after_related_joins(self):
        results = self.search('consultoria')
        identities = [(result.kind, result.url) for result in results]
        self.assertEqual(len(identities), len(set(identities)))

    def test_pagination_preserves_query(self):
        for number in range(25):
            self.company(f'Empresa Paginável {number:02d}')
        response = self.client.get(reverse('global_search'), {'q': 'Empresa Paginável', 'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['query'], 'Empresa Paginável')
        self.assertEqual(response.context['page_obj'].number, 2)
        self.assertContains(response, 'q=Empresa%20Pagin%C3%A1vel')

    def test_domain_alias_returns_existing_public_content(self):
        self.assertEqual(
            len([item for item in self.search('serviços') if item.kind == 'servicos']),
            1,
        )

    def test_domain_alias_and_multiple_words_are_combined(self):
        results = self.search('serviço assessoria jurídica')
        self.assertIn(str(self.service.uuid), [item.object_id for item in results])

    def test_current_yubotuka_video_is_found_by_description_playlist_category_and_tag(self):
        for query in ('música autoral', 'cultura musical', 'som independente'):
            with self.subTest(query=query):
                self.assertIn(
                    str(self.video.uuid),
                    [item.object_id for item in self.search(query) if item.kind == 'videos'],
                )

    def test_type_filter_and_useful_empty_state(self):
        response = self.client.get(reverse('global_search'), {'q': 'consultoria', 'tipo': 'servicos'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(item.kind == 'servicos' for item in response.context['results']))
        empty = self.client.get(reverse('global_search'), {'q': 'termo-inexistente-xyz'})
        self.assertContains(empty, 'Nenhum resultado encontrado para')
        self.assertContains(empty, 'Esportes')

    def test_each_public_domain_is_found(self):
        cases = (
            ('vaga auxiliar administrativo', 'vagas', self.job.uuid),
            ('teatro comunitário', 'eventos', self.event.uuid),
            ('trilhas ecológicas', 'turismo', self.tourism.uuid),
            ('dança regional', 'noticias', self.article.uuid),
            ('esporte futebol', 'esportes', self.championship.uuid),
        )
        for query, kind, object_id in cases:
            with self.subTest(query=query):
                self.assertIn(
                    str(object_id),
                    [item.object_id for item in self.search(query) if item.kind == kind],
                )
