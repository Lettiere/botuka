import json
import re
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from apps.core.seo.page_builders import artigo_seo, empresa_seo, home_seo, media_seo, servico_seo, tourism_seo, vaga_seo
from apps.core.seo.utils import clean_text, image_metadata, resolve_social_image, youtube_thumbnail, youtube_video_id


@override_settings(ALLOWED_HOSTS=['127.0.0.1', 'localhost', 'botuka.com.br'])
class SeoMetadataTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def _home(self):
        request = RequestFactory().get('/', HTTP_HOST='127.0.0.1:7700')
        seo = home_seo(request)
        context = {
            'seo': seo,
            'seo_default': seo,
            'seo_config': {},
        }
        return HttpResponse(
            render_to_string('seo/meta.html', context)
            + render_to_string('seo/json_ld.html', context)
        )

    def test_home_has_unique_core_metadata_and_valid_json_ld(self):
        response = self._home()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<title>BOTUKA — Empresas, serviços, eventos e notícias de Botucatu</title>', html=True)
        self.assertContains(response, 'rel="canonical"')
        self.assertContains(response, 'property="og:image"')
        self.assertContains(response, 'name="twitter:card" content="summary_large_image"')
        self.assertContains(response, 'property="og:image:secure_url"')
        self.assertContains(response, 'name="twitter:image"')
        self.assertContains(response, 'property="og:image:width" content="1200"')
        self.assertContains(response, 'property="og:image:height" content="630"')
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

    def test_description_is_sanitized_and_does_not_cut_words(self):
        value = clean_text('<p>Uma descrição com   espaços e conteúdo relevante.</p>', 28)
        self.assertNotIn('<p>', value)
        self.assertNotIn('  ', value)
        self.assertEqual(value, 'Uma descrição com espaços e…')

    def test_youtube_id_and_thumbnail_supported_formats(self):
        expected = 'AbC_123-xYz'
        urls = [
            f'https://www.youtube.com/watch?v={expected}',
            f'https://youtu.be/{expected}',
            f'https://www.youtube.com/embed/{expected}',
            f'https://www.youtube.com/shorts/{expected}',
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(youtube_video_id(url), expected)
                self.assertEqual(youtube_thumbnail(url), f'https://img.youtube.com/vi/{expected}/maxresdefault.jpg')

    def test_missing_image_file_falls_back_without_error(self):
        class BrokenImage:
            name = 'missing.jpg'
            @property
            def url(self):
                raise ValueError('missing')
        broken = BrokenImage()
        url, image_type, width, height = image_metadata(RequestFactory().get('/'), broken)
        self.assertTrue(url.endswith('botuka-default-1200x630.png'))
        self.assertEqual((image_type, width, height), ('image/png', 1200, 630))

    @override_settings(IS_PRODUCTION=True, SITE_URL='https://botuka.com.br')
    def test_social_image_resolver_accepts_existing_local_file(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = FileSystemStorage(location=directory, base_url='/media/')
            storage.save('social/card.png', ContentFile(b'image'))
            image = SimpleNamespace(
                name='social/card.png', storage=storage,
                url='/media/social/card.png', width=1200, height=630,
            )
            result = resolve_social_image(
                RequestFactory().get('/', HTTP_HOST='botuka.com.br'), image,
            )
        self.assertEqual(
            result,
            ('https://botuka.com.br/media/social/card.png', 'image/png', 1200, 630),
        )

    @override_settings(IS_PRODUCTION=True, SITE_URL='https://botuka.com.br')
    def test_social_image_resolver_rejects_missing_storage_file(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = FileSystemStorage(location=directory, base_url='/media/')
            missing = SimpleNamespace(
                name='social/missing.jpg', storage=storage,
                url='/media/social/missing.jpg', width=1200, height=630,
            )
            result = resolve_social_image(
                RequestFactory().get('/', HTTP_HOST='botuka.com.br'), missing,
            )
        self.assertEqual(result[0], 'https://botuka.com.br/static/img/seo/botuka-default-1200x630.png')
        self.assertEqual(result[1:], ('image/png', 1200, 630))

    def test_video_uses_registered_thumbnail_and_video_metadata(self):
        obj = SimpleNamespace(
            titulo='Vídeo exemplo', descricao_curta='Descrição real.',
            thumbnail='https://cdn.example.com/thumb.jpg', video_id='AbC_123-xYz',
            youtube_url='https://youtu.be/AbC_123-xYz',
            embed_url='https://www.youtube-nocookie.com/embed/AbC_123-xYz',
            publicado_em=None, atualizado_em=None, duracao=None,
        )
        seo = media_seo(RequestFactory().get('/yob/um/', HTTP_HOST='botuka.com.br'), obj, kind='video')
        self.assertEqual(seo['content_type'], 'video.other')
        self.assertEqual(seo['image_url'], obj.thumbnail)
        self.assertEqual(seo['video_url'], obj.embed_url)

    def test_video_uses_youtube_thumbnail_fallback(self):
        obj = SimpleNamespace(
            titulo='Sem thumbnail', descricao='Descrição real.', thumbnail='',
            video_id='AbC_123-xYz', youtube_url='https://youtu.be/AbC_123-xYz',
            embed_url='https://www.youtube-nocookie.com/embed/AbC_123-xYz',
            publicado_em=None, atualizado_em=None, duracao=None,
        )
        seo = media_seo(RequestFactory().get('/yob/dois/', HTTP_HOST='botuka.com.br'), obj, kind='video')
        self.assertIn('/AbC_123-xYz/maxresdefault.jpg', seo['image_url'])

    def test_home_has_no_duplicate_primary_tags(self):
        body = self._home().content.decode()
        for marker in ('<title>', 'name="description"', 'property="og:title"', 'rel="canonical"', 'name="twitter:card"'):
            self.assertEqual(body.count(marker), 1, marker)

    def test_article_uses_first_related_image_when_cover_is_empty(self):
        class Related:
            def filter(self, **kwargs): return self
            def order_by(self, *args): return self
            def first(self): return SimpleNamespace(arquivo='', url_externa='https://cdn.example.com/article.jpg')
            def all(self): return []
            def __iter__(self): return iter([self.first()])
        artigo = SimpleNamespace(
            titulo='Notícia real', titulo_seo='', descricao_seo='', resumo='Resumo real',
            subtitulo='', conteudo='Conteúdo real', imagem_social='', imagem_capa='',
            texto_alternativo_imagem='',
            imagens=Related(), autor_editorial_id=None,
            autor=SimpleNamespace(get_full_name=lambda: 'Redação'),
            categoria=SimpleNamespace(nome='Cidade', slug='cidade'), tipo_editorial='NOTICIA',
            publicado_em=None, atualizado_em=None, tags=Related(),
        )
        seo = artigo_seo(RequestFactory().get('/noticias/noticia-real/'), artigo)
        self.assertEqual(seo['image_url'], 'https://cdn.example.com/article.jpg')
        self.assertIn('NewsArticle', json.dumps(seo['schema']))

    def test_article_prioritizes_social_image(self):
        class Related:
            def filter(self, **kwargs): return self
            def order_by(self, *args): return self
            def __iter__(self): return iter([])
            def all(self): return []
        artigo = SimpleNamespace(
            titulo='Notícia social', titulo_seo='', descricao_seo='', resumo='Resumo',
            subtitulo='', conteudo='Conteúdo',
            imagem_social='https://cdn.example.com/social-1200x630.jpg',
            imagem_capa='https://cdn.example.com/capa.jpg', texto_alternativo_imagem='',
            imagens=Related(), autor_editorial_id=None,
            autor=SimpleNamespace(get_full_name=lambda: 'Redação'),
            categoria=SimpleNamespace(nome='Cidade', slug='cidade'), tipo_editorial='NOTICIA',
            publicado_em=None, atualizado_em=None, tags=Related(),
        )
        seo = artigo_seo(RequestFactory().get('/noticias/social/'), artigo)
        self.assertEqual(seo['image_url'], artigo.imagem_social)

    def test_service_uses_principal_image(self):
        class Images:
            def all(self):
                return [SimpleNamespace(principal=False, imagem='https://cdn.example.com/other.jpg'),
                        SimpleNamespace(principal=True, imagem='https://cdn.example.com/main.jpg')]
        servico = SimpleNamespace(
            titulo='Serviço real', descricao_curta='Descrição real', descricao_completa='',
            imagens=Images(), empresa_id=None, empresa=None, tipo_servico='Manutenção',
            publicado_em=None, atualizado_em=None,
        )
        seo = servico_seo(RequestFactory().get('/servicos/real/'), servico)
        self.assertEqual(seo['image_url'], 'https://cdn.example.com/main.jpg')
        self.assertIn('Service', json.dumps(seo['schema']))

    def test_tourism_uses_main_image_and_valid_schema(self):
        local = SimpleNamespace(
            nome='Parque real', descricao_curta='Descrição do parque.',
            imagem_principal='https://cdn.example.com/park.jpg',
            capa='', fotos=SimpleNamespace(all=lambda: []), categoria=None,
            imagem_texto_alternativo='Vista do parque', telefone_publico='',
            logradouro='Rua Um', numero='10', cidade='Botucatu', estado='SP', cep='',
            visibilidade_localizacao='PUBLICA', latitude=-22.8, longitude=-48.4,
            publicado_em=None, atualizado_em=None,
        )
        seo = tourism_seo(RequestFactory().get('/turismo/local/parque/'), local)
        self.assertEqual(seo['image_url'], 'https://cdn.example.com/park.jpg')
        self.assertIn('TouristAttraction', json.dumps(seo['schema']))


class IntegrationConsentTests(SimpleTestCase):
    databases = {'default'}

    def test_banner_exibe_texto_lgpd_e_controles_de_escolha(self):
        with patch('apps.core.views.montar_contexto_home', return_value={}):
            response = self.client.get('/')
        self.assertContains(response, 'Lei Geral de Proteção de Dados (LGPD)')
        self.assertContains(response, 'data-consent="essential"')
        self.assertContains(response, 'data-consent="all"')

    @override_settings(ENABLE_ANALYTICS=False, GOOGLE_TAG_MANAGER_ID='GTM-ABC123')
    def test_gtm_disabled_by_default(self):
        with patch('apps.core.views.montar_contexto_home', return_value={}):
            response = self.client.get('/')
        self.assertNotContains(response, 'googletagmanager.com/gtm.js')

    @override_settings(ENABLE_ANALYTICS=True, GOOGLE_TAG_MANAGER_ID='GTM-ABC123')
    def test_gtm_requires_explicit_analytics_consent(self):
        self.client.cookies['botuka_consent'] = json.dumps({
            'analytics': True,
            'marketing': False,
            'version': settings.CONSENT_POLICY_VERSION,
            'expiresAt': (time.time() + 3600) * 1000,
        })
        with patch('apps.core.views.montar_contexto_home', return_value={}):
            response = self.client.get('/')
        self.assertContains(response, 'googletagmanager.com/gtm.js')
        self.assertNotContains(response, 'connect.facebook.net')

    @override_settings(ENABLE_ANALYTICS=True, GOOGLE_TAG_MANAGER_ID='GTM-ABC123')
    def test_consentimento_de_politica_antiga_nao_libera_analytics(self):
        self.client.cookies['botuka_consent'] = json.dumps({
            'analytics': True, 'marketing': True, 'version': 'politica-antiga',
        })
        with patch('apps.core.views.montar_contexto_home', return_value={}):
            response = self.client.get('/')
        self.assertNotContains(response, 'googletagmanager.com/gtm.js')

    def test_data_layer_helper_has_field_allowlist(self):
        with patch('apps.core.views.montar_contexto_home', return_value={}):
            response = self.client.get('/')
        body = response.content.decode()
        helper = body.split('</head>', 1)[0]
        self.assertIn('content_type', helper)
        self.assertNotIn('cpf_cnpj', helper)
        self.assertNotIn('password', helper.lower())
