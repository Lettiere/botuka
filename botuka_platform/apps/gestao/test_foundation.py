from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import AcessoModulo, ConcessaoPermissao
from apps.core.models import Permissao


class GestaoFoundationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.master = user_model.objects.create_superuser(
            "foundation-master", password="x",
        )
        self.user = user_model.objects.create_user(
            "foundation-user", password="x",
        )
        self.target = user_model.objects.create_user(
            "foundation-target", password="x", is_active=True,
        )

    def grant(self, *codes):
        access = AcessoModulo.objects.create(
            usuario=self.user,
            modulo="gestao",
            concedido_por=self.master,
            justificativa="Teste da fundação da gestão",
        )
        for code in codes:
            permission = Permissao.objects.get(codigo=code)
            ConcessaoPermissao.objects.create(
                acesso=access,
                usuario=self.user,
                permissao=permission,
                concedida_por=self.master,
                justificativa="Teste da fundação da gestão",
            )

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("gestao:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_base_renders_accessible_navigation_breadcrumb_and_post_logout(self):
        self.client.force_login(self.master)
        response = self.client.get(reverse("gestao:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="gestao-sidebar"')
        self.assertContains(response, 'aria-label="Navegação estrutural"')
        self.assertContains(response, 'data-sidebar-open')
        self.assertContains(
            response,
            f'<form class="gestao-logout" method="post" action="{reverse("accounts:logout")}">',
            html=False,
        )
        self.assertNotContains(response, f'href="{reverse("accounts:logout")}"')

    def test_sidebar_only_exposes_authorized_areas(self):
        self.grant("gestao.acessar")
        self.client.force_login(self.user)
        response = self.client.get(reverse("gestao:dashboard"))
        self.assertEqual(response.status_code, 200)
        menu = response.content.decode().split(
            '<nav class="gestao-menu"', 1,
        )[1].split("</nav>", 1)[0]
        self.assertNotIn(reverse("gestao:usuarios_lista"), menu)
        self.assertNotIn(reverse("gestao:configuracoes_lista"), menu)

    def test_status_changes_reject_get_and_accept_authorized_post(self):
        self.client.force_login(self.master)
        deactivate_url = reverse("gestao:usuarios_desativar", args=[self.target.pk])
        self.assertEqual(self.client.get(deactivate_url).status_code, 405)
        response = self.client.post(deactivate_url)
        self.assertRedirects(response, reverse("gestao:usuarios_lista"))
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

        activate_url = reverse("gestao:usuarios_ativar", args=[self.target.pk])
        self.assertEqual(self.client.get(activate_url).status_code, 405)
        self.client.post(activate_url)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

    def test_unauthorized_status_change_is_blocked(self):
        self.grant("gestao.acessar")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("gestao:usuarios_desativar", args=[self.target.pk]),
        )
        self.assertEqual(response.status_code, 403)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)
