from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Perfil, PerfilPermissao, Permissao

from .models import (
    Artigo, ArtigoFonte, Autor, CategoriaNoticia, Coluna, Colunista,
    EditorialStatus, ImagemPublicacao, LinkRelacionado, MidiaIncorporada,
)
from .services import alterar_status, publicar_agendados


class EditorialBaseTest(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("autora", password="x")
        self.autor = Autor.objects.create(usuario=self.usuario, nome="Autora Botuka")
        self.categoria = CategoriaNoticia.objects.create(nome="Agro Local")
        self.artigo = Artigo.objects.create(
            autor=self.usuario, autor_editorial=self.autor,
            categoria=self.categoria, titulo="Pesquisa melhora a produção",
            conteudo="Conteúdo editorial original.",
        )

    def grant(self, *codes):
        perfil, _ = Perfil.objects.get_or_create(nome=f"P-{self.usuario.pk}")
        self.usuario.perfil = perfil
        self.usuario.save(update_fields=["perfil"])
        for code in codes:
            permissao = Permissao.all_objects.get(codigo=code)
            PerfilPermissao.objects.get_or_create(perfil=perfil, permissao=permissao)


class SoftDeleteTests(EditorialBaseTest):
    def test_delete_individual_e_restore(self):
        uuid = self.artigo.uuid
        self.artigo.delete()
        self.assertFalse(Artigo.objects.filter(uuid=uuid).exists())
        removido = Artigo.all_objects.get(uuid=uuid)
        self.assertIsNotNone(removido.excluido_em)
        removido.restore()
        self.assertTrue(Artigo.objects.filter(uuid=uuid).exists())

    def test_delete_em_lote_e_logico(self):
        quantidade, _ = Artigo.objects.filter(pk=self.artigo.pk).delete()
        self.assertEqual(quantidade, 1)
        self.assertTrue(Artigo.all_objects.filter(pk=self.artigo.pk).exists())
        self.assertFalse(Artigo.objects.filter(pk=self.artigo.pk).exists())

    def test_restore_em_lote(self):
        Artigo.objects.filter(pk=self.artigo.pk).delete()
        self.assertEqual(Artigo.all_objects.excluidos().restore(), 1)
        self.assertTrue(Artigo.objects.filter(pk=self.artigo.pk).exists())


class AuthorAndColumnTests(EditorialBaseTest):
    def test_autor_pode_existir_sem_usuario(self):
        independente = Autor.objects.create(nome="Especialista independente")
        self.assertIsNone(independente.usuario)

    def test_autor_tem_multiplas_colunas_e_perfil_colunista(self):
        Coluna.objects.create(autor=self.autor, nome="Agro em Movimento")
        Coluna.objects.create(autor=self.autor, nome="Universidade em Foco")
        Colunista.objects.create(autor=self.autor)
        self.assertEqual(self.autor.colunas.count(), 2)
        self.assertEqual(self.client.get(reverse("news_public:colunista", args=[self.autor.slug])).status_code, 200)


class LinkAndMediaTests(EditorialBaseTest):
    def test_multiplas_fontes_e_links(self):
        for indice in range(2):
            ArtigoFonte.objects.create(
                artigo=self.artigo, titulo=f"Fonte {indice}",
                nome_fonte="Universidade", url=f"https://example.com/{indice}",
                data_acesso=timezone.localdate(),
            )
            LinkRelacionado.objects.create(
                artigo=self.artigo, tipo=LinkRelacionado.Tipo.SITE,
                titulo=f"Link {indice}", url=f"https://example.com/link/{indice}",
            )
        self.assertEqual(self.artigo.fontes.count(), 2)
        self.assertEqual(self.artigo.links_relacionados.count(), 2)

    def test_rejeita_iframe_e_javascript(self):
        with self.assertRaises(ValidationError):
            LinkRelacionado.objects.create(
                artigo=self.artigo, tipo=LinkRelacionado.Tipo.SITE,
                titulo="Inválido", url="javascript:alert(1)",
            )
        with self.assertRaises(ValidationError):
            MidiaIncorporada.objects.create(
                artigo=self.artigo, url="<iframe src='https://youtube.com'></iframe>",
            )

    def test_youtube_extrai_id_e_embed_privativo(self):
        midia = MidiaIncorporada.objects.create(
            artigo=self.artigo,
            url="https://youtu.be/dQw4w9WgXcQ?utm_source=teste",
        )
        self.assertEqual(midia.identificador_externo, "dQw4w9WgXcQ")
        self.assertEqual(midia.embed_url, "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")


class ImageRightsTests(EditorialBaseTest):
    def imagem(self, **kwargs):
        defaults = {
            "artigo": self.artigo,
            "url_externa": "https://example.com/imagem.jpg",
            "texto_alternativo": "Pesquisadora trabalhando em laboratório",
            "credito": "Universidade",
            "fonte": "Universidade",
            "url_fonte": "https://example.com/origem",
            "licenca": ImagemPublicacao.Licenca.USO_AUTORIZADO,
            "direitos_confirmados": True,
        }
        defaults.update(kwargs)
        return ImagemPublicacao(**defaults)

    def test_imagem_sem_credito_e_licenca_desconhecida_bloqueia(self):
        imagem = self.imagem(credito="", licenca=ImagemPublicacao.Licenca.DESCONHECIDA)
        with self.assertRaises(ValidationError):
            imagem.validar_direitos_publicacao()

    def test_imagem_externa_sem_fonte_e_direitos_bloqueia(self):
        imagem = self.imagem(fonte="", url_fonte="", direitos_confirmados=False)
        with self.assertRaises(ValidationError):
            imagem.validar_direitos_publicacao()

    def test_imagem_valida(self):
        self.imagem().validar_direitos_publicacao()


class WorkflowTests(EditorialBaseTest):
    def test_matriz_e_permissoes(self):
        with self.assertRaises(PermissionDenied):
            alterar_status(
                artigo=self.artigo, novo_status=EditorialStatus.ENVIADO_REVISAO,
                usuario=self.usuario,
            )
        self.grant("news.enviar_revisao")
        alterar_status(
            artigo=self.artigo, novo_status=EditorialStatus.ENVIADO_REVISAO,
            usuario=self.usuario,
        )
        self.assertEqual(self.artigo.historico_editorial.count(), 1)
        with self.assertRaises(ValidationError):
            alterar_status(
                artigo=self.artigo, novo_status=EditorialStatus.PUBLICADO,
                usuario=self.usuario,
            )

    def test_publicacao_agendada(self):
        self.artigo.status = EditorialStatus.AGENDADO
        self.artigo.agendado_para = timezone.now() - timedelta(minutes=1)
        self.artigo.save()
        self.assertEqual(publicar_agendados(), 1)
        self.artigo.refresh_from_db()
        self.assertEqual(self.artigo.status, EditorialStatus.PUBLICADO)


class PublicAndAliasesTests(EditorialBaseTest):
    def test_aliases_publico_e_painel(self):
        self.assertEqual(self.client.get("/news/").status_code, 301)
        self.client.force_login(self.usuario)
        self.grant("news.acessar_painel")
        self.assertEqual(self.client.get("/painel/news/").status_code, 302)
        self.assertEqual(self.client.get("/painel/noticias/").status_code, 200)

    def test_home_publica_e_seo(self):
        self.artigo.status = EditorialStatus.PUBLICADO
        self.artigo.save()
        response = self.client.get(reverse("news_public:artigo", args=[self.artigo.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "NewsArticle")
