from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AccountDashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dashboard_user",
            password="senha-local-forte",
            nome_exibicao="Pessoa de Teste",
        )

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("painel:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("next=/painel/", response.url)

    def test_empty_account_renders_contextual_first_steps(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("painel:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bem-vindo à BOTUKA")
        self.assertContains(response, "Cadastrar empresa")
        self.assertContains(response, "Criar currículo")
        self.assertContains(response, "Cadastrar serviço")
        self.assertNotContains(response, 'href="#"')
        self.assertNotContains(response, "data-progress=")

    def test_logout_rejects_get_and_accepts_post(self):
        self.client.force_login(self.user)
        logout_url = reverse("accounts:logout")
        self.assertEqual(self.client.get(logout_url).status_code, 405)
        response = self.client.post(logout_url)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_dashboard_templates_have_no_inline_css_or_script(self):
        template_root = Path(__file__).resolve().parents[2] / "templates" / "painel"
        for relative in ("base.html", "dashboard.html"):
            content = (template_root / relative).read_text(encoding="utf-8")
            self.assertNotIn("<style", content.lower())
            self.assertNotIn("style=", content.lower())
            self.assertNotIn("<script>", content.lower())
