import uuid
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import timezone

from apps.core.seo.utils import canonical_url
from apps.core.services.public_sharing import (
    gerar_material_impressao,
    gerar_qrcode_png,
    obter_dados_compartilhamento,
    obter_url_publica,
)
from apps.core.services.public_urls import build_public_absolute_url
from apps.core.templatetags.sharing_tags import public_url
from apps.core.sharing_views import qrcode_png as qrcode_png_view
from apps.news.models import Artigo
from apps.organizations.models import Empresa
from apps.services.models import Servico


class PublicUrlFromRequestTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.objeto = Mock()
        self.objeto.get_absolute_url.return_value = "/noticias/noticia-de-teste/"

    @override_settings(
        ALLOWED_HOSTS=["127.0.0.1"],
        IS_PRODUCTION=False,
        FORCE_SCRIPT_NAME=None,
    )
    def test_preserva_host_protocolo_e_porta_local(self):
        request = self.factory.get(
            "/noticias/noticia-de-teste/",
            HTTP_HOST="127.0.0.1:7700",
        )
        url = obter_url_publica(self.objeto, request)
        self.assertEqual(url, "http://127.0.0.1:7700/noticias/noticia-de-teste/")
        self.assertEqual(canonical_url(request), url)

    def test_helper_trata_caminho_absoluto_relativo_e_request_ausente(self):
        request = self.factory.get("/", HTTP_HOST="127.0.0.1:7700")
        self.assertEqual(
            build_public_absolute_url(request, "empresas/aleicah/"),
            "http://127.0.0.1:7700/empresas/aleicah/",
        )
        self.assertEqual(
            build_public_absolute_url(request, "https://exemplo.test/pagina/"),
            "https://exemplo.test/pagina/",
        )
        self.assertEqual(
            build_public_absolute_url(None, "/empresas/aleicah/"),
            "/empresas/aleicah/",
        )

    def test_template_tag_cobre_string_objeto_e_request_ausente(self):
        request = self.factory.get("/", HTTP_HOST="127.0.0.1:7700")
        objeto = Mock()
        objeto.get_absolute_url.return_value = "/empresas/aleicah/"
        self.assertEqual(
            public_url({"request": request}, objeto),
            "http://127.0.0.1:7700/empresas/aleicah/",
        )
        self.assertEqual(
            public_url({"request": request}, "/servicos/teste/"),
            "http://127.0.0.1:7700/servicos/teste/",
        )
        self.assertEqual(
            public_url({}, objeto),
            "/empresas/aleicah/",
        )

    @override_settings(
        ALLOWED_HOSTS=["botuka.com.br"],
        IS_PRODUCTION=True,
        USE_X_FORWARDED_HOST=True,
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    )
    def test_respeita_host_e_protocolo_encaminhados_em_producao(self):
        request = self.factory.get(
            "/noticias/noticia-de-teste/",
            HTTP_HOST="app-interno:8000",
            HTTP_X_FORWARDED_HOST="botuka.com.br",
            HTTP_X_FORWARDED_PROTO="https",
        )
        url = obter_url_publica(self.objeto, request)
        self.assertEqual(url, "https://botuka.com.br/noticias/noticia-de-teste/")
        self.assertEqual(canonical_url(request), url)


class RegisteredPublicObjectUrlTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.empresa = Empresa(
            uuid=uuid.uuid4(),
            slug="aleicah",
            nome_fantasia="Aleicah",
            status=Empresa.Status.ATIVA,
            perfil_publico=True,
            ativo=True,
        )

    @override_settings(ALLOWED_HOSTS=["127.0.0.1"], IS_PRODUCTION=False)
    def test_empresa_local_preserva_porta_e_todos_consumidores_usam_mesma_url(self):
        request = self.factory.get(
            "/painel/empresas/00000000-0000-0000-0000-000000000000/qrcode/",
            HTTP_HOST="127.0.0.1:7700",
        )
        expected = "http://127.0.0.1:7700/empresas/aleicah/"
        share = obter_dados_compartilhamento(self.empresa, request)
        print_data = gerar_material_impressao(self.empresa, request)
        with patch(
            "apps.core.services.public_sharing.qrcode.QRCode.add_data"
        ) as add_data:
            gerar_qrcode_png(self.empresa, request)
        self.assertEqual(obter_url_publica(self.empresa, request), expected)
        self.assertEqual(share["url"], expected)
        self.assertEqual(print_data["url"], expected)
        add_data.assert_called_once_with(expected)
        self.assertNotIn("/painel/", expected)
        self.assertNotIn(str(self.empresa.uuid), expected)

    @override_settings(
        ALLOWED_HOSTS=["botuka.com.br"],
        IS_PRODUCTION=True,
        USE_X_FORWARDED_HOST=True,
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    )
    def test_empresa_producao_usa_host_e_https_encaminhados(self):
        request = self.factory.get(
            "/painel/empresas/00000000-0000-0000-0000-000000000000/qrcode/",
            HTTP_HOST="app-interno:8000",
            HTTP_X_FORWARDED_HOST="botuka.com.br",
            HTTP_X_FORWARDED_PROTO="https",
        )
        expected = "https://botuka.com.br/empresas/aleicah/"
        with patch(
            "apps.core.services.public_sharing.qrcode.QRCode.add_data"
        ) as add_data:
            gerar_qrcode_png(self.empresa, request)
        self.assertEqual(obter_url_publica(self.empresa, request), expected)
        add_data.assert_called_once_with(expected)
        self.assertNotIn("127.0.0.1", expected)
        self.assertNotIn("localhost", expected)

    @override_settings(ALLOWED_HOSTS=["botuka.com.br"], IS_PRODUCTION=True)
    def test_noticia_e_servico_alinham_url_oficial_e_qrcode(self):
        request = self.factory.get(
            "/noticias/materia/",
            HTTP_HOST="botuka.com.br",
            secure=True,
        )
        artigo = Artigo(
            uuid=uuid.uuid4(),
            slug="materia",
            titulo="Matéria",
            status="PUBLICADO",
            publicado_em=timezone.now(),
            ativo=True,
            atualizado_em=timezone.now(),
        )
        servico = Servico(
            uuid=uuid.uuid4(),
            slug="consultoria",
            titulo="Consultoria",
            status=Servico.Status.PUBLICADO,
            publicado_em=timezone.now(),
            ativo=True,
            atualizado_em=timezone.now(),
        )
        self.assertEqual(
            obter_dados_compartilhamento(artigo, request)["url"],
            "https://botuka.com.br/noticias/materia/",
        )
        self.assertEqual(
            gerar_material_impressao(artigo, request)["url"],
            "https://botuka.com.br/noticias/materia/",
        )
        self.assertEqual(
            obter_dados_compartilhamento(servico, request)["url"],
            "https://botuka.com.br/servicos/consultoria/",
        )

    def test_endpoint_qrcode_nao_permite_cache_de_url_de_outro_host(self):
        request = self.factory.get("/qrcode/empresa/teste.png")
        with (
            patch(
                "apps.core.sharing_views.obter_objeto_publico",
                return_value=self.empresa,
            ),
            patch(
                "apps.core.sharing_views.gerar_qrcode_png",
                return_value=b"png",
            ),
        ):
            response = qrcode_png_view(request, "empresa", self.empresa.uuid)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertIn("Host", response["Vary"])
