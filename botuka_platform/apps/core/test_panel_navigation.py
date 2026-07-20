from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Perfil, PerfilPermissao, Permissao


class PanelNavigationTests(TestCase):
    module_labels = (
        "Esportes", "YTv Botuka", "BOTUKA News", "Prefeitura",
        "Vagas", "Currículo", "Candidaturas",
    )

    def make_user(self, username, profile_name, *permissions):
        profile = Perfil.objects.create(nome=profile_name)
        user = get_user_model().objects.create_user(username, password="x", perfil=profile)
        for code in permissions:
            permission = Permissao.objects.create(codigo=code, nome=code)
            PerfilPermissao.objects.create(perfil=profile, permissao=permission)
        return user

    def assert_all_modules(self, profile_name):
        user = self.make_user(profile_name.lower(), profile_name)
        self.client.force_login(user)
        response = self.client.get(reverse("painel:dashboard"))
        self.assertEqual(response.status_code, 200)
        for label in self.module_labels:
            self.assertContains(response, label)
        for icon in (
            "bi-trophy-fill", "bi-play-btn-fill", "bi-newspaper", "bi-bank2",
            "bi-briefcase-fill", "bi-file-earmark-person-fill", "bi-person-check-fill",
        ):
            self.assertContains(response, icon)
        self.assertContains(response, "Módulos do painel")

    def test_root_ve_todos_os_modulos(self):
        self.assert_all_modules("ROOT")

    def test_master_ve_todos_os_modulos(self):
        self.assert_all_modules("MASTER")

    def test_usuario_sem_permissao_nao_ve_modulos_restritos(self):
        user = self.make_user("sem_permissao_nav", "CIDADAO_NAV")
        self.client.force_login(user)
        response = self.client.get(reverse("painel:dashboard"))
        for label in ("Esportes", "YTv Botuka", "BOTUKA News", "Prefeitura", "Vagas"):
            self.assertNotContains(response, label)
        self.assertContains(response, "Currículo")
        self.assertContains(response, "Candidaturas")

    def test_permissao_especifica_exibe_somente_modulo_autorizado(self):
        user = self.make_user("reporter_nav", "NEWS_REPORTER_NAV", "news.criar")
        self.client.force_login(user)
        response = self.client.get(reverse("painel:dashboard"))
        self.assertContains(response, "BOTUKA News")
        self.assertNotContains(response, "YTv Botuka")
        self.assertNotContains(response, "Prefeitura")
        self.assertEqual(self.client.get(reverse("painel:news_dashboard")).status_code, 200)
