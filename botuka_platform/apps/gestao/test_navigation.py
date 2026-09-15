from html.parser import HTMLParser
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse

from apps.accounts.models import AcessoModulo, ConcessaoPermissao
from apps.core.models import Permissao
from apps.gestao.navigation import gestao_navigation


class _NavigationLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_sidebar = False
        self.links = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "aside" and attributes.get("id") == "gestao-sidebar":
            self.in_sidebar = True
        if self.in_sidebar and tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"])

    def handle_endtag(self, tag):
        if tag == "aside":
            self.in_sidebar = False


class GestaoNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.master = User.objects.create_superuser("navigation-master", password="x")
        cls.limited = User.objects.create_user("navigation-limited", password="x")
        for module, code in (("gestao", "gestao.acessar"), ("usuarios", "usuarios.visualizar")):
            access = AcessoModulo.objects.create(
                usuario=cls.limited, modulo=module, concedido_por=cls.master,
                justificativa="Teste de navegação",
            )
            permission, _ = Permissao.objects.get_or_create(
                codigo=code,
                defaults={"nome": code, "modulo": module, "grupo": "Gestão"},
            )
            ConcessaoPermissao.objects.create(
                acesso=access, usuario=cls.limited, permissao=permission,
                concedida_por=cls.master, justificativa="Teste de navegação",
            )

    def test_master_has_expected_groups_and_every_link_resolves(self):
        self.client.force_login(self.master)
        response = self.client.get(reverse("gestao:dashboard"))
        menu = response.content.decode().split('id="gestao-sidebar"', 1)[1].split("</aside>", 1)[0]
        for label in (
            "Visão geral", "Cadastros", "Conteúdo", "Negócios",
            "Publicidade", "Financeiro", "Inteligência", "Sistema",
        ):
            self.assertIn(label, menu)
        parser = _NavigationLinks()
        parser.feed(response.content.decode())
        self.assertGreater(len(parser.links), 20)
        for url in parser.links:
            resolve(urlsplit(url).path)

    def test_limited_user_only_sees_granted_group_and_link(self):
        self.client.force_login(self.limited)
        response = self.client.get(reverse("gestao:dashboard"))
        menu = response.content.decode().split('id="gestao-sidebar"', 1)[1].split("</aside>", 1)[0]
        self.assertIn("Usuários", menu)
        self.assertIn(reverse("gestao:usuarios_lista"), menu)
        for hidden in ("Empresas", "Publicidade", "Financeiro", "Analytics", "Configurações"):
            self.assertNotIn(hidden, menu)

    def test_child_page_marks_only_its_item_and_group_active(self):
        self.client.force_login(self.master)
        response = self.client.get(reverse("gestao:central_lista", args=["artigos"]))
        menu = response.content.decode().split('id="gestao-sidebar"', 1)[1].split("</aside>", 1)[0]
        self.assertEqual(menu.count('aria-current="page"'), 1)
        self.assertIn('class="is-active" aria-current="page"><i class="bi bi-newspaper"', menu)
        self.assertIn('class="gestao-menu-group is-active" open', menu)

    def test_mobile_controls_focus_contract_and_logout_is_post(self):
        self.client.force_login(self.master)
        response = self.client.get(reverse("gestao:dashboard"))
        self.assertContains(response, 'aria-controls="gestao-sidebar"')
        self.assertContains(response, 'aria-expanded="false"')
        self.assertContains(response, 'data-sidebar-close')
        self.assertContains(response, 'aria-hidden="true"></button>')
        self.assertContains(response, 'method="post" action="{}"'.format(reverse("accounts:logout")))
        self.assertNotContains(response, 'href="{}"'.format(reverse("accounts:logout")))

    def test_navigation_permission_matrix_has_bounded_queries(self):
        request = RequestFactory().get(reverse("gestao:dashboard"))
        request.user = self.limited
        request.resolver_match = resolve(request.path)
        with CaptureQueriesContext(connection) as queries:
            navigation = gestao_navigation(request)["gestao_navigation"]
        self.assertTrue(navigation)
        self.assertLessEqual(len(queries), 12)
