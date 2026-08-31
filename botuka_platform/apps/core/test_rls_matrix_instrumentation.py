from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import ConfiguracaoSistema
from apps.news.models import Artigo, Autor, CategoriaNoticia, EditorialStatus


class InternalExecutorMatrixTests(TestCase):
    def setUp(self):
        self.master = get_user_model().objects.create_superuser(
            "matrix-master", email="matrix@example.invalid", password="x"
        )
        self.client.force_login(self.master)

    def test_gestao_e_comunicacao_renderizam_no_executor_internal(self):
        urls = [
            "/gestao/",
            "/gestao/comunicacao/",
            "/gestao/comunicacao/prospeccao/",
            "/gestao/comunicacao/distribuicao/",
            "/gestao/comunicacao/marketing/",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_crud_configuracao_sistema_no_executor_internal(self):
        add_url = reverse("admin:core_configuracaosistema_add")
        response = self.client.post(
            add_url,
            {
                "chave": "rls.matrix.instrumentada",
                "valor": "criada no banco temporario",
                "descricao": "evidencia CRUD do executor internal",
                "ativo": "on",
                "_save": "Salvar",
            },
        )
        self.assertEqual(response.status_code, 302)
        item = ConfiguracaoSistema.all_objects.get(chave="rls.matrix.instrumentada")

        change_url = reverse("admin:core_configuracaosistema_change", args=[item.pk])
        response = self.client.post(
            change_url,
            {
                "chave": item.chave,
                "valor": "atualizada no banco temporario",
                "descricao": item.descricao,
                "ativo": "on",
                "_save": "Salvar",
            },
        )
        self.assertEqual(response.status_code, 302)

        delete_url = reverse("admin:core_configuracaosistema_delete", args=[item.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 200)
        self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 302)


class WorkerExecutorMatrixTests(TestCase):
    databases = {"default", "worker"}

    def setUp(self):
        self.usuario = get_user_model().objects.create_user("matrix-worker", password="x")
        self.autor = Autor.objects.create(usuario=self.usuario, nome="Autora Matrix")
        self.categoria = CategoriaNoticia.objects.create(nome="Categoria Matrix")
        self.artigo = Artigo.objects.create(
            autor=self.usuario,
            autor_editorial=self.autor,
            categoria=self.categoria,
            titulo="Publicacao instrumentada",
            conteudo="Conteudo valido para a instrumentacao.",
            status=EditorialStatus.AGENDADO,
            agendado_para=timezone.now() - timedelta(minutes=1),
            publicador=self.usuario,
        )

    def test_publicar_noticias_agendadas_no_executor_worker(self):
        call_command("publicar_noticias_agendadas", verbosity=0)
        self.artigo.refresh_from_db()
        self.assertEqual(self.artigo.status, EditorialStatus.PUBLICADO)
        self.assertTrue(self.artigo.historico_editorial.exists())
