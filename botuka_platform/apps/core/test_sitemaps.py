from django.test import SimpleTestCase
from django.urls import reverse

from apps.core.seo.sitemaps import ArtigoSitemap, EmpresaSitemap, ServicoSitemap, StaticSitemap, VagaSitemap


class SitemapAndRobotsTests(SimpleTestCase):
    def test_robots_blocks_private_areas_and_declares_sitemap(self):
        response = self.client.get(reverse('robots_txt'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Disallow: /painel/')
        self.assertContains(response, 'Disallow: /admin/')
        self.assertContains(response, 'Sitemap:')

    def test_static_sitemap_has_only_public_routes(self):
        locations = [StaticSitemap().location(item) for item in StaticSitemap().items()]
        self.assertIn('/', locations)
        self.assertFalse(any(path.startswith(('/painel/', '/conta/', '/gestao/', '/admin/')) for path in locations))

    def test_dynamic_sitemaps_filter_publication_state(self):
        queries = {
            'empresa': str(EmpresaSitemap().items().query).lower(),
            'servico': str(ServicoSitemap().items().query).lower(),
            'vaga': str(VagaSitemap().items().query).lower(),
        }
        self.assertIn('perfil_publico', queries['empresa'])
        self.assertIn('publicado', queries['servico'])
        self.assertIn('publicada', queries['vaga'])
