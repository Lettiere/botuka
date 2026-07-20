from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from apps.core.demo_seeds import seed_home_demo


@override_settings(DEBUG=True)
class PublicDirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_home_demo()

    def test_rotas_publicas_principais(self):
        routes = [
            "home", "events:lista", "publico:empresas", "publico:servicos",
            "recruitment_public:vagas", "media_public:home", "media_public:ao_vivo",
            "sports_public:home", "government_public:home", "news_public:home",
        ]
        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)

    def test_cultura_e_filtros_invalidos_nao_geram_500(self):
        from apps.news.models import CategoriaNoticia
        cultura = CategoriaNoticia.objects.get(nome="Cultura")
        self.assertEqual(self.client.get(reverse("news_public:categoria", args=[cultura.slug])).status_code, 200)
        for route in ("events:lista", "publico:empresas", "publico:servicos", "recruitment_public:vagas", "media_public:home"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route), {"page": "inválida", "ordem": "inexistente", "q": "%' OR 1=1 --"})
                self.assertEqual(response.status_code, 200)

    def test_home_aponta_para_diretorios_e_nao_lista_curriculos(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("events:lista"))
        self.assertContains(response, reverse("publico:empresas"))
        self.assertContains(response, reverse("publico:servicos"))
        self.assertNotContains(response, "Profissionais disponíveis")
        curriculum_url = reverse("recruitment_public:curriculo", args=["00000000-0000-0000-0000-000000000000"])
        self.assertNotContains(response, curriculum_url)

    def test_templates_novos_sem_links_falsos_orm_ou_inline(self):
        templates = [
            "publico/eventos/lista.html", "publico/empresas/lista.html",
            "publico/servicos/lista.html", "publico/vagas/lista.html",
            "publico/news/home.html", "publico/ytv/home.html", "publico/ytv/ao_vivo.html",
        ]
        for relative in templates:
            content = (Path(settings.BASE_DIR) / "templates" / relative).read_text(encoding="utf-8")
            self.assertNotIn('href="#"', content, relative)
            self.assertNotIn(".objects", content, relative)
            self.assertNotIn("<style", content, relative)
            self.assertNotIn("<script", content, relative)

    def test_paginacao_preserva_query_string(self):
        response = self.client.get(reverse("publico:empresas"), {"q": "Empresa", "page": 1})
        self.assertEqual(response.status_code, 200)
        if response.context["page_obj"].has_next():
            self.assertContains(response, "q=Empresa")
