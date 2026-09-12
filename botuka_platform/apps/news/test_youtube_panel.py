from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.domain import EditorialStatus
from apps.core.models import Perfil, PerfilPermissao, Permissao
from apps.news.models import Artigo, ArtigoBloco, CategoriaNoticia


class NewsYoutubePanelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "youtube-news-author",
            password="x",
        )
        self.categoria = CategoriaNoticia.objects.create(nome="Cidade YouTube")

        perfil = Perfil.objects.create(nome="NEWS-YOUTUBE-TEST")
        self.user.perfil = perfil
        self.user.save(update_fields=["perfil"])

        for codigo in (
            "news.criar_artigo",
            "news.editar_artigo_proprio",
        ):
            permissao = Permissao.all_objects.get(codigo=codigo)
            PerfilPermissao.objects.get_or_create(
                perfil=perfil,
                permissao=permissao,
            )

        self.client.force_login(self.user)

    def dados_novo_artigo(
        self,
        titulo="Artigo com video",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    ):
        return {
            "categoria": self.categoria.pk,
            "titulo": titulo,
            "conteudo": "<p>Texto seguro</p>",
            "tipo_editorial": "NOTICIA",
            "videos-TOTAL_FORMS": "1",
            "videos-INITIAL_FORMS": "0",
            "videos-MIN_NUM_FORMS": "0",
            "videos-MAX_NUM_FORMS": "1000",
            "videos-0-titulo": "Video teste",
            "videos-0-url": url,
            "videos-0-ordem": "1",
        }

    def dados_edicao_video(self, artigo, bloco, **overrides):
        dados = {
            "categoria": self.categoria.pk,
            "titulo": artigo.titulo,
            "conteudo": artigo.conteudo,
            "tipo_editorial": artigo.tipo_editorial,
            "videos-TOTAL_FORMS": "1",
            "videos-INITIAL_FORMS": "1",
            "videos-MIN_NUM_FORMS": "0",
            "videos-MAX_NUM_FORMS": "1000",
            "videos-0-id": str(bloco.pk),
            "videos-0-titulo": bloco.titulo,
            "videos-0-url": bloco.url,
            "videos-0-ordem": str(bloco.ordem),
        }
        dados.update(overrides)
        return dados

    def test_video_youtube_criado_pelo_painel(self):
        response = self.client.post(
            reverse("painel:news_artigo_novo"),
            self.dados_novo_artigo(),
        )

        self.assertEqual(response.status_code, 302)

        artigo = Artigo.objects.get(titulo="Artigo com video")
        bloco = artigo.blocos.get(tipo=ArtigoBloco.Tipo.VIDEO)

        self.assertEqual(bloco.titulo, "Video teste")
        self.assertEqual(bloco.identificador_externo, "dQw4w9WgXcQ")
        self.assertEqual(bloco.ordem, 1)

    def test_url_youtube_invalida_nao_cria_artigo(self):
        response = self.client.post(
            reverse("painel:news_artigo_novo"),
            self.dados_novo_artigo(
                titulo="Artigo invalido",
                url="https://example.com/video",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Artigo.objects.filter(titulo="Artigo invalido").exists()
        )

    def test_youtube_short_link_aceito(self):
        response = self.client.post(
            reverse("painel:news_artigo_novo"),
            self.dados_novo_artigo(
                titulo="Artigo short",
                url="https://youtu.be/dQw4w9WgXcQ",
            ),
        )

        self.assertEqual(response.status_code, 302)

        bloco = Artigo.objects.get(
            titulo="Artigo short"
        ).blocos.get(tipo=ArtigoBloco.Tipo.VIDEO)

        self.assertEqual(
            bloco.identificador_externo,
            "dQw4w9WgXcQ",
        )

    def test_youtube_shorts_aceito(self):
        response = self.client.post(
            reverse("painel:news_artigo_novo"),
            self.dados_novo_artigo(
                titulo="Artigo shorts",
                url="https://www.youtube.com/shorts/dQw4w9WgXcQ",
            ),
        )

        self.assertEqual(response.status_code, 302)

        bloco = Artigo.objects.get(
            titulo="Artigo shorts"
        ).blocos.get(tipo=ArtigoBloco.Tipo.VIDEO)

        self.assertEqual(
            bloco.identificador_externo,
            "dQw4w9WgXcQ",
        )

    def test_youtube_embed_aceito(self):
        response = self.client.post(
            reverse("painel:news_artigo_novo"),
            self.dados_novo_artigo(
                titulo="Artigo embed",
                url="https://www.youtube.com/embed/dQw4w9WgXcQ",
            ),
        )

        self.assertEqual(response.status_code, 302)

        bloco = Artigo.objects.get(
            titulo="Artigo embed"
        ).blocos.get(tipo=ArtigoBloco.Tipo.VIDEO)

        self.assertEqual(
            bloco.identificador_externo,
            "dQw4w9WgXcQ",
        )

    def test_video_renderizado_publicamente_com_nocookie(self):
        artigo = Artigo.objects.create(
            autor=self.user,
            categoria=self.categoria,
            titulo="Artigo publico com video",
            conteudo="<p>Texto seguro</p>",
            status=EditorialStatus.PUBLICADO,
            publicado_em=timezone.now(),
        )

        ArtigoBloco.objects.create(
            artigo=artigo,
            tipo=ArtigoBloco.Tipo.VIDEO,
            titulo="Video publico",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            ordem=1,
        )

        response = self.client.get(
            reverse("news_public:artigo", args=[artigo.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        )

    def test_video_editado_pelo_painel(self):
        artigo = Artigo.objects.create(
            autor=self.user,
            categoria=self.categoria,
            titulo="Artigo para editar video",
            conteudo="<p>Texto seguro</p>",
        )

        bloco = ArtigoBloco.objects.create(
            artigo=artigo,
            tipo=ArtigoBloco.Tipo.VIDEO,
            titulo="Titulo antigo",
            url="https://youtu.be/dQw4w9WgXcQ",
            ordem=1,
        )

        response = self.client.post(
            reverse("painel:news_artigo_editar", args=[artigo.uuid]),
            self.dados_edicao_video(
                artigo,
                bloco,
                **{
                    "videos-0-titulo": "Titulo novo",
                    "videos-0-url":
                        "https://www.youtube.com/watch?v=9bZkp7q19f0",
                    "videos-0-ordem": "7",
                },
            ),
        )

        self.assertEqual(response.status_code, 302)

        bloco.refresh_from_db()

        self.assertEqual(bloco.titulo, "Titulo novo")
        self.assertEqual(
            bloco.identificador_externo,
            "9bZkp7q19f0",
        )
        self.assertEqual(bloco.ordem, 7)

    def test_video_removido_com_soft_delete(self):
        artigo = Artigo.objects.create(
            autor=self.user,
            categoria=self.categoria,
            titulo="Artigo para remover video",
            conteudo="<p>Texto seguro</p>",
        )

        bloco = ArtigoBloco.objects.create(
            artigo=artigo,
            tipo=ArtigoBloco.Tipo.VIDEO,
            titulo="Video removivel",
            url="https://youtu.be/dQw4w9WgXcQ",
            ordem=1,
        )

        response = self.client.post(
            reverse("painel:news_artigo_editar", args=[artigo.uuid]),
            self.dados_edicao_video(
                artigo,
                bloco,
                **{"videos-0-DELETE": "on"},
            ),
        )

        self.assertEqual(response.status_code, 302)

        self.assertFalse(
            ArtigoBloco.objects.filter(pk=bloco.pk).exists()
        )

        bloco_excluido = ArtigoBloco.all_objects.get(pk=bloco.pk)

        self.assertFalse(bloco_excluido.ativo)
        self.assertIsNotNone(bloco_excluido.excluido_em)
