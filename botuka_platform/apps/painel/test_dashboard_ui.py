from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase
from django.urls import reverse


class DashboardUiContractTests(SimpleTestCase):
    def setUp(self):
        self.template_path = (
            Path(settings.BASE_DIR) / "templates" / "painel" / "dashboard.html"
        )
        self.css_path = (
            Path(settings.BASE_DIR) / "static" / "painel" / "css" / "dashboard.css"
        )

    def test_dashboard_preserva_rota_e_template(self):
        self.assertEqual(reverse("painel:dashboard"), "/painel/")
        self.assertIsNotNone(get_template("painel/dashboard.html"))

    def test_dashboard_reutiliza_componentes_visuais_do_perfil(self):
        content = self.template_path.read_text(encoding="utf-8")
        for class_name in (
            "profile-page",
            "profile-container",
            "profile-hero",
            "profile-avatar",
            "profile-content-card",
            "profile-summary-card",
            "profile-button",
        ):
            self.assertIn(class_name, content)

    def test_dashboard_nao_possui_css_ou_javascript_embutido(self):
        content = self.template_path.read_text(encoding="utf-8").lower()
        self.assertNotIn("<style", content)
        self.assertNotIn("style=", content)
        self.assertNotIn("<script", content)
        self.assertIn("painel/css/dashboard.css", content)

    def test_css_isolado_define_grade_mobile_sem_overflow(self):
        content = self.css_path.read_text(encoding="utf-8")
        self.assertIn("@media(max-width:600px)", content)
        self.assertIn("grid-template-columns:1fr", content)
        self.assertIn("min-width:0", content)
