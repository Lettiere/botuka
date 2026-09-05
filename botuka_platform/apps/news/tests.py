from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from apps.core.domain import EditorialStatus
from apps.core.models import Perfil,Permissao,PerfilPermissao
from apps.news.models import CategoriaNoticia,Artigo,ArtigoBloco

class NewsTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('reporter',password='x');p=Perfil.objects.create(nome='NEWS_REPORTER');self.user.perfil=p;self.user.save();perm=Permissao.all_objects.get(codigo='news.criar');PerfilPermissao.objects.create(perfil=p,permissao=perm);perm_edit=Permissao.all_objects.get(codigo='news.editar_artigo_proprio');PerfilPermissao.objects.create(perfil=p,permissao=perm_edit);self.cat=CategoriaNoticia.objects.create(nome='Cidade')
    def test_categoria_criminal_rejeitada(self):
        with self.assertRaises(ValidationError):CategoriaNoticia.objects.create(nome='Noticiário policial')
    def test_artigo_privado_e_publicado(self):
        a=Artigo.objects.create(autor=self.user,categoria=self.cat,titulo='Cidade em pauta',conteudo='Texto seguro')
        self.assertEqual(self.client.get(reverse('news_public:artigo',args=[a.slug])).status_code,404);a.status=EditorialStatus.PUBLICADO;a.save();response=self.client.get(reverse('news_public:artigo',args=[a.slug]));self.assertEqual(response.status_code,200)
        self.assertTemplateUsed(response,'publico/news/artigo.html')
        self.assertContains(response,'article-detail-page')
        self.assertContains(response,'data-reading-progress')
        self.assertContains(response,'data-copy-link')
        self.assertContains(response,'/static/news/css/artigo-detalhe.css')
        self.assertContains(response,'/static/news/js/artigo-detalhe.js')
        self.assertContains(response,'NewsArticle')
        self.assertEqual(response.context['tempo_leitura'],1)
    def test_bloco_inseguro_rejeitado(self):
        a=Artigo.objects.create(autor=self.user,categoria=self.cat,titulo='Teste',conteudo='Seguro')
        with self.assertRaises(ValidationError):ArtigoBloco.objects.create(artigo=a,tipo=ArtigoBloco.Tipo.TEXTO,conteudo='<script>alert(1)</script>')
    def test_reporter_nao_publica_pelo_painel(self):
        self.client.force_login(self.user);dados={'categoria':self.cat.pk,'titulo':'Sem publicação direta','conteudo':'Texto','status':EditorialStatus.PUBLICADO,'ativo':'on'};r=self.client.post(reverse('painel:news_artigo_novo'),dados);self.assertEqual(r.status_code,200);self.assertFalse(Artigo.objects.filter(titulo='Sem publicação direta').exists())

    def _dados_artigo_com_video(self, titulo="Artigo com video", url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"):
        return {
            "categoria": self.cat.pk,
            "titulo": titulo,
            "conteudo": "Texto seguro",
            "tipo_editorial": "NOTICIA",
            "videos-TOTAL_FORMS": "1",
            "videos-INITIAL_FORMS": "0",
            "videos-MIN_NUM_FORMS": "0",
            "videos-MAX_NUM_FORMS": "1000",
            "videos-0-titulo": "Video teste",
            "videos-0-url": url,
            "videos-0-ordem": "1",
        }

    def test_video_youtube_criado_pelo_painel(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel:news_artigo_novo"),
            self._dados_artigo_com_video(),
        )

        self.assertEqual(response.status_code, 302)

        artigo = Artigo.objects.get(titulo="Artigo com video")
        bloco = artigo.blocos.get(tipo=ArtigoBloco.Tipo.VIDEO)

        self.assertEqual(bloco.titulo, "Video teste")
        self.assertEqual(bloco.identificador_externo, "dQw4w9WgXcQ")
        self.assertEqual(bloco.ordem, 1)

    def test_video_youtube_url_invalida_nao_cria_artigo(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel:news_artigo_novo"),
            self._dados_artigo_com_video(
                titulo="Artigo invalido",
                url="https://example.com/video",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Artigo.objects.filter(titulo="Artigo invalido").exists()
        )

    def test_video_youtube_short_link(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel:news_artigo_novo"),
            self._dados_artigo_com_video(
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

    def test_video_youtube_renderizado_publicamente(self):
        artigo = Artigo.objects.create(
            autor=self.user,
            categoria=self.cat,
            titulo="Artigo publico com video",
            conteudo="Texto seguro",
            status=EditorialStatus.PUBLICADO,
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

    def test_bloco_nao_video_permanece_intacto(self):
        artigo = Artigo.objects.create(
            autor=self.user,
            categoria=self.cat,
            titulo="Artigo misto",
            conteudo="Texto seguro",
        )

        bloco_texto = ArtigoBloco.objects.create(
            artigo=artigo,
            tipo=ArtigoBloco.Tipo.TEXTO,
            conteudo="Bloco de texto preservado",
            ordem=1,
        )

        ArtigoBloco.objects.create(
            artigo=artigo,
            tipo=ArtigoBloco.Tipo.VIDEO,
            titulo="Video existente",
            url="https://youtu.be/dQw4w9WgXcQ",
            ordem=2,
        )

        self.client.force_login(self.user)

        dados = {
            "categoria": self.cat.pk,
            "titulo": artigo.titulo,
            "conteudo": artigo.conteudo,
            "tipo_editorial": "NOTICIA",
            "videos-TOTAL_FORMS": "0",
            "videos-INITIAL_FORMS": "0",
            "videos-MIN_NUM_FORMS": "0",
            "videos-MAX_NUM_FORMS": "1000",
        }

        response = self.client.post(
            reverse("painel:news_artigo_editar", args=[artigo.uuid]),
            dados,
        )

        self.assertEqual(response.status_code, 302)

        bloco_texto.refresh_from_db()
        self.assertEqual(
            bloco_texto.conteudo,
            "Bloco de texto preservado",
        )

    def _dados_edicao_video(self, artigo, bloco, **overrides):
        dados = {
            "categoria": self.cat.pk,
            "titulo": artigo.titulo,
            "conteudo": artigo.conteudo,
            "tipo_editorial": "NOTICIA",
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

    def test_video_youtube_shorts_aceito(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel:news_artigo_novo"),
            self._dados_artigo_com_video(
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

    def test_video_youtube_embed_aceito(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel:news_artigo_novo"),
            self._dados_artigo_com_video(
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

    def test_video_youtube_editado_pelo_painel(self):
        artigo = Artigo.objects.create(
            autor=self.user,
            categoria=self.cat,
            titulo="Artigo para editar video",
            conteudo="Texto seguro",
        )

        bloco = ArtigoBloco.objects.create(
            artigo=artigo,
            tipo=ArtigoBloco.Tipo.VIDEO,
            titulo="Titulo antigo",
            url="https://youtu.be/dQw4w9WgXcQ",
            ordem=1,
        )

        self.client.force_login(self.user)

        dados = self._dados_edicao_video(
            artigo,
            bloco,
            **{
                "videos-0-titulo": "Titulo novo",
                "videos-0-url": "https://www.youtube.com/watch?v=9bZkp7q19f0",
                "videos-0-ordem": "7",
            }
        )

        response = self.client.post(
            reverse("painel:news_artigo_editar", args=[artigo.uuid]),
            dados,
        )

        self.assertEqual(response.status_code, 302)

        bloco.refresh_from_db()

        self.assertEqual(bloco.titulo, "Titulo novo")
        self.assertEqual(bloco.identificador_externo, "9bZkp7q19f0")
        self.assertEqual(bloco.ordem, 7)

    def test_video_youtube_removido_com_soft_delete(self):
        artigo = Artigo.objects.create(
            autor=self.user,
            categoria=self.cat,
            titulo="Artigo para remover video",
            conteudo="Texto seguro",
        )

        bloco = ArtigoBloco.objects.create(
            artigo=artigo,
            tipo=ArtigoBloco.Tipo.VIDEO,
            titulo="Video removivel",
            url="https://youtu.be/dQw4w9WgXcQ",
            ordem=1,
        )

        self.client.force_login(self.user)

        dados = self._dados_edicao_video(
            artigo,
            bloco,
            **{"videos-0-DELETE": "on"}
        )

        response = self.client.post(
            reverse("painel:news_artigo_editar", args=[artigo.uuid]),
            dados,
        )

        self.assertEqual(response.status_code, 302)

        self.assertFalse(
            ArtigoBloco.objects.filter(pk=bloco.pk).exists()
        )

        bloco_excluido = ArtigoBloco.all_objects.get(pk=bloco.pk)

        self.assertFalse(bloco_excluido.ativo)
        self.assertIsNotNone(bloco_excluido.excluido_em)

    def test_video_de_outro_artigo_nao_pode_ser_adulterado(self):
        artigo_a = Artigo.objects.create(
            autor=self.user,
            categoria=self.cat,
            titulo="Artigo A",
            conteudo="Texto A",
        )

        artigo_b = Artigo.objects.create(
            autor=self.user,
            categoria=self.cat,
            titulo="Artigo B",
            conteudo="Texto B",
        )

        bloco_b = ArtigoBloco.objects.create(
            artigo=artigo_b,
            tipo=ArtigoBloco.Tipo.VIDEO,
            titulo="Video protegido",
            url="https://youtu.be/dQw4w9WgXcQ",
            ordem=1,
        )

        self.client.force_login(self.user)

        dados = {
            "categoria": self.cat.pk,
            "titulo": artigo_a.titulo,
            "conteudo": artigo_a.conteudo,
            "tipo_editorial": "NOTICIA",
            "videos-TOTAL_FORMS": "1",
            "videos-INITIAL_FORMS": "1",
            "videos-MIN_NUM_FORMS": "0",
            "videos-MAX_NUM_FORMS": "1000",
            "videos-0-id": str(bloco_b.pk),
            "videos-0-titulo": "VIDEO ADULTERADO",
            "videos-0-url": "https://youtu.be/9bZkp7q19f0",
            "videos-0-ordem": "99",
        }

        response = self.client.post(
            reverse("painel:news_artigo_editar", args=[artigo_a.uuid]),
            dados,
        )

        self.assertEqual(response.status_code, 302)

        bloco_b.refresh_from_db()

        self.assertEqual(bloco_b.titulo, "Video protegido")
        self.assertEqual(bloco_b.identificador_externo, "dQw4w9WgXcQ")
        self.assertEqual(bloco_b.ordem, 1)

    def test_iframe_arbitrario_nao_e_persistido_no_conteudo(self):
        artigo = Artigo(
            autor=self.user,
            categoria=self.cat,
            titulo="Artigo iframe inseguro",
            conteudo=(
                '<p>Texto seguro</p>'
                '<iframe src="https://evil.example/embed/123"></iframe>'
            ),
        )

        artigo.save()

        artigo.refresh_from_db()

        self.assertNotIn("<iframe", artigo.conteudo.lower())
        self.assertNotIn("evil.example", artigo.conteudo.lower())

