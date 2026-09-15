from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gestao.central_views import CONTENT_KINDS, _WORKFLOW_ROUTES, _models
from apps.news.models import Artigo, CategoriaNoticia, EditorialStatus


class ContentManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.master = User.objects.create_superuser('content-master', password='x')
        cls.outsider = User.objects.create_user('content-outsider', password='x')
        cls.category = CategoriaNoticia.objects.create(nome='Cidade')
        cls.article = Artigo.objects.create(
            autor=cls.master, categoria=cls.category, titulo='Notícia local',
            conteudo='<p>Conteúdo editorial real.</p>',
            status=EditorialStatus.RASCUNHO,
        )

    def test_real_editorial_domains_are_available_read_only(self):
        expected = {
            'artigos', 'categorias-noticias', 'eventos', 'videos', 'episodios',
            'transmissoes', 'turismo', 'roteiros-turisticos',
            'experiencias-turisticas', 'orgaos-publicos', 'acoes-publicas',
        }
        self.assertEqual(set(CONTENT_KINDS), expected)
        self.assertTrue(expected.issubset(_models()))
        self.client.force_login(self.master)
        for kind in CONTENT_KINDS:
            response = self.client.get(reverse('gestao:central_lista', args=[kind]))
            self.assertEqual(response.status_code, 200, kind)
            self.assertTrue(response.context['read_only'], kind)

    def test_workflow_links_are_real_and_central_has_no_mutation_action(self):
        self.client.force_login(self.master)
        for kind, (route, args, _capability) in _WORKFLOW_ROUTES.items():
            response = self.client.get(reverse('gestao:central_lista', args=[kind]))
            self.assertContains(response, reverse(route, args=args))
            self.assertNotContains(response, 'central_status')
            self.assertNotContains(response, 'central_excluir')

    def test_master_permission_search_status_detail_and_heavy_body_absent(self):
        url = reverse('gestao:central_lista', args=['artigos'])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.master)
        response = self.client.get(url, {'q': 'Cidade', 'status': EditorialStatus.RASCUNHO})
        self.assertContains(response, self.article.titulo)
        self.assertNotContains(response, 'Conteúdo editorial real')
        detail = self.client.get(reverse('gestao:central_detalhe', args=['artigos', self.article.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self.category.nome)

    def test_article_listing_queries_do_not_grow_per_row(self):
        self.client.force_login(self.master)
        url = reverse('gestao:central_lista', args=['artigos'])
        with CaptureQueriesContext(connection) as first:
            self.client.get(url)
        Artigo.objects.bulk_create([
            Artigo(
                autor=self.master, categoria=self.category, titulo=f'Artigo {index}',
                slug=f'artigo-{index}', conteudo='<p>Texto</p>',
            ) for index in range(6)
        ])
        with CaptureQueriesContext(connection) as many:
            self.client.get(url)
        self.assertLessEqual(len(many), len(first) + 1)
