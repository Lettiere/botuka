from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.gestao.central_views import (
    BUSINESS_KINDS,
    _BUSINESS_WORKFLOW_ROUTES,
    _models,
)
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Empresa
from apps.products.models import Produto


class BusinessManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.master = User.objects.create_superuser('business-master', password='x')
        cls.outsider = User.objects.create_user('business-outsider', password='x')
        country = Pais.objects.create(nome='Brasil Negócios', codigo_iso_2='BN', codigo_iso_3='BNG')
        state = Estado.objects.create(pais=country, nome='Estado Negócios', sigla='NG')
        city = Cidade.objects.create(estado=state, nome='Cidade Negócios')
        cls.company = Empresa.objects.create(
            usuario_proprietario=cls.master, nome_fantasia='Empresa Proprietária',
            cidade=city, estado=state, status=Empresa.Status.ATIVA,
        )
        cls.product = Produto.objects.create(
            nome='Produto empresarial', categoria='Comércio',
            descricao_curta='Resumo comercial',
            descricao_completa='<p>Corpo pesado do produto</p>',
            preco=Decimal('125.50'), titular_tipo=Produto.TitularTipo.EMPRESA,
            criador_registro=cls.master, proprietario=cls.master,
            responsavel=cls.master, empresa_proprietaria=cls.company,
        )

    def test_real_business_domains_are_global_and_master_only(self):
        expected = {
            'produtos', 'servicos', 'profissionais-agenda', 'servicos-agenda',
            'agendamentos', 'vagas',
        }
        self.assertEqual(set(BUSINESS_KINDS), expected)
        self.assertTrue(expected.issubset(_models()))
        for kind in BUSINESS_KINDS:
            url = reverse('gestao:central_lista', args=[kind])
            self.client.force_login(self.outsider)
            self.assertEqual(self.client.get(url).status_code, 403, kind)
            self.client.force_login(self.master)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, kind)
            self.assertTrue(response.context['read_only'], kind)

    def test_real_operational_links_and_scoped_agenda_notice(self):
        self.client.force_login(self.master)
        for kind, (route, args, _capability) in _BUSINESS_WORKFLOW_ROUTES.items():
            response = self.client.get(reverse('gestao:central_lista', args=[kind]))
            self.assertContains(response, reverse(route, args=args))
        response = self.client.get(reverse('gestao:central_lista', args=['agendamentos']))
        self.assertContains(response, 'contexto de empresa na Agenda')
        self.assertFalse(response.context['workflow_url'])

    def test_product_company_search_status_detail_and_safe_payload(self):
        self.client.force_login(self.master)
        url = reverse('gestao:central_lista', args=['produtos'])
        response = self.client.get(url, {
            'q': self.company.nome_fantasia,
            'status': Produto.Status.RASCUNHO,
        })
        self.assertContains(response, self.product.nome)
        self.assertContains(response, self.company.nome_fantasia)
        self.assertContains(response, '125,50')
        self.assertNotContains(response, 'Corpo pesado do produto')
        detail = self.client.get(reverse(
            'gestao:central_detalhe', args=['produtos', self.product.pk],
        ))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self.company.nome_fantasia)

    def test_product_list_query_count_does_not_grow_per_row(self):
        self.client.force_login(self.master)
        url = reverse('gestao:central_lista', args=['produtos'])
        with CaptureQueriesContext(connection) as first:
            self.client.get(url)
        Produto.objects.bulk_create([
            Produto(
                nome=f'Produto {index}', slug=f'produto-negocio-{index}',
                categoria='Comércio', descricao_curta='Resumo',
                descricao_completa='<p>Descrição</p>', preco=Decimal('10.00'),
                titular_tipo=Produto.TitularTipo.EMPRESA,
                criador_registro=self.master, proprietario=self.master,
                responsavel=self.master, empresa_proprietaria=self.company,
            ) for index in range(6)
        ])
        with CaptureQueriesContext(connection) as many:
            self.client.get(url)
        self.assertLessEqual(len(many), len(first) + 1)
