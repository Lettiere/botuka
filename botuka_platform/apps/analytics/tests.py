import json
import time
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.organizations.models import Empresa
from apps.locations.models import Cidade, Estado, Pais

from .dashboard import resolve_period
from .models import AnalyticsDailyCompany, AnalyticsEvent
from .services import register_event


class AnalyticsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user('analytics-owner', password='safe-pass')
        cls.other = user_model.objects.create_user('analytics-other', password='safe-pass')
        pais = Pais.objects.create(nome='Brasil Analytics', codigo_iso_2='AN', codigo_iso_3='ANA')
        estado = Estado.objects.create(pais=pais, nome='São Paulo Analytics', sigla='AY')
        cidade = Cidade.objects.create(estado=estado, nome='Botucatu Analytics')
        cls.company = Empresa.objects.create(
            usuario_proprietario=cls.owner,
            nome_fantasia='Empresa Analytics',
            status=Empresa.Status.ATIVA,
            ativo=True,
            perfil_publico=True,
            cidade=cidade,
            estado=estado,
        )

    def setUp(self):
        self.factory = RequestFactory()

    def payload(self, **values):
        payload = {
            'event_name': 'view_company',
            'visitor_id': str(uuid.uuid4()),
            'session_id': str(uuid.uuid4()),
            'object_type': 'company',
            'object_id': str(self.company.uuid),
            'path': '/empresas/empresa-analytics/',
            'dedupe_key': str(uuid.uuid4()),
            'metadata': {'search_term': 'advocacia', 'email': 'nao-persistir@example.com'},
            'attribution': {'source': 'google', 'medium': 'organic', 'gclid': 'click-id'},
        }
        payload.update(values)
        return payload

    def request(self, user=None, agent='Mozilla/5.0'):
        request = self.factory.post('/api/analytics/events/', HTTP_USER_AGENT=agent)
        request.user = user or AnonymousUser()
        return request

    def test_event_is_resolved_server_side_sanitized_and_aggregated(self):
        event = register_event(self.request(), self.payload())
        self.assertEqual(event.empresa, self.company)
        self.assertEqual(event.gclid, 'click-id')
        self.assertNotIn('email', event.metadata)
        daily = AnalyticsDailyCompany.objects.get(empresa=self.company)
        self.assertEqual((daily.views, daily.visitors, daily.search_views), (1, 1, 1))

    def test_deduplication_and_unique_visitor_are_not_inflated(self):
        visitor = str(uuid.uuid4())
        first = self.payload(visitor_id=visitor, dedupe_key='same-event')
        self.assertIsNotNone(register_event(self.request(), first))
        self.assertIsNone(register_event(self.request(), first))
        second = self.payload(visitor_id=visitor)
        register_event(self.request(), second)
        daily = AnalyticsDailyCompany.objects.get(empresa=self.company)
        self.assertEqual(daily.views, 2)
        self.assertEqual(daily.visitors, 1)

    def test_invalid_uuid_bots_staff_and_owner_are_discarded(self):
        self.assertIsNone(register_event(self.request(), self.payload(object_id='invalid')))
        self.assertIsNone(register_event(self.request(agent='Googlebot'), self.payload()))
        self.owner.is_staff = True
        self.owner.save(update_fields=['is_staff'])
        self.assertIsNone(register_event(self.request(self.owner), self.payload()))
        self.owner.is_staff = False
        self.owner.save(update_fields=['is_staff'])
        self.assertIsNone(register_event(self.request(self.owner), self.payload()))
        self.assertEqual(AnalyticsEvent.objects.count(), 0)

    def test_endpoint_requires_valid_analytics_consent(self):
        url = reverse('analytics:collect')
        response = self.client.post(url, data=json.dumps(self.payload()), content_type='application/json')
        self.assertEqual(response.status_code, 202)
        self.assertFalse(response.json()['accepted'])
        self.client.cookies['botuka_consent'] = json.dumps({
            'version': settings.CONSENT_POLICY_VERSION,
            'expiresAt': time.time() * 1000 + 60000,
            'analytics': True,
        })
        response = self.client.post(url, data=json.dumps(self.payload()), content_type='application/json')
        self.assertTrue(response.json()['accepted'])

    def test_dashboard_is_private_and_isolated_by_company(self):
        url = reverse('analytics:company_dashboard', args=[self.company.uuid])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.get(url, {'period': '30'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['empresa'], self.company)

    def test_custom_period_rejects_future_or_oversized_ranges(self):
        period, start, end, _, _ = resolve_period({
            'period': 'custom', 'start': '2020-01-01', 'end': '2030-01-01',
        })
        self.assertEqual(period, '30')
        self.assertEqual((end - start).days, 29)
