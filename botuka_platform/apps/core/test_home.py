from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.demo_seeds import seed_home_demo
from apps.core.services.home import montar_contexto_home


@override_settings(DEBUG=True, CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "home-tests"}})
class HomeAggregatorTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_home_responde_200_com_banco_vazio(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Serviços em destaque")

    def test_contexto_tem_contrato_estavel_e_limites(self):
        seed_home_demo(); cache.clear()
        contexto = montar_contexto_home()
        chaves = {"empresas_destaque", "servicos_destaque", "vagas_recentes",
            "noticias_destaque", "noticias_recentes", "programas_ytv", "episodios_ytv",
            "transmissoes_ao_vivo", "modalidades_esportivas", "campeonatos_ativos",
            "jogos_proximos", "resultados_recentes", "acoes_prefeitura", "orgaos_publicos",
            "eventos_destaque", "eventos_proximos", "cultura_destaque", "cultura_recentes",
            "gastronomia_destaque", "parques_destaque", "empresas_agenda",
            "estatisticas_home"}
        self.assertTrue(chaves.issubset(contexto))
        self.assertLessEqual(len(contexto["servicos_destaque"]), 6)
        self.assertLessEqual(len(contexto["episodios_ytv"]), 4)
        self.assertLessEqual(len(contexto["acoes_prefeitura"]), 4)

    def test_conteudo_publicado_aparece_e_privado_nao(self):
        seed_home_demo(); cache.clear()
        from decimal import Decimal

        from django.contrib.auth import get_user_model
        from django.utils import timezone

        from apps.products.models import CategoriaProduto, FamiliaProduto, Produto, TipoProduto
        from apps.services.models import (
            AreaProfissional,
            FormaCobranca,
            Profissao,
            ProfissaoTipoServico,
            Servico,
            Setor,
            TipoServico,
        )

        usuario = get_user_model().objects.get(username="demo_servicos")
        setor = Setor.objects.create(nome="Setor público da HOME")
        area = AreaProfissional.objects.create(setor=setor, nome="Área pública da HOME")
        profissao = Profissao.objects.create(
            setor=setor, area=area, nome="Profissão pública da HOME",
        )
        tipo_servico = TipoServico.objects.create(nome="Tipo público da HOME")
        ProfissaoTipoServico.objects.create(
            profissao=profissao, tipo_servico=tipo_servico,
        )
        forma_cobranca = FormaCobranca.objects.create(nome="Cobrança pública da HOME")
        Servico.objects.create(
            usuario_responsavel=usuario,
            prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA,
            setor=setor,
            area=area,
            profissao=profissao,
            tipo_servico=tipo_servico,
            forma_cobranca=forma_cobranca,
            titulo="Serviço público válido da HOME",
            status=Servico.Status.PUBLICADO,
            destaque=True,
        )

        categoria = CategoriaProduto.objects.create(
            nome="Categoria pública da HOME", slug="categoria-publica-home",
        )
        familia = FamiliaProduto.objects.create(
            categoria=categoria, nome="Família pública da HOME", slug="familia-publica-home",
        )
        tipo_produto = TipoProduto.objects.create(
            familia=familia,
            nome="Tipo de produto público da HOME",
            slug="tipo-produto-publico-home",
        )
        Produto.objects.create(
            nome="Produto público destacado da HOME",
            categoria=categoria.nome,
            categoria_taxonomia=categoria,
            familia=familia,
            tipo_produto=tipo_produto,
            descricao_curta="Produto válido para a HOME.",
            descricao_completa="Produto público destacado para teste.",
            preco=Decimal("20.00"),
            titular_tipo=Produto.TitularTipo.PESSOA_FISICA,
            criador_registro=usuario,
            proprietario=usuario,
            responsavel=usuario,
            status=Produto.Status.PUBLICADO,
            publicado_em=timezone.now(),
            publico=True,
            destaque=True,
        )
        cache.clear()

        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Serviço demonstrativo 01")
        self.assertNotContains(response, "Serviço demonstrativo 25")
        self.assertContains(response, "Serviço público válido da HOME")
        self.assertContains(response, "Produto público destacado da HOME")
        self.assertContains(response, "Oportunidade demonstrativa 12")
        self.assertContains(response, "Conteúdo demonstrativo da cidade 01")
        self.assertContains(response, "Episódio demonstrativo 01")
        self.assertNotContains(response, "Episódio demonstrativo 13")
        self.assertContains(response, "Campeonato Demo 01")
        self.assertContains(response, "Ação pública demonstrativa 01")
        self.assertContains(response, "Eventos em Botucatu")
        self.assertContains(response, "Cultura em Botucatu")
        self.assertContains(response, "Bares e restaurantes")
        self.assertContains(response, "Parques, praças e lazer")

    def test_curriculo_privado_e_dados_sensiveis_nao_aparecem(self):
        seed_home_demo(); cache.clear()
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "demo_candidato08")
        self.assertNotContains(response, "cpf")
        self.assertNotContains(response, "data_nascimento")

    @patch("apps.core.services.home.aggregator.services.obter_servicos_destaque", side_effect=RuntimeError("falha simulada"))
    def test_falha_isolada_nao_derruba_home(self, _adapter):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["servicos_destaque"], [])

    @patch("apps.core.services.home.aggregator.events.obter_eventos", side_effect=RuntimeError("falha simulada"))
    def test_falha_de_eventos_fica_isolada(self, _adapter):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["eventos_destaque"], [])
        self.assertEqual(response.context["eventos_proximos"], [])

    def test_includes_e_sql_seguro(self):
        includes = ["empresas", "servicos", "agenda", "vagas", "news", "eventos", "cultura",
            "gastronomia", "parques", "ytv", "esportes", "jogos", "prefeitura", "empty_state"]
        for name in includes:
            self.assertTrue((Path(settings.BASE_DIR) / "templates" / "home" / "includes" / f"{name}.html").is_file())
        sql = Path(settings.BASE_DIR).parent / "database" / "seeds" / "botuka_demo_inserts.sql"
        if sql.exists():
            content = sql.read_text(encoding="utf-8").lower()
            for command in ("drop ", "delete ", "truncate "):
                self.assertNotIn(command, content)

    def test_home_nao_expoe_curriculos(self):
        seed_home_demo(); cache.clear()
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Profissionais disponíveis")
        self.assertNotIn("curriculos_publicos", response.context)

    def test_home_e_navbar_expoem_entrada_da_agenda(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Agenda Botuka")
        self.assertContains(response, reverse("agenda_public:home"))
        self.assertContains(response, "botukaExploreModal")
        self.assertContains(response, "Explorar recursos")


@override_settings(DEBUG=True)
class DemoSeedTests(TestCase):
    def test_execucao_dupla_nao_duplica(self):
        first = seed_home_demo()
        second = seed_home_demo()
        self.assertEqual(first, second)
        from apps.services.models import Servico
        from apps.news.models import Artigo
        self.assertEqual(Servico.all_objects.filter(slug__startswith="servico-demo-").count(), 30)
        self.assertEqual(Artigo.objects.filter(slug__startswith="artigo-demo-").count(), 20)
