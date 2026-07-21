import json
import re
from types import SimpleNamespace
from unittest.mock import patch

from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from apps.core.seo.page_builders import artigo_seo, empresa_seo, home_seo, vaga_seo


class SeoMetadataTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def _home(self):
        with patch('apps.core.views.montar_contexto_home', return_value={}):
            return self.client.get('/', HTTP_HOST='127.0.0.1:7700')

    def test_home_has_unique_core_metadata_and_valid_json_ld(self):
        response = self._home()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<title>BOTUKA — Empresas, serviços, eventos e notícias de Botucatu</title>', html=True)
        self.assertContains(response, 'rel="canonical"')
        self.assertContains(response, 'property="og:image"')
        self.assertContains(response, 'name="twitter:card" content="summary_large_image"')
        self.assertContains(response, 'botuka-default-1200x630.png')
        scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>', response.content.decode(), re.S)
        self.assertEqual(len(scripts), 1)
        payload = json.loads(scripts[0])
        self.assertEqual(payload['@context'], 'https://schema.org')
        self.assertIn('Organization', [item['@type'] for item in payload['@graph']])

    def test_private_panel_is_noindex_and_not_in_static_sitemap(self):
        from apps.core.seo.sitemaps import StaticSitemap
        self.assertFalse(any('/painel/' in reverse(route) for route in StaticSitemap.routes))
        request = RequestFactory().get('/painel/')
        from apps.core.seo.context import seo_context
        self.assertEqual(seo_context(request)['seo_default']['robots'], 'noindex,nofollow')

    @override_settings(IS_PRODUCTION=True, SITE_URL='https://botuka.com.br')
    def test_production_urls_are_https(self):
        seo = home_seo(RequestFactory().get('/', HTTP_HOST='botuka.com.br'))
        self.assertTrue(seo['canonical_url'].startswith('https://'))
        self.assertTrue(seo['image_url'].startswith('https://'))

    def test_specific_schema_builders_do_not_expose_sensitive_fields(self):
        request = RequestFactory().get('/empresas/exemplo/')
        image = SimpleNamespace(url='/media/company.png', __bool__=lambda self: True)
        empresa = SimpleNamespace(nome_fantasia='Empresa Exemplo', cidade='Botucatu', descricao_curta='Descrição pública.', descricao_completa='', imagem_capa=image, logo=None, atualizado_em=None)
        seo = empresa_seo(request, empresa)
        serialized = json.dumps(seo['schema'])
        self.assertIn('LocalBusiness', serialized)
        self.assertNotIn('cpf', serialized.lower())
        self.assertNotIn('email', serialized.lower())


class IntegrationConsentTests(SimpleTestCase):
    @override_settings(ENABLE_ANALYTICS=False, GOOGLE_TAG_MANAGER_ID='GTM-ABC123')
    def test_gtm_disabled_by_default(self):
        with patch('apps.core.views.montar_contexto_home', return_value={}):
            response = self.client.get('/')
        self.assertNotContains(response, 'googletagmanager.com/gtm.js')

    @override_settings(ENABLE_ANALYTICS=True, GOOGLE_TAG_MANAGER_ID='GTM-ABC123')
    def test_gtm_requires_explicit_analytics_consent(self):
        self.client.cookies['botuka_consent'] = json.dumps({'analytics': True, 'marketing': False})
        with patch('apps.core.views.montar_contexto_home', return_value={}):
            response = self.client.get('/')
        self.assertContains(response, 'googletagmanager.com/gtm.js')
        self.assertNotContains(response, 'connect.facebook.net')

    def test_data_layer_helper_has_field_allowlist(self):
        with patch('apps.core.views.montar_contexto_home', return_value={}):
            response = self.client.get('/')
        body = response.content.decode()
        helper = body.split('</head>', 1)[0]
        self.assertIn('content_type', helper)
        self.assertNotIn('cpf_cnpj', helper)
        self.assertNotIn('password', helper.lower())
