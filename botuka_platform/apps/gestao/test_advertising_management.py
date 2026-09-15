from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.advertising.models import Campanha, PlanoPublicitario, Posicionamento
from apps.gestao.central_views import (
    ADVERTISING_KINDS,
    _ADVERTISING_WORKFLOW_ROUTES,
    _models,
)
from apps.organizations.models import Empresa


class AdvertisingManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.master = User.objects.create_superuser('advertising-master', password='x')
        cls.outsider = User.objects.create_user('advertising-outsider', password='x')
        cls.company = Empresa.objects.create(
            nome_fantasia='Anunciante Gestão', usuario_proprietario=cls.outsider,
        )
        cls.position = Posicionamento.objects.create(
            nome='Takeover Home', codigo='takeover-gestao', contexto='home',
            aceita_takeover=True,
        )
        cls.plan = PlanoPublicitario.objects.create(
            nome='Impacto Gestão', nivel=PlanoPublicitario.Nivel.ZERO,
            preco_diario=Decimal('100'), prioridade=50, exclusivo=True,
        )
        now = timezone.now()
        cls.campaign = Campanha.objects.create(
            empresa=cls.company, plano=cls.plan, nome='Campanha Gestão',
            inicio=now, fim=now + timedelta(days=2), criado_por=cls.outsider,
        )
        cls.campaign.posicionamentos.add(cls.position)

    def test_all_real_advertising_domains_are_master_only_and_read_only(self):
        expected = {
            'planos-publicitarios', 'posicionamentos-publicitarios', 'campanhas',
            'segmentacoes', 'criativos', 'contratacoes', 'entregas',
            'auditoria-publicidade',
        }
        self.assertEqual(set(ADVERTISING_KINDS), expected)
        self.assertTrue(expected.issubset(_models()))
        for kind in ADVERTISING_KINDS:
            url = reverse('gestao:central_lista', args=[kind])
            self.client.force_login(self.outsider)
            self.assertEqual(self.client.get(url).status_code, 403, kind)
            self.client.force_login(self.master)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, kind)
            self.assertTrue(response.context['read_only'], kind)

    def test_levels_fields_filters_details_and_real_workflow_links(self):
        self.client.force_login(self.master)
        plans = self.client.get(reverse(
            'gestao:central_lista', args=['planos-publicitarios'],
        ), {'q': 'Impacto', 'status': '1'})
        self.assertContains(plans, 'Impacto Gestão')
        self.assertContains(plans, '100,00')
        campaign = self.client.get(reverse(
            'gestao:central_lista', args=['campanhas'],
        ), {'q': self.company.nome_fantasia})
        self.assertContains(campaign, self.campaign.nome)
        self.assertContains(campaign, self.company.nome_fantasia)
        detail = self.client.get(reverse(
            'gestao:central_detalhe', args=['campanhas', self.campaign.pk],
        ))
        self.assertEqual(detail.status_code, 200)
        for kind, (route, args, _capability) in _ADVERTISING_WORKFLOW_ROUTES.items():
            response = self.client.get(reverse('gestao:central_lista', args=[kind]))
            self.assertContains(response, reverse(route, args=args))
