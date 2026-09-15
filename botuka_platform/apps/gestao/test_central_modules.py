from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.analytics.models import AnalyticsEvent
from apps.core.models import ConfiguracaoSistema
from apps.gestao.central_views import _models
from apps.locations.models import Bairro, Cidade, Estado, Pais


class CentralModulesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.master = User.objects.create_superuser('central-master', password='x')
        cls.outsider = User.objects.create_user('central-outsider', password='x')

    def test_all_catalog_urls_are_master_only_and_render(self):
        for kind in _models():
            url = reverse('gestao:central_lista', args=[kind])
            self.client.force_login(self.outsider)
            self.assertEqual(self.client.get(url).status_code, 403, kind)
            self.client.force_login(self.master)
            self.assertEqual(self.client.get(url).status_code, 200, kind)
        self.assertEqual(self.client.get(reverse('gestao:central_lista', args=['inexistente'])).status_code, 404)

    def test_analytics_search_filter_detail_and_pagination(self):
        AnalyticsEvent.objects.bulk_create([
            AnalyticsEvent(
                event_name='company_view' if index == 0 else 'page_view',
                visitor_id=f'visitor-{index}', session_id=f'session-{index}',
                path=f'/empresa/{index}', source='search', dedupe_key=f'key-{index}',
            ) for index in range(26)
        ])
        self.client.force_login(self.master)
        url = reverse('gestao:central_lista', args=['analytics-eventos'])
        response = self.client.get(url, {'q': 'company_view'})
        self.assertContains(response, 'company_view')
        response = self.client.get(url)
        self.assertTrue(response.context['page_obj'].has_next())
        event = AnalyticsEvent.objects.first()
        self.assertEqual(self.client.get(reverse(
            'gestao:central_detalhe', args=['analytics-eventos', event.pk],
        )).status_code, 200)

    def test_read_only_catalog_has_no_mutation_routes(self):
        names = {
            getattr(pattern, 'name', None)
            for pattern in __import__('apps.gestao.urls', fromlist=['urlpatterns']).urlpatterns
        }
        self.assertNotIn('central_editar', names)
        self.assertNotIn('central_excluir', names)
        self.assertNotIn('central_status', names)

    def test_catalog_configuration_references_real_fields(self):
        for kind, (model, _title, _section, search, columns, filter_field) in _models().items():
            for configured in (*search, *columns):
                current_model = model
                parts = configured.replace('.', '__').split('__')
                for index, part in enumerate(parts):
                    field_names = {field.name for field in current_model._meta.fields}
                    self.assertIn(part, field_names, f'{kind}: {configured}')
                    field = current_model._meta.get_field(part)
                    if index < len(parts) - 1:
                        self.assertTrue(field.is_relation, f'{kind}: {configured}')
                        current_model = field.related_model
            if filter_field:
                self.assertIn(filter_field, {field.name for field in model._meta.fields}, kind)


class LocalityManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.master = User.objects.create_superuser('location-master', password='x')
        cls.country = Pais.objects.create(nome='Brasil', codigo_iso_2='BR', codigo_iso_3='BRA')
        cls.state = Estado.objects.create(pais=cls.country, nome='São Paulo', sigla='SP')
        cls.city = Cidade.objects.create(estado=cls.state, nome='Botucatu')
        cls.neighborhood = Bairro.objects.create(cidade=cls.city, nome='Centro')

    def test_locality_crud_detail_search_and_soft_status(self):
        self.client.force_login(self.master)
        for slug, instance in (
            ('paises', self.country), ('estados', self.state),
            ('cidades', self.city), ('bairros', self.neighborhood),
        ):
            listing = reverse(f'gestao:{slug}_lista')
            self.assertContains(self.client.get(listing, {'q': str(instance)}), str(instance))
            detail = reverse(f'gestao:{slug}_detalhe', args=[instance.pk])
            status = reverse(f'gestao:{slug}_status', args=[instance.pk])
            self.assertEqual(self.client.get(detail).status_code, 200)
            self.assertEqual(self.client.get(status).status_code, 405)
            self.assertRedirects(self.client.post(status), detail)
            instance.refresh_from_db()
            self.assertFalse(instance.ativo)
            self.assertIsNotNone(instance.removido_em)

    def test_location_creation_validation_and_hierarchy(self):
        self.client.force_login(self.master)
        url = reverse('gestao:estados_novo')
        self.assertEqual(self.client.post(url, {'nome': '', 'sigla': ''}).status_code, 200)
        response = self.client.post(url, {
            'pais': self.country.pk, 'nome': 'Paraná', 'sigla': 'PR',
            'codigo_ibge': '41', 'ativo': 'on',
        })
        self.assertRedirects(response, reverse('gestao:estados_lista'))
        self.assertTrue(Estado.objects.filter(nome='Paraná', pais=self.country).exists())


class SystemManagementTests(TestCase):
    def test_sensitive_configuration_value_is_not_rendered(self):
        master = get_user_model().objects.create_superuser('system-master', password='x')
        config = ConfiguracaoSistema.objects.create(
            chave='INTEGRATION_API_TOKEN', valor='segredo-que-nao-pode-vazar',
            descricao='Credencial protegida',
        )
        self.client.force_login(master)
        response = self.client.get(reverse('gestao:configuracoes_editar', args=[config.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'segredo-que-nao-pode-vazar')
        self.assertContains(response, 'Valor protegido')
