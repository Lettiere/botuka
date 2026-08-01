from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.demo_seeds import seed_home_demo
from apps.government.models import AcaoPublica, OrgaoPublico
from apps.media.models import Episodio, Programa
from apps.sports.models import Atleta, Campeonato, Disputa, Equipe, Modalidade


@override_settings(DEBUG=True)
class ModernPublicModulesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_home_demo()

    def test_home_exibe_quatro_vitrines_com_destinos_reais(self):
        response = self.client.get(reverse("home"))
        for texto in ("YoBotuka", "Esportes em Botucatu", "Próximos jogos e resultados", "Prefeitura de Botucatu"):
            self.assertContains(response, texto)
        for route in ("media_public:yubotuka_home", "media_public:yubotuka_ao_vivo", "sports_public:home", "government_public:home"):
            self.assertContains(response, reverse(route))
        self.assertNotContains(response, 'href="#"')
        self.assertNotContains(response, "/painel/")

    def test_listagens_filtros_invalidos_e_estados_vazios(self):
        for route in ("media_public:home", "media_public:ao_vivo", "sports_public:home", "government_public:home"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route), {"page": "inválida", "categoria": "inexistente", "status": "inexistente"})
                self.assertEqual(response.status_code, 200)

    def test_paginas_filhas_publicas(self):
        objects = [
            ("media_public:programa", Programa.objects.first().slug),
            ("media_public:episodio", Episodio.objects.filter(status="PUBLICADO").first().slug),
            ("sports_public:modalidade", Modalidade.objects.first().slug),
            ("sports_public:equipe", Equipe.objects.first().slug),
            ("sports_public:atleta", Atleta.objects.filter(publico=True).first().uuid),
            ("sports_public:campeonato", Campeonato.objects.first().slug),
            ("sports_public:jogo", Disputa.objects.first().uuid),
            ("government_public:orgao", OrgaoPublico.objects.first().slug),
            ("government_public:acao", AcaoPublica.objects.filter(status="PUBLICADO").first().slug),
        ]
        for route, argument in objects:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route, args=[argument])).status_code, 200)

    def test_templates_sem_orm_inline_ou_links_falsos(self):
        roots = ["home/includes", "publico/ytv", "publico/sports", "publico/government"]
        selected = {"ytv.html", "esportes.html", "jogos.html", "prefeitura.html"}
        for root in roots:
            for path in (Path(settings.BASE_DIR) / "templates" / root).glob("*.html"):
                if root == "home/includes" and path.name not in selected:
                    continue
                content = path.read_text(encoding="utf-8")
                for forbidden in ('href="#"', ".objects", "<style", "<script", "onclick="):
                    self.assertNotIn(forbidden, content, f"{path}: {forbidden}")

    def test_ao_vivo_sem_transmissao_nao_renderiza_iframe(self):
        response = self.client.get(reverse("media_public:ao_vivo"))
        self.assertNotContains(response, "<iframe")
        self.assertContains(response, "Nenhuma transmissão ao vivo neste momento")
