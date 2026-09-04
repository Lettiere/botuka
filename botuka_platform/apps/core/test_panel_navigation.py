from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Perfil, PerfilPermissao, Permissao
from apps.organizations.models import Empresa


class PanelNavigationTests(TestCase):
    module_labels = (
        "BOTUKA News", "YoBotuka", "Prefeitura", "Turismo",
        "Empresas", "Serviços", "Produtos", "Novo produto",
        "Conversas de produtos", "Denúncias de produtos", "Vagas",
        "Currículo", "Candidaturas", "Eventos", "Rede Social", "Esportes",
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
        self.assertEqual(
            {item["label"] for item in items},
            {"Empresas", "Serviços", "Currículo", "Candidaturas", "Rede Social"},
        )

    def test_comunidade_exibe_somente_atalho_central_do_social(self):
        user = self.make_user("comunidade_nav", "CIDADAO_COMUNIDADE_NAV")
        self.client.force_login(user)
        response = self.client.get(reverse("painel:dashboard"))
        community = next(
            group for group in response.context["painel_module_groups"]
            if group["label"] == "Comunidade"
        )
        self.assertEqual(community["items"], [{
            "label": "Rede Social",
            "description": "Feed, conexões e comunidade",
            "icon": "bi-people-fill",
            "url": "http://127.0.0.1:7800/social/",
        }])

    def test_permissao_especifica_exibe_somente_modulo_autorizado(self):
        user = self.make_user(
            "reporter_nav", "NEWS_REPORTER_NAV",
            "news.acessar_modulo", "news.criar",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("painel:dashboard"))
        items = [item for group in response.context["painel_module_groups"] for item in group["items"]]
        labels = {item["label"] for item in items}
        self.assertIn("BOTUKA News", labels)
        self.assertNotIn("YoBotuka", labels)
        self.assertNotIn("Prefeitura", labels)
        self.assertNotIn("Turismo", labels)
        self.assertEqual(self.client.get(reverse("painel:news_dashboard")).status_code, 200)

    def test_modal_oferece_cadastro_para_usuario_sem_empresa(self):
        user = self.make_user("sem_empresa_nav", "CIDADAO_SEM_EMPRESA_NAV")
        self.client.force_login(user)

        response = self.client.get(reverse("painel:dashboard"))

        self.assertContains(response, 'data-navigation-category="company"')
        self.assertContains(
            response,
            f'class="navigation-company-create" href="{reverse("painel:empresa_criar")}"',
        )
        self.assertContains(response, "Cadastrar nova empresa")

        total_antes = Empresa.objects.filter(usuario_proprietario=user).count()
        wizard = self.client.get(reverse("painel:empresa_criar"))
        self.assertEqual(wizard.status_code, 200)
        self.assertTemplateUsed(wizard, "painel/empresas/wizard.html")
        self.assertEqual(
            Empresa.objects.filter(usuario_proprietario=user).count(), total_antes,
        )

    def test_modal_preserva_empresas_e_oferece_cadastro_com_uma_ou_varias(self):
        user = self.make_user("com_empresas_nav", "CIDADAO_COM_EMPRESAS_NAV")
        primeira = Empresa.objects.create(
            usuario_proprietario=user, nome_fantasia="Empresa Alfa",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("painel:dashboard"))
        self.assertContains(response, "Empresa Alfa")
        self.assertContains(response, "Cadastrar nova empresa")
        self.assertContains(response, reverse("painel:empresa_detalhe", args=[primeira.uuid]))

        segunda = Empresa.objects.create(
            usuario_proprietario=user, nome_fantasia="Empresa Beta",
        )
        response = self.client.get(reverse("painel:dashboard"))
        self.assertContains(response, 'data-company-menu-select')
        self.assertContains(response, "Empresa Alfa")
        self.assertContains(response, "Empresa Beta")
        self.assertContains(response, "Cadastrar nova empresa")
        self.assertContains(response, reverse("painel:empresa_detalhe", args=[primeira.uuid]))
        self.assertContains(response, reverse("painel:empresa_detalhe", args=[segunda.uuid]))

    def test_cadastro_no_limite_delega_bloqueio_para_view_sem_criar_empresa(self):
        user = self.make_user("limite_empresa_nav", "CIDADAO_LIMITE_EMPRESA_NAV")
        Empresa.objects.create(usuario_proprietario=user, nome_fantasia="Empresa Única")
        self.client.force_login(user)
        total_antes = Empresa.objects.filter(usuario_proprietario=user).count()

        response = self.client.get(reverse("painel:empresa_criar"))

        self.assertRedirects(response, reverse("painel:empresas_lista"))
        self.assertEqual(
            Empresa.objects.filter(usuario_proprietario=user).count(), total_antes,
        )
