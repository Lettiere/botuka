from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Perfil, PerfilPermissao, Permissao


class PanelNavigationTests(TestCase):
    module_labels = (
        "Esportes", "YTv Botuka", "BOTUKA News", "Prefeitura",
        "Turismo", "Vagas", "Currículo", "Candidaturas",
    )

    def make_user(self, username, profile_name, *permissions):
        profile, _ = Perfil.objects.get_or_create(nome=profile_name)
        user = get_user_model().objects.create_user(username, password="x", perfil=profile)
        for code in permissions:
            permission, _ = Permissao.objects.get_or_create(codigo=code, defaults={"nome": code})
            PerfilPermissao.objects.create(perfil=profile, permissao=permission)
        return user

    def assert_all_modules(self, profile_name):
        user = self.make_user(profile_name.lower(), profile_name)
        self.client.force_login(user)
        response = self.client.get(reverse("painel:dashboard"))
        self.assertEqual(response.status_code, 200)
        items = [item for group in response.context["painel_module_groups"] for item in group["items"]]
        self.assertEqual({item["label"] for item in items}, set(self.module_labels))
        self.assertTrue(all(item["url"] for item in items))

    def test_root_ve_todos_os_modulos(self):
        self.assert_all_modules("ROOT")

    def test_master_ve_todos_os_modulos(self):
        self.assert_all_modules("MASTER")

    def test_usuario_sem_permissao_nao_ve_modulos_restritos(self):
        user = self.make_user("sem_permissao_nav", "CIDADAO_NAV")
        self.client.force_login(user)
        response = self.client.get(reverse("painel:dashboard"))
        items = [item for group in response.context["painel_module_groups"] for item in group["items"]]
        self.assertEqual({item["label"] for item in items}, {"Currículo", "Candidaturas"})

    def test_permissao_especifica_exibe_somente_modulo_autorizado(self):
        user = self.make_user("reporter_nav", "NEWS_REPORTER_NAV", "news.criar")
        self.client.force_login(user)
        response = self.client.get(reverse("painel:dashboard"))
        items = [item for group in response.context["painel_module_groups"] for item in group["items"]]
        labels = {item["label"] for item in items}
        self.assertIn("BOTUKA News", labels)
        self.assertNotIn("YTv Botuka", labels)
        self.assertNotIn("Prefeitura", labels)
        self.assertNotIn("Turismo", labels)
        self.assertEqual(self.client.get(reverse("painel:news_dashboard")).status_code, 200)
