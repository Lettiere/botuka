from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Perfil, PerfilPermissao, Permissao

from .forms import ArtigoForm
from .models import Artigo, Autor, CategoriaNoticia


class NewsPanelAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("autor-news", password="x")
        self.other = get_user_model().objects.create_user("outro-news", password="x")
        self.category = CategoriaNoticia.objects.create(nome="Cidade")
        self.author = Autor.objects.create(usuario=self.user, nome="Autor")
        self.other_author = Autor.objects.create(usuario=self.other, nome="Outro")

    def grant(self, user, *codes):
        profile, _ = Perfil.objects.get_or_create(nome=f"PROFILE-{user.pk}")
        user.perfil = profile
        user.save(update_fields=["perfil"])
        for code in codes:
            permission = Permissao.all_objects.get(codigo=code)
            PerfilPermissao.objects.get_or_create(perfil=profile, permissao=permission)

    def article(self, user=None, author=None):
        return Artigo.objects.create(
            autor=user or self.user, autor_editorial=author or self.author,
            categoria=self.category, titulo="Artigo de teste", conteudo="Conteúdo.",
        )

    def test_usuario_sem_acesso_nao_entra(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("painel:news_dashboard")).status_code, 403)

    def test_autor_nao_ve_campo_de_autor(self):
        self.grant(self.user, "news.criar_artigo")
        form = ArtigoForm(usuario=self.user)
        self.assertNotIn("autor_editorial", form.fields)

    def test_manipulacao_de_autor_e_rejeitada(self):
        self.grant(self.user, "news.criar_artigo")
        form = ArtigoForm(
            data={
                "titulo": "Título", "conteudo": "Conteúdo",
                "categoria": self.category.pk, "autor_editorial": self.other_author.pk,
            },
            usuario=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Você não pode atribuir outro autor", str(form.non_field_errors()))

    def test_autor_nao_edita_artigo_de_terceiro(self):
        self.grant(self.user, "news.acessar_modulo", "news.editar_artigo_proprio")
        article = self.article(self.other, self.other_author)
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(reverse("painel:news_artigo_editar", args=[article.uuid])).status_code,
            404,
        )

    def test_permissao_de_atribuir_autor_exibe_campo(self):
        self.grant(self.user, "news.atribuir_autor")
        self.assertIn("autor_editorial", ArtigoForm(usuario=self.user).fields)
