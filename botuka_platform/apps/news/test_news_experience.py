from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.services.public_sharing import gerar_qrcode_png, obter_url_publica
from apps.news.models import (
    Artigo, CategoriaNoticia, ComentarioArtigo, CurtidaComentario,
    EditorialStatus,
)
from apps.news.sanitizers import sanitizar_html_editorial


class RichTextSanitizerTests(SimpleTestCase):
    def test_preserva_formatacao_permitida(self):
        html = (
            "<h2>Título</h2><p><strong>Texto</strong> "
            '<a href="https://botuka.com.br">link</a></p>'
        )
        resultado = sanitizar_html_editorial(html)
        self.assertIn("<h2>Título</h2>", resultado)
        self.assertIn("<strong>Texto</strong>", resultado)

    def test_remove_html_perigoso(self):
        resultado = sanitizar_html_editorial(
            (
                '<script>alert(1)</script>'
                '<p onclick="x()">Seguro</p>'
                '<iframe src="https://x"></iframe>'
            )
        )
        self.assertEqual(resultado, "<p>Seguro</p>")


@override_settings(
    PUBLIC_BASE_URL="https://botuka.com.br",
    SITE_URL="https://botuka.com.br",
)
class NewsExperienceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.autor = user_model.objects.create_user(
            "autor-news", password="senha"
        )
        cls.leitor = user_model.objects.create_user(
            "leitor-news", password="senha"
        )
        cls.outro = user_model.objects.create_user(
            "outro-news", password="senha"
        )
        cls.categoria = CategoriaNoticia.objects.create(nome="Cidade")
        cls.artigo = Artigo.objects.create(
            autor=cls.autor,
            categoria=cls.categoria,
            titulo="Notícia pública",
            conteudo="<h2>Conteúdo</h2><p>Texto publicado.</p>",
            status=EditorialStatus.PUBLICADO,
            publicado_em=timezone.now(),
        )

    def test_pagina_tem_editor_nos_fluxos(self):
        self.client.force_login(self.autor)
        with (
            patch("apps.news.views.pode", return_value=True),
            patch("apps.news.services.pode", return_value=True),
        ):
            nova = self.client.get(
                reverse("painel:news_artigo_novo")
            )
            edicao = self.client.get(
                reverse("painel:news_artigo_editar", args=[self.artigo.uuid])
            )
        self.assertContains(nova, "data-richtext-editor")
        self.assertContains(edicao, "&lt;h2&gt;Conteúdo&lt;/h2&gt;")

    def test_og_e_twitter_usam_url_absoluta(self):
        resposta = self.client.get(self.artigo.get_absolute_url())
        self.assertContains(
            resposta,
            'property="og:image" content="https://botuka.com.br/'
        )
        self.assertContains(
            resposta,
            'name="twitter:image" content="https://botuka.com.br/'
        )

    def test_qrcode_publico_png_svg_e_dominio(self):
        self.assertEqual(
            obter_url_publica(self.artigo),
            f"https://botuka.com.br/noticias/{self.artigo.slug}/"
        )
        self.assertTrue(
            gerar_qrcode_png(self.artigo).startswith(b"\x89PNG")
        )
        self.assertEqual(
            self.client.get(
                reverse("sharing:png", args=["noticia", self.artigo.uuid])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("sharing:svg", args=["noticia", self.artigo.uuid])
            ).status_code,
            200,
        )

    def test_qrcode_bloqueia_noticia_privada(self):
        self.artigo.status = EditorialStatus.RASCUNHO
        self.artigo.save()
        with self.assertRaises(PermissionDenied):
            obter_url_publica(self.artigo)

    def test_usuario_comenta_e_responde_sem_terceiro_nivel(self):
        self.client.force_login(self.leitor)
        self.client.post(
            reverse("news_public:comentario_novo", args=[self.artigo.slug]),
            {"texto": "Comentário"},
        )
        principal = ComentarioArtigo.objects.get(usuario=self.leitor)
        self.client.force_login(self.outro)
        self.client.post(
            reverse("news_public:comentario_responder", args=[principal.uuid]),
            {"texto": "Resposta"},
        )
        resposta = ComentarioArtigo.objects.get(usuario=self.outro)
        self.client.force_login(self.leitor)
        self.client.post(
            reverse("news_public:comentario_responder", args=[resposta.uuid]),
            {"texto": "Nova resposta"},
        )
        nova = ComentarioArtigo.objects.filter(
            usuario=self.leitor
        ).exclude(pk=principal.pk).get()
        self.assertEqual(nova.comentario_raiz, principal)
        self.assertEqual(nova.respondendo_a, resposta)

    def test_visitante_nao_comenta_e_artigo_encerrado_bloqueia(self):
        url = reverse("news_public:comentario_novo", args=[self.artigo.slug])
        self.assertEqual(
            self.client.post(url, {"texto": "Anônimo"}).status_code, 302
        )
        self.artigo.comentarios_encerrados = True
        self.artigo.save()
        self.client.force_login(self.leitor)
        self.assertEqual(
            self.client.post(url, {"texto": "Fechado"}).status_code, 403
        )

    def test_edicao_autoral_exclusao_logica_e_curtida_unica(self):
        comentario = ComentarioArtigo.objects.create(
            artigo=self.artigo, usuario=self.leitor, texto="Original"
        )
        self.client.force_login(self.outro)
        self.assertEqual(
            self.client.post(
                reverse("news_public:comentario_editar", args=[comentario.uuid]),
                {"texto": "Inválido"},
            ).status_code,
            403,
        )
        self.client.force_login(self.leitor)
        self.client.post(
            reverse("news_public:comentario_editar", args=[comentario.uuid]),
            {"texto": "Editado"},
        )
        comentario.refresh_from_db()
        self.assertEqual(comentario.texto, "Editado")
        like_url = reverse(
            "news_public:comentario_curtir", args=[comentario.uuid]
        )
        self.client.post(like_url)
        self.client.post(like_url)
        self.assertEqual(
            CurtidaComentario.objects.filter(
                comentario=comentario, usuario=self.leitor
            ).count(),
            0,
        )
        self.client.post(
            reverse("news_public:comentario_excluir", args=[comentario.uuid])
        )
        self.assertFalse(
            ComentarioArtigo.objects.filter(pk=comentario.pk).exists()
        )
        self.assertTrue(
            ComentarioArtigo.all_objects.filter(
                pk=comentario.pk, excluido_em__isnull=False
            ).exists()
        )

    def test_moderacao_previa_e_texto_invalido(self):
        self.artigo.comentarios_moderados = True
        self.artigo.save()
        self.client.force_login(self.leitor)
        self.client.post(
            reverse("news_public:comentario_novo", args=[self.artigo.slug]),
            {"texto": "Pendente"},
        )
        self.assertEqual(
            ComentarioArtigo.objects.get().status,
            ComentarioArtigo.Status.PENDENTE,
        )
        self.assertEqual(
            self.client.post(
                reverse("news_public:comentario_novo", args=[self.artigo.slug]),
                {"texto": "   "},
            ).status_code,
            302,
        )