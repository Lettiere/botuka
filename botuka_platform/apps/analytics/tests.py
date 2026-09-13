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

from .dashboard import dashboard_data, resolve_period
from .models import AnalyticsDailyCompany, AnalyticsEvent
from .services import register_event, resolve_company


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

    def test_email_contact_is_aggregated(self):
        event = register_event(
            self.request(),
            self.payload(
                event_name='company_contact',
                metadata={'method': 'email'},
            ),
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.metadata.get('method'), 'email')

        daily = AnalyticsDailyCompany.objects.get(
            empresa=self.company,
        )

        self.assertEqual(daily.email_clicks, 1)
        self.assertEqual(daily.visitors, 1)

    def test_dashboard_is_private_and_isolated_by_company(self):
        url = reverse('analytics:company_dashboard', args=[self.company.uuid])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.get(url, {'period': '30'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['empresa'], self.company)

    def test_dashboard_ecosystem_counts_are_complete_and_company_isolated(self):
        from datetime import timedelta

        from django.utils import timezone

        other_company = Empresa.objects.create(
            usuario_proprietario=self.other,
            nome_fantasia='Outra Empresa Analytics 360',
            status=Empresa.Status.ATIVA,
            ativo=True,
            perfil_publico=True,
            cidade=self.company.cidade,
            estado=self.company.estado,
        )

        def create_event(event_name, object_type, *, empresa=None):
            return AnalyticsEvent.objects.create(
                event_name=event_name,
                visitor_id=str(uuid.uuid4()),
                session_id=str(uuid.uuid4()),
                empresa=empresa or self.company,
                object_type=object_type,
                object_id=uuid.uuid4(),
                path='/analytics/teste/',
                dedupe_key=str(uuid.uuid4()),
            )

        expected_events = (
            ('view_company', 'company'),
            ('view_service', 'service'),
            ('view_item', 'product'),
            ('view_content', 'article'),
            ('view_content', 'tourism_place'),
            ('view_content', 'tourism_guide'),
            ('view_content', 'sports_team'),
            ('view_content', 'sports_athlete'),
            ('view_event', 'event'),
            ('view_job', 'job'),
            ('generate_lead', 'appointment'),
            ('ad_impression', 'ad_campaign'),
            ('ad_click', 'ad_campaign'),
        )

        for event_name, object_type in expected_events:
            create_event(event_name, object_type)

        # Estes eventos jamais podem aparecer no dashboard de self.company.
        create_event('view_company', 'company', empresa=other_company)
        create_event('view_content', 'article', empresa=other_company)
        create_event('generate_lead', 'appointment', empresa=other_company)
        create_event('ad_impression', 'ad_campaign', empresa=other_company)
        create_event('ad_click', 'ad_campaign', empresa=other_company)

        today = timezone.localdate()

        data = dashboard_data(
            self.company,
            today,
            today,
            today - timedelta(days=1),
            today - timedelta(days=1),
        )

        content = dict(data['content_metrics'])

        self.assertEqual(content['Perfil da empresa'], 1)
        self.assertEqual(content['Serviços'], 1)
        self.assertEqual(content['Produtos'], 1)
        self.assertEqual(content['Notícias'], 1)
        self.assertEqual(content['Turismo'], 2)
        self.assertEqual(content['Esportes'], 2)
        self.assertEqual(content['Eventos'], 1)
        self.assertEqual(content['Vagas'], 1)
        self.assertEqual(content['Agendamentos gerados'], 1)

        self.assertEqual(
            data['advertising_metrics'],
            {
                'impressions': 1,
                'clicks': 1,
            },
        )

    def test_resolve_company_for_article_requires_single_principal_company(self):
        from django.utils import timezone
        from apps.news.models import Artigo, ArtigoFonte, CategoriaNoticia

        categoria = CategoriaNoticia.objects.create(
            nome='Analytics 360',
            slug='analytics-360',
        )

        artigo = Artigo.objects.create(
            autor=self.owner,
            categoria=categoria,
            titulo='Artigo Analytics 360',
            slug='artigo-analytics-360',
            conteudo='Conteúdo de teste.',
        )

        fonte = ArtigoFonte.objects.create(
            artigo=artigo,
            organizacao=self.company,
            titulo='Fonte principal',
            url='https://example.com/fonte-principal',
            data_acesso=timezone.localdate(),
            principal=True,
            ativo=True,
        )

        self.assertEqual(
            resolve_company('article', artigo.uuid),
            self.company,
        )

        second_company = Empresa.objects.create(
            usuario_proprietario=self.other,
            nome_fantasia='Empresa Analytics 2',
            status=Empresa.Status.ATIVA,
            ativo=True,
            perfil_publico=True,
            cidade=self.company.cidade,
            estado=self.company.estado,
        )

        ArtigoFonte.objects.create(
            artigo=artigo,
            organizacao=second_company,
            titulo='Segunda fonte principal',
            url='https://example.com/segunda-fonte',
            data_acesso=timezone.localdate(),
            principal=True,
            ativo=True,
        )

        self.assertIsNone(
            resolve_company('article', artigo.uuid)
        )

        fonte.principal = False
        fonte.save(update_fields=['principal'])

        self.assertEqual(
            resolve_company('article', artigo.uuid),
            second_company,
        )

    def test_resolve_company_for_tourism_place_uses_responsible_company_only(self):
        from apps.tourism.models import LocalTuristico

        local = LocalTuristico.objects.create(
            usuario_criador=self.owner,
            usuario_atualizador=self.owner,
            nome='Local Analytics 360',
            slug='local-analytics-360',
            descricao_curta='Local de teste.',
            descricao_completa='Descrição completa do local.',
            empresa_responsavel=self.company,
        )

        self.assertEqual(
            resolve_company('tourism_place', local.uuid),
            self.company,
        )

        local.empresa_responsavel = None
        local.save(update_fields=['empresa_responsavel'])

        self.assertIsNone(
            resolve_company('tourism_place', local.uuid)
        )

    def test_resolve_company_for_tourism_guide_company_and_sports(self):
        from apps.tourism.models import GuiaTuristico, EmpresaTuristica
        from apps.sports.models import OrganizacaoEsportiva

        guia = GuiaTuristico.objects.create(
            usuario_criador=self.owner,
            usuario_atualizador=self.owner,
            tipo=GuiaTuristico.Tipo.PJ,
            usuario=self.owner,
            empresa=self.company,
            slug='guia-analytics-360',
            nome_profissional='Guia Analytics',
            apresentacao='Guia de teste.',
        )

        turismo_tipo = EmpresaTuristica._meta.get_field(
            'tipo_atuacao'
        ).choices[0][0]

        empresa_turistica = EmpresaTuristica.objects.create(
            usuario_criador=self.owner,
            usuario_atualizador=self.owner,
            empresa=self.company,
            tipo_atuacao=turismo_tipo,
        )

        sports_tipo = OrganizacaoEsportiva._meta.get_field(
            'tipo'
        ).choices[0][0]

        organizacao = OrganizacaoEsportiva.objects.create(
            empresa=self.company,
            usuario_responsavel=self.owner,
            tipo=sports_tipo,
            nome='Organização Analytics',
            slug='organizacao-analytics',
            cidade='Botucatu',
        )

        self.assertEqual(
            resolve_company('tourism_guide', guia.uuid),
            self.company,
        )
        self.assertEqual(
            resolve_company('tourism_company', empresa_turistica.uuid),
            self.company,
        )
        self.assertEqual(
            resolve_company('sports_org', organizacao.uuid),
            self.company,
        )

    def test_resolve_company_for_appointment_uses_service_company(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.agenda.models import (
            AgendaProfissional,
            AgendaProfissionalServico,
            Agendamento,
        )
        from apps.services.models import Servico

        prestador_tipo = 'EMPRESA'

        servico = Servico.objects.create(
            usuario_responsavel=self.owner,
            empresa=self.company,
            prestador_tipo=prestador_tipo,
            titulo='Serviço Analytics 360',
            slug='servico-analytics-360',
        )

        from apps.organizations.models import EmpresaUsuario

        empresa_usuario, _ = EmpresaUsuario.objects.get_or_create(
            empresa=self.company,
            usuario=self.owner,
            defaults={
                'funcao': 'PROPRIETARIO',
                'proprietario': True,
                'ativo': True,
            },
        )

        profissional = AgendaProfissional.objects.create(
            empresa_usuario=empresa_usuario,
        )

        profissional_servico = AgendaProfissionalServico.objects.create(
            profissional=profissional,
            servico=servico,
            duracao_minutos=60,
        )

        inicio = timezone.now() + timedelta(days=1)

        agendamento = Agendamento(
            profissional_servico=profissional_servico,
            cliente=self.other,
            inicio=inicio,
            fim=inicio + timedelta(minutes=60),
        )
        Agendamento.objects.bulk_create([agendamento])

        self.assertEqual(
            resolve_company('appointment', agendamento.uuid),
            self.company,
        )

    def test_resolve_company_for_sports_team_and_athlete(self):
        from apps.sports.models import (
            Atleta,
            Equipe,
            Modalidade,
            OrganizacaoEsportiva,
        )

        modalidade = Modalidade.objects.create(
            nome='Modalidade Analytics 360',
        )

        organizacao = OrganizacaoEsportiva.objects.create(
            empresa=self.company,
            usuario_responsavel=self.owner,
            tipo=OrganizacaoEsportiva.Tipo.CLUBE,
            nome='Clube Analytics 360',
            cidade='Botucatu',
        )

        equipe = Equipe.objects.create(
            organizacao=organizacao,
            modalidade=modalidade,
            nome='Equipe Analytics 360',
            cidade='Botucatu',
        )

        atleta = Atleta.objects.create(
            equipe=equipe,
            nome_publico='Atleta Analytics 360',
            modalidade=modalidade,
            publico=True,
        )

        self.assertEqual(
            resolve_company('sports_team', equipe.uuid),
            self.company,
        )

        self.assertEqual(
            resolve_company('sports_athlete', atleta.uuid),
            self.company,
        )

        atleta_sem_equipe = Atleta.objects.create(
            nome_publico='Atleta Sem Equipe Analytics',
            modalidade=modalidade,
            publico=True,
        )

        self.assertIsNone(
            resolve_company(
                'sports_athlete',
                atleta_sem_equipe.uuid,
            )
        )

    def test_custom_period_rejects_future_or_oversized_ranges(self):
        period, start, end, _, _ = resolve_period({
            'period': 'custom', 'start': '2020-01-01', 'end': '2030-01-01',
        })
        self.assertEqual(period, '30')
        self.assertEqual((end - start).days, 29)
