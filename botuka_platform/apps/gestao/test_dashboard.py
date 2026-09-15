from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AcessoModulo, ConcessaoPermissao
from apps.advertising.models import (
    AuditoriaPublicidade,
    Campanha,
    Criativo,
    EntregaPublicidade,
    PlanoPublicitario,
    Posicionamento,
)
from apps.analytics.models import AnalyticsDailyCompany, AnalyticsEvent
from apps.core.models import Auditoria, Permissao
from apps.organizations.models import Empresa
from apps.payments.models import Cobranca, Pagamento, Webhook


class GestaoDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.master = user_model.objects.create_superuser("dashboard-master", password="x")
        cls.limited = user_model.objects.create_user("dashboard-limited", password="x")
        access = AcessoModulo.objects.create(
            usuario=cls.limited, modulo="gestao", concedido_por=cls.master,
            justificativa="Teste do dashboard",
        )
        permission = Permissao.objects.get(codigo="gestao.acessar")
        ConcessaoPermissao.objects.create(
            acesso=access, usuario=cls.limited, permissao=permission,
            concedida_por=cls.master, justificativa="Teste do dashboard",
        )
        cls.company = Empresa.objects.create(
            nome_fantasia="Empresa Dashboard", usuario_proprietario=cls.master,
        )
        plan = PlanoPublicitario.objects.create(
            nome="Plano Dashboard", nivel=4, preco_diario=Decimal("10.00"),
        )
        position = Posicionamento.objects.create(
            codigo="dashboard-test", nome="Dashboard", contexto="home",
        )
        now = timezone.now()
        cls.campaign = Campanha.objects.create(
            empresa=cls.company, plano=plan, nome="Campanha pendente",
            status=Campanha.Status.AGUARDANDO_APROVACAO,
            inicio=now, fim=now + timedelta(days=2), criado_por=cls.master,
        )
        cls.campaign.posicionamentos.add(position)
        creative = Criativo.objects.create(
            campanha=cls.campaign, tipo=Criativo.Tipo.TEXTO,
            titulo="Criativo pendente", texto="Oferta",
            url_destino="https://example.com", ativo=True, aprovado=False,
        )
        EntregaPublicidade.objects.create(
            campanha=cls.campaign, criativo=creative, posicionamento=position,
            visitante_hash="visitor", contexto="home", clicado_em=now,
        )
        AuditoriaPublicidade.objects.create(
            campanha=cls.campaign, usuario=cls.master, acao="ENVIADA_APROVACAO",
        )
        Auditoria.objects.create(
            usuario=cls.master, acao="ATUALIZAR", entidade="Empresa",
            registro_id=str(cls.company.pk), origem="GESTAO",
        )
        charge = Cobranca.objects.create(
            empresa=cls.company, criada_por=cls.master,
            status=Cobranca.Status.PAGA, valor_total=Decimal("120.00"),
            paga_em=now,
        )
        Pagamento.objects.create(
            cobranca=charge, gateway="fake", status=Pagamento.Status.FALHOU,
            valor=Decimal("120.00"),
        )
        Webhook.objects.create(
            gateway="fake", event_id="dashboard-error", tipo="payment.failed",
            assinatura_valida=False, erro="Assinatura inválida",
        )
        AnalyticsDailyCompany.objects.create(
            date=now.date(), empresa=cls.company, views=12, visitors=5,
            impressions=20, leads=2, whatsapp_clicks=1,
        )
        AnalyticsEvent.objects.create(
            event_name="view_company", visitor_id="visitor", session_id="session",
            empresa=cls.company, path="/empresa/", dedupe_key="dashboard-event",
        )

    def test_master_sees_real_operational_metrics_and_activity(self):
        self.client.force_login(self.master)
        response = self.client.get(reverse("gestao:dashboard"))
        self.assertEqual(response.status_code, 200)
        operational = response.context["operational"]
        self.assertEqual(operational["advertising"]["awaiting"], 1)
        self.assertEqual(operational["advertising"]["ctr"], 100.0)
        self.assertEqual(operational["payments"]["paid_total"], Decimal("120.00"))
        self.assertEqual(operational["payments"]["failed"], 1)
        self.assertEqual(operational["analytics"]["views"], 12)
        self.assertEqual(operational["analytics"]["events_24h"], 1)
        self.assertEqual(operational["platform"]["companies"]["total"], 1)
        self.assertEqual(operational["platform"]["companies"]["active"], 0)
        self.assertEqual(operational["platform"]["users"]["active"], 2)
        self.assertContains(response, 'Plataforma')
        self.assertContains(response, "Campanha pendente")
        self.assertContains(response, "Operação comercial")
        self.assertContains(response, "Analytics — 30 dias")
        self.assertContains(response, "Insights derivados")
        self.assertContains(response, "Fila de publicidade")

    def test_attention_items_have_real_action_links_and_are_sorted(self):
        self.client.force_login(self.master)
        response = self.client.get(reverse("gestao:dashboard"))
        items = response.context["pendencias"]
        self.assertTrue(all(item["url"].startswith("/") for item in items))
        self.assertEqual(items[0]["label"], "Campanhas aguardando aprovação")
        self.assertContains(response, reverse("advertising:campanha_administracao"))
        self.assertContains(
            response, reverse("gestao:central_lista", args=["pagamentos"]),
        )

    def test_non_master_does_not_receive_global_financial_or_analytics_data(self):
        self.client.force_login(self.limited)
        response = self.client.get(reverse("gestao:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["operational"])
        self.assertNotContains(response, "Cobranças pagas")
        self.assertNotContains(response, "Atividade recente")
        self.assertNotContains(response, "Operação comercial")

    def test_non_master_only_sees_cards_for_granted_domains(self):
        access = AcessoModulo.objects.create(
            usuario=self.limited, modulo="usuarios", concedido_por=self.master,
            justificativa="Teste de escopo do dashboard",
        )
        permission, _ = Permissao.objects.get_or_create(
            codigo="usuarios.visualizar",
            defaults={"nome": "Visualizar usuários", "modulo": "gestao"},
        )
        ConcessaoPermissao.objects.create(
            acesso=access, usuario=self.limited, permissao=permission,
            concedida_por=self.master, justificativa="Teste de escopo",
        )
        self.client.force_login(self.limited)
        response = self.client.get(reverse("gestao:dashboard"))
        self.assertContains(response, "Usuários")
        self.assertContains(response, reverse("gestao:usuarios_lista"))
        self.assertNotContains(response, "Empresas ativas")
        self.assertNotContains(response, "Categorias de produto")

    def test_anonymous_and_user_without_management_access_are_blocked(self):
        self.assertEqual(self.client.get(reverse("gestao:dashboard")).status_code, 302)
        outsider = get_user_model().objects.create_user("dashboard-outsider", password="x")
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse("gestao:dashboard")).status_code, 403)

    def test_master_dashboard_has_bounded_query_count(self):
        self.client.force_login(self.master)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("gestao:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 45)
