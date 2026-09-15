from datetime import timedelta
from decimal import Decimal
import json
import time
from io import BytesIO
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.template import RequestContext, Template
from django.test import Client, RequestFactory, TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import Empresa, EmpresaUsuario
from apps.analytics.models import AnalyticsEvent
from apps.payments.models import Cobranca
from apps.payments.services import processar_pagamento
from apps.taxonomy.models import Categoria, Subcategoria

from .forms import CriativoForm, SegmentacaoForm
from .models import (AuditoriaPublicidade, Campanha, CampanhaSegmentacao, Criativo,
                     EntregaPublicidade, PlanoPublicitario, Posicionamento)
from .services import (aprovar_campanha, cancelar_campanha, contratar_campanha,
                       entregar_publicidade, moderar_campanha,
                       sincronizar_status_pagamento)


class AdvertisingFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('adv-owner', password='x')
        cls.other = get_user_model().objects.create_user('adv-other', password='x')
        cls.master = get_user_model().objects.create_superuser('adv-master', password='x')
        cls.empresa = Empresa.objects.create(nome_fantasia='Anunciante', usuario_proprietario=cls.owner)
        cls.categoria = Categoria.objects.create(nome='Restaurantes publicidade')
        cls.subcategoria = Subcategoria.objects.create(categoria=cls.categoria, nome='Pizzaria publicidade')
        cls.posicao = Posicionamento.objects.create(codigo='home-topo', nome='Topo', contexto='home', aceita_takeover=True)
        cls.plano = PlanoPublicitario.objects.create(nome='Segmentado', nivel=3, preco_diario=Decimal('12.50'), prioridade=10, impressoes_por_usuario_dia=2)

    def campanha(self, plano=None):
        now = timezone.now()
        campanha = Campanha.objects.create(empresa=self.empresa, plano=plano or self.plano, nome='Campanha', inicio=now - timedelta(hours=1), fim=now + timedelta(days=2), criado_por=self.owner)
        campanha.posicionamentos.add(self.posicao)
        Criativo.objects.create(campanha=campanha, tipo=Criativo.Tipo.TEXTO, titulo='Oferta', texto='Compre agora', url_destino='https://example.com')
        segmentacao = CampanhaSegmentacao.objects.create(campanha=campanha)
        segmentacao.categorias.add(self.categoria)
        return campanha

    def ativar(self, campanha):
        contratacao = contratar_campanha(campanha_id=campanha.pk, usuario=self.owner)
        processar_pagamento(cobranca_id=contratacao.cobranca_id, idempotency_key=f'pay-{campanha.pk}')
        sincronizar_status_pagamento(campanha_id=campanha.pk)
        return aprovar_campanha(campanha_id=campanha.pk, usuario=self.master)

    def test_calculo_contratacao_ignora_total_do_cliente(self):
        campanha = self.campanha()
        contrato = contratar_campanha(campanha_id=campanha.pk, usuario=self.owner)
        self.assertEqual(contrato.quantidade_dias, 3)
        self.assertEqual(contrato.valor_total, Decimal('37.50'))
        self.assertEqual(contrato.cobranca.valor_total, Decimal('37.50'))
        self.assertEqual(contrato.cobranca.origem, Cobranca.Origem.PUBLICIDADE)
        self.assertTrue(contrato.cobranca.external_reference.startswith('advertising:'))

    def test_outra_empresa_nao_contrata(self):
        with self.assertRaises(PermissionDenied):
            contratar_campanha(campanha_id=self.campanha().pk, usuario=self.other)

    def test_campanha_nao_paga_nao_ativa_nem_entrega(self):
        campanha = self.campanha()
        contratar_campanha(campanha_id=campanha.pk, usuario=self.owner)
        campanha = aprovar_campanha(campanha_id=campanha.pk, usuario=self.master)
        self.assertEqual(campanha.status, Campanha.Status.APROVADA)
        self.assertIsNone(entregar_publicidade(posicionamento_codigo='home-topo', visitante_id='v1', contexto='home', categoria=self.categoria))

    def test_paga_sem_aprovacao_nao_entrega(self):
        campanha = self.campanha()
        contrato = contratar_campanha(campanha_id=campanha.pk, usuario=self.owner)
        processar_pagamento(cobranca_id=contrato.cobranca_id, idempotency_key='paga-sem-aprovacao')
        sincronizar_status_pagamento(campanha_id=campanha.pk)
        self.assertIsNone(entregar_publicidade(posicionamento_codigo='home-topo', visitante_id='v2', contexto='home', categoria=self.categoria))

    def test_entrega_segmentada_rotacao_e_frequencia(self):
        campanha = self.ativar(self.campanha())
        self.assertEqual(campanha.contratacao.cobranca.pagamentos.get().gateway, 'c6')
        self.assertIsNotNone(entregar_publicidade(posicionamento_codigo='home-topo', visitante_id='v3', contexto='home', categoria=self.categoria))
        self.assertIsNotNone(entregar_publicidade(posicionamento_codigo='home-topo', visitante_id='v3', contexto='home', categoria=self.categoria))
        self.assertIsNone(entregar_publicidade(posicionamento_codigo='home-topo', visitante_id='v3', contexto='home', categoria=self.categoria))
        self.assertIsNone(entregar_publicidade(posicionamento_codigo='home-topo', visitante_id='v4', contexto='home', categoria=None))

    def test_fora_do_periodo_nao_entrega(self):
        campanha = self.ativar(self.campanha())
        futuro = campanha.fim + timedelta(seconds=1)
        self.assertIsNone(entregar_publicidade(posicionamento_codigo='home-topo', visitante_id='v5', contexto='home', categoria=self.categoria, agora=futuro))

    def test_prioridade_e_rotacao_por_menor_entrega(self):
        alta = PlanoPublicitario.objects.create(
            nome='Premium alto', nivel=1, preco_diario='20', prioridade=20,
            impressoes_por_usuario_dia=1,
        )
        baixa = PlanoPublicitario.objects.create(
            nome='Premium baixo', nivel=1, preco_diario='15', prioridade=5,
            impressoes_por_usuario_dia=1,
        )
        campanha_alta = self.ativar(self.campanha(alta))
        campanha_baixa = self.ativar(self.campanha(baixa))
        primeira = entregar_publicidade(
            posicionamento_codigo='home-topo', visitante_id='rotation', contexto='home')
        segunda = entregar_publicidade(
            posicionamento_codigo='home-topo', visitante_id='rotation', contexto='home')
        self.assertEqual(primeira.campanha, campanha_alta)
        self.assertEqual(segunda.campanha, campanha_baixa)

    def test_takeover_exige_exclusividade_e_posicao_compativel(self):
        with self.assertRaises(ValidationError):
            PlanoPublicitario.objects.create(nome='Takeover inválido', nivel=0, preco_diario=Decimal('100.00'), exclusivo=False)

    def test_pagamento_cancelado_nao_entrega(self):
        campanha = self.ativar(self.campanha())
        campanha.contratacao.cobranca.status = Cobranca.Status.CANCELADA
        campanha.contratacao.cobranca.cancelada_em = timezone.now()
        campanha.contratacao.cobranca.save(update_fields=['status', 'cancelada_em'])
        self.assertIsNone(entregar_publicidade(posicionamento_codigo='home-topo', visitante_id='v6', contexto='home', categoria=self.categoria))

    def test_aprovada_e_paga_em_qualquer_ordem_ativa(self):
        campanha = self.campanha()
        contrato = contratar_campanha(campanha_id=campanha.pk, usuario=self.owner)
        aprovar_campanha(campanha_id=campanha.pk, usuario=self.master)
        processar_pagamento(cobranca_id=contrato.cobranca_id, idempotency_key='approve-first')
        campanha = sincronizar_status_pagamento(campanha_id=campanha.pk)
        self.assertEqual(campanha.status, Campanha.Status.ATIVA)

    def test_conflito_exclusividade_e_limite(self):
        exclusive = PlanoPublicitario.objects.create(
            nome='Impacto', nivel=0, preco_diario=Decimal('100'), exclusivo=True,
        )
        contratar_campanha(campanha_id=self.campanha(exclusive).pk, usuario=self.owner)
        with self.assertRaises(ValidationError):
            contratar_campanha(campanha_id=self.campanha().pk, usuario=self.owner)

        Campanha.objects.update(status=Campanha.Status.CANCELADA)
        limited = PlanoPublicitario.objects.create(
            nome='Plus', nivel=2, preco_diario=Decimal('20'), limite_anunciantes=1,
        )
        contratar_campanha(campanha_id=self.campanha(limited).pk, usuario=self.owner)
        other_company = Empresa.objects.create(nome_fantasia='Segundo', usuario_proprietario=self.owner)
        candidate = self.campanha(limited)
        candidate.empresa = other_company
        candidate.save(update_fields=['empresa'])
        with self.assertRaises(ValidationError):
            contratar_campanha(campanha_id=candidate.pk, usuario=self.owner)

    def test_rejeicao_pausa_reativacao_cancelamento_e_auditoria(self):
        rejected = self.campanha()
        contratar_campanha(campanha_id=rejected.pk, usuario=self.owner)
        moderar_campanha(campanha_id=rejected.pk, usuario=self.master,
                         acao='REJEITAR', motivo='Criativo inadequado')
        rejected.refresh_from_db()
        self.assertEqual(rejected.status, Campanha.Status.REJEITADA)
        self.assertEqual(rejected.auditoria.latest('pk').detalhes['motivo'], 'Criativo inadequado')

        active = self.ativar(self.campanha())
        paused = moderar_campanha(campanha_id=active.pk, usuario=self.master, acao='PAUSAR')
        self.assertEqual(paused.status, Campanha.Status.PAUSADA)
        reactivated = moderar_campanha(campanha_id=active.pk, usuario=self.master, acao='REATIVAR')
        self.assertEqual(reactivated.status, Campanha.Status.ATIVA)

        draft = self.campanha()
        cancelar_campanha(campanha_id=draft.pk, usuario=self.owner, motivo='Desistência')
        self.assertTrue(AuditoriaPublicidade.objects.filter(campanha=draft, acao='CANCELADA').exists())

    def test_criativo_e_segmentacao_invalidos(self):
        self.assertFalse(CriativoForm(data={
            'tipo': 'HTML', 'titulo': 'X', 'texto': '<script>x</script>',
            'url_destino': 'https://example.com', 'ativo': True,
        }).is_valid())
        self.assertFalse(SegmentacaoForm(data={'termos': 'não-é-lista'}).is_valid())

    def test_criativo_textual_rejeita_html_e_video_aceita_mp4_webm_configurados(self):
        campaign = self.campanha()
        self.assertFalse(CriativoForm(data={
            'tipo': Criativo.Tipo.TEXTO, 'titulo': 'Texto',
            'texto': '<strong>Oferta</strong>',
            'url_destino': 'https://example.com', 'ativo': True,
        }, campanha=campaign).is_valid())
        for extension, content_type in (('mp4', 'video/mp4'), ('webm', 'video/webm')):
            form = CriativoForm(data={
                'tipo': Criativo.Tipo.VIDEO, 'titulo': f'Vídeo {extension}',
                'url_destino': 'https://example.com', 'ativo': True,
            }, files={
                'video': SimpleUploadedFile(
                    f'criativo.{extension}', b'video-test', content_type=content_type,
                ),
            }, campanha=campaign)
            self.assertTrue(form.is_valid(), form.errors)

    def test_selecao_publica_nao_adiciona_queries_por_campanha(self):
        self.ativar(self.campanha())
        with CaptureQueriesContext(connection) as uma:
            entregar_publicidade(
                posicionamento_codigo='home-topo', visitante_id='query-one',
                contexto='home', categoria=self.categoria,
            )
        for index in range(4):
            campaign = self.campanha(PlanoPublicitario.objects.create(
                nome=f'Plano query {index}', nivel=1,
                preco_diario='10', prioridade=index,
            ))
            self.ativar(campaign)
        with CaptureQueriesContext(connection) as varias:
            entregar_publicidade(
                posicionamento_codigo='home-topo', visitante_id='query-many',
                contexto='home', categoria=self.categoria,
            )
        self.assertLessEqual(len(varias), len(uma) + 1)

    def _request(self, *, authenticated=False, analytics=False):
        request = RequestFactory().get('/publicidade-teste/')
        SessionMiddleware(lambda value: None).process_request(request)
        request.session.save()
        request.user = self.owner if authenticated else AnonymousUser()
        if analytics:
            consent = {'version': settings.CONSENT_POLICY_VERSION, 'analytics': True,
                       'expiresAt': (time.time() + 3600) * 1000}
            request.COOKIES['botuka_consent'] = quote(json.dumps(consent))
        return request

    def test_componente_takeover_impressao_unica_e_visitantes(self):
        takeover = PlanoPublicitario.objects.create(
            nome='Takeover público', nivel=0, preco_diario='100', exclusivo=True,
            impressoes_por_usuario_dia=1, duracao_segundos=6,
        )
        campanha = self.ativar(self.campanha(takeover))
        request = self._request(analytics=True)
        source = "{% load advertising_tags %}{% advertising_slot 'leaderboard' position_code='home-topo' page_context='home' %}{% advertising_slot 'leaderboard' position_code='home-topo' page_context='home' %}"
        rendered = Template(source).render(RequestContext(request, {'categoria': self.categoria}))
        self.assertIn('data-ad-takeover', rendered)
        self.assertIn('data-duration="6"', rendered)
        self.assertEqual(EntregaPublicidade.objects.filter(campanha=campanha).count(), 1)
        self.assertEqual(AnalyticsEvent.objects.filter(event_name='ad_impression').count(), 1)

        authenticated = self._request(authenticated=True)
        rendered = Template(source.split('{% advertising_slot')[0] + "{% advertising_slot 'leaderboard' position_code='home-topo' page_context='home' %}").render(
            RequestContext(authenticated, {'categoria': self.categoria}))
        self.assertIn('data-ad-takeover', rendered)

    def test_clique_redireciona_com_seguranca_e_e_idempotente(self):
        campanha = self.ativar(self.campanha())
        entrega = entregar_publicidade(
            posicionamento_codigo='home-topo', visitante_id='click-visitor',
            contexto='home', categoria=self.categoria,
        )
        consent = {'version': settings.CONSENT_POLICY_VERSION, 'analytics': True,
                   'expiresAt': (time.time() + 3600) * 1000}
        self.client.cookies['botuka_consent'] = quote(json.dumps(consent))
        url = reverse('advertising_public:entrega_clique', args=[entrega.uuid])
        self.assertRedirects(self.client.get(url), 'https://example.com', fetch_redirect_response=False)
        self.assertRedirects(self.client.get(url), 'https://example.com', fetch_redirect_response=False)
        self.assertEqual(AnalyticsEvent.objects.filter(event_name='ad_click').count(), 1)
        campanha.criativos.update(url_destino='javascript:alert(1)')
        self.assertEqual(self.client.get(url).status_code, 404)


class AdvertisingAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('flow-owner', password='x')
        cls.member = get_user_model().objects.create_user('flow-member', password='x')
        cls.outsider = get_user_model().objects.create_user('flow-outsider', password='x')
        cls.master = get_user_model().objects.create_superuser('flow-master', password='x')
        cls.empresa = Empresa.objects.create(nome_fantasia='Empresa Flow', usuario_proprietario=cls.owner)
        cls.other_company = Empresa.objects.create(nome_fantasia='Empresa Fora', usuario_proprietario=cls.outsider)
        EmpresaUsuario.objects.create(empresa=cls.empresa, usuario=cls.member, ativo=True, administrador=True)
        cls.plan = PlanoPublicitario.objects.create(nome='Standard Flow', nivel=4, preco_diario='10')
        cls.position = Posicionamento.objects.create(codigo='flow', nome='Flow', contexto='home')
        now = timezone.now()
        cls.campaign = Campanha.objects.create(empresa=cls.empresa, plano=cls.plan, nome='Escopo',
                                               inicio=now, fim=now + timedelta(days=2), criado_por=cls.owner)
        cls.campaign.posicionamentos.add(cls.position)

    def test_usuario_sem_vinculo_nao_acessa_e_master_acessa(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse('advertising:campanha_detalhe', args=[self.campaign.uuid])).status_code, 403)
        self.client.force_login(self.master)
        self.assertEqual(self.client.get(reverse('advertising:campanha_detalhe', args=[self.campaign.uuid])).status_code, 200)
        self.assertContains(self.client.get(reverse('advertising:campanha_lista')), 'Escopo')

    def test_post_forjado_de_empresa_rejeitado_e_vinculo_aceito(self):
        now = timezone.now()
        data = {'empresa': self.other_company.pk, 'plano': self.plan.pk, 'nome': 'Forjada',
                'inicio': now.strftime('%Y-%m-%dT%H:%M'),
                'fim': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
                'posicionamentos': [self.position.pk]}
        self.client.force_login(self.member)
        response = self.client.post(reverse('advertising:campanha_criar'), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Campanha.objects.filter(nome='Forjada').exists())
        data['empresa'] = self.empresa.pk
        response = self.client.post(reverse('advertising:campanha_criar'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Campanha.objects.get(nome='Forjada').empresa, self.empresa)

    def test_mutacoes_administrativas_rejeitam_get_e_exigem_csrf(self):
        self.client.force_login(self.master)
        mutation_urls = (
            reverse('advertising:campanha_criativo', args=[self.campaign.uuid]),
            reverse('advertising:campanha_segmentar', args=[self.campaign.uuid]),
            reverse('advertising:campanha_contratar', args=[self.campaign.uuid]),
            reverse('advertising:campanha_cancelar', args=[self.campaign.uuid]),
            reverse('advertising:campanha_aprovar', args=[self.campaign.uuid]),
            reverse('advertising:campanha_moderar', args=[self.campaign.uuid, 'pausar']),
        )
        for url in mutation_urls:
            self.assertEqual(self.client.get(url).status_code, 405, url)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        self.assertEqual(csrf_client.post(
            reverse('advertising:campanha_contratar', args=[self.campaign.uuid]),
        ).status_code, 403)


class AdvertisingCommercialConfigurationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.master = get_user_model().objects.create_superuser('commercial-master', password='x')
        cls.regular = get_user_model().objects.create_user('commercial-regular', password='x')
        cls.company = Empresa.objects.create(nome_fantasia='Comercial', usuario_proprietario=cls.regular)

    def plan_data(self, **overrides):
        data = {
            'nome': 'Plano comercial', 'nivel': 4, 'descricao': 'Descrição',
            'preco_diario': '25.00', 'prioridade': 3, 'limite_anunciantes': 2,
            'impressoes_por_usuario_dia': 3, 'duracao_segundos': 8, 'ativo': 'on',
        }
        data.update(overrides)
        return data

    def position_data(self, **overrides):
        data = {
            'nome': 'Banner comercial', 'codigo': 'commercial-banner',
            'descricao': 'Topo público', 'contexto': 'home', 'largura': 1200,
            'altura': 300, 'largura_mobile': 600, 'altura_mobile': 300,
            'proporcao_recomendada': '4:1', 'tamanho_maximo_bytes': 50000,
            'formatos_permitidos': 'png, webp', 'permite_imagem': 'on',
            'dimensoes_obrigatorias': 'on', 'ativo': 'on',
        }
        data.update(overrides)
        return data

    def image_file(self, size=(1200, 300), format='PNG', name='creative.png'):
        content = BytesIO()
        Image.new('RGB', size, 'white').save(content, format=format)
        return SimpleUploadedFile(name, content.getvalue(), content_type=f'image/{format.lower()}')

    def test_somente_master_acessa_e_cria_configuracao(self):
        url = reverse('advertising:configuracao_comercial')
        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.master)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(
            self.client.get(reverse('advertising:campanha_administracao')),
            'Planos e posicionamentos',
        )
        response = self.client.post(reverse('advertising:plano_criar'), self.plan_data())
        self.assertRedirects(response, url)
        self.assertTrue(PlanoPublicitario.objects.get(nome='Plano comercial').ativo)
        response = self.client.post(reverse('advertising:posicionamento_criar'), self.position_data())
        self.assertRedirects(response, url)
        position = Posicionamento.objects.get(codigo='commercial-banner')
        self.assertEqual((position.largura, position.altura), (1200, 300))
        self.assertEqual((position.largura_mobile, position.altura_mobile), (600, 300))

    def test_alteracao_preco_nao_retroage_contratacao(self):
        plan = PlanoPublicitario.objects.create(
            nome='Preço histórico', nivel=4, preco_diario='10', ativo=True)
        position = Posicionamento.objects.create(
            nome='Histórico', codigo='historico', contexto='home')
        now = timezone.now()
        campaign = Campanha.objects.create(
            empresa=self.company, plano=plan, nome='Histórica', criado_por=self.regular,
            inicio=now, fim=now + timedelta(days=2))
        campaign.posicionamentos.add(position)
        Criativo.objects.create(campanha=campaign, tipo='TEXTO', titulo='Texto',
                                texto='Oferta', url_destino='https://example.com')
        contract = contratar_campanha(campanha_id=campaign.pk, usuario=self.regular)
        old_total = contract.valor_total
        self.client.force_login(self.master)
        self.client.post(reverse('advertising:plano_editar', args=[plan.pk]),
                         self.plan_data(nome=plan.nome, preco_diario='99.00', ativo=''))
        plan.refresh_from_db()
        contract.refresh_from_db()
        self.assertEqual(plan.preco_diario, Decimal('99.00'))
        self.assertEqual(contract.valor_total, old_total)
        self.assertFalse(plan.ativo)

    def test_regras_de_arquivo_e_criativo_valido(self):
        position = Posicionamento.objects.create(
            nome='Estrito', codigo='estrito', contexto='home', largura=1200, altura=300,
            largura_mobile=600, altura_mobile=300, dimensoes_obrigatorias=True,
            tamanho_maximo_bytes=50000, formatos_permitidos=['png'],
            permite_imagem=True, permite_video=False, permite_texto=False)
        plan = PlanoPublicitario.objects.create(nome='Upload', nivel=4, preco_diario='1')
        now = timezone.now()
        campaign = Campanha.objects.create(
            empresa=self.company, plano=plan, nome='Upload', criado_por=self.regular,
            inicio=now, fim=now + timedelta(days=1))
        campaign.posicionamentos.add(position)
        base = {'tipo': 'IMAGEM', 'titulo': 'Banner', 'url_destino': 'https://example.com', 'ativo': True}
        self.assertFalse(CriativoForm(base, {'imagem': self.image_file((800, 200))}, campanha=campaign).is_valid())
        self.assertFalse(CriativoForm(base, {'imagem': self.image_file(format='GIF', name='creative.gif')}, campanha=campaign).is_valid())
        position.tamanho_maximo_bytes = 10
        position.save()
        self.assertFalse(CriativoForm(base, {'imagem': self.image_file()}, campanha=campaign).is_valid())
        position.tamanho_maximo_bytes = 50000
        position.save()
        form = CriativoForm(base, {'imagem': self.image_file()}, campanha=campaign)
        self.assertTrue(form.is_valid(), form.errors)
