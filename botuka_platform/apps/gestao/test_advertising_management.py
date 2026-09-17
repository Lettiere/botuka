from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.advertising.models import (
    Campanha,
    Criativo,
    EntregaPublicidade,
    PlanoPublicitario,
    Posicionamento,
)
from apps.gestao.central_views import (
    ADVERTISING_KINDS,
    _ADVERTISING_WORKFLOW_ROUTES,
    _models,
)
from apps.organizations.models import Empresa


class AdvertisingManagementTests(TestCase):
    databases = {'default', 'internal'}

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


class AdvertisingCampaignCentralTests(AdvertisingManagementTests):
    def test_central_campanhas_e_exclusiva_master(self):
        url = reverse('gestao:publicidade_campanhas')

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.master)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'gestao/publicidade/campanhas_lista.html',
        )
        self.assertContains(response, 'Campanhas publicitárias')
        self.assertContains(response, self.campaign.nome)
        self.assertContains(response, self.company.nome_fantasia)

    def test_central_campanhas_filtra_por_busca(self):
        self.client.force_login(self.master)
        url = reverse('gestao:publicidade_campanhas')

        response = self.client.get(url, {'q': 'Campanha Gestão'})
        self.assertContains(response, self.campaign.nome)

        response = self.client.get(url, {'q': 'INEXISTENTE-XYZ'})
        self.assertNotContains(response, self.campaign.nome)
        self.assertContains(
            response,
            'Nenhuma campanha corresponde aos filtros informados.',
        )

    def test_central_campanhas_filtra_por_status(self):
        self.client.force_login(self.master)
        url = reverse('gestao:publicidade_campanhas')

        response = self.client.get(
            url,
            {'status': Campanha.Status.RASCUNHO},
        )
        self.assertContains(response, self.campaign.nome)

        response = self.client.get(
            url,
            {'status': Campanha.Status.ATIVA},
        )
        self.assertNotContains(response, self.campaign.nome)

    def test_central_exibe_indicadores(self):
        self.client.force_login(self.master)

        response = self.client.get(
            reverse('gestao:publicidade_campanhas')
        )

        self.assertEqual(response.context['totais']['total'], 1)
        self.assertEqual(response.context['totais']['rascunho'], 1)
        self.assertEqual(response.context['totais']['aguardando'], 0)
        self.assertEqual(response.context['totais']['ativas'], 0)
        self.assertEqual(response.context['totais']['pausadas'], 0)

    def test_detalhe_campanha_e_exclusivo_master(self):
        url = reverse(
            'gestao:publicidade_campanha_detalhe',
            args=[self.campaign.uuid],
        )

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.master)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'gestao/publicidade/campanha_detalhe.html',
        )
        self.assertContains(response, self.campaign.nome)
        self.assertContains(response, self.company.nome_fantasia)
        self.assertContains(response, self.plan.nome)

    def test_acoes_de_moderacao_nao_aceitam_get(self):
        self.client.force_login(self.master)

        urls = [
            reverse(
                'gestao:publicidade_campanha_aprovar',
                args=[self.campaign.uuid],
            ),
            reverse(
                'gestao:publicidade_campanha_moderar',
                args=[self.campaign.uuid, 'REJEITAR'],
            ),
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_rejeicao_exige_motivo(self):
        self.campaign.status = Campanha.Status.AGUARDANDO_APROVACAO
        self.campaign.save(update_fields=['status', 'atualizado_em'])

        self.client.force_login(self.master)

        response = self.client.post(
            reverse(
                'gestao:publicidade_campanha_moderar',
                args=[self.campaign.uuid, 'REJEITAR'],
            ),
            {'motivo': ''},
        )

        self.assertEqual(response.status_code, 302)

        self.campaign.refresh_from_db()
        self.assertEqual(
            self.campaign.status,
            Campanha.Status.AGUARDANDO_APROVACAO,
        )

    def test_master_pode_rejeitar_campanha_com_motivo(self):
        self.campaign.status = Campanha.Status.AGUARDANDO_APROVACAO
        self.campaign.save(update_fields=['status', 'atualizado_em'])

        self.client.force_login(self.master)

        response = self.client.post(
            reverse(
                'gestao:publicidade_campanha_moderar',
                args=[self.campaign.uuid, 'REJEITAR'],
            ),
            {'motivo': 'Criativo fora da política comercial.'},
        )

        self.assertEqual(response.status_code, 302)

        self.campaign.refresh_from_db()
        self.assertEqual(
            self.campaign.status,
            Campanha.Status.REJEITADA,
        )
        self.assertEqual(
            self.campaign.motivo_rejeicao,
            'Criativo fora da política comercial.',
        )

    def test_aprovacao_sem_cobertura_de_criativos_e_bloqueada(self):
        self.campaign.status = Campanha.Status.AGUARDANDO_APROVACAO
        self.campaign.save(update_fields=['status', 'atualizado_em'])

        self.client.force_login(self.master)

        response = self.client.post(
            reverse(
                'gestao:publicidade_campanha_aprovar',
                args=[self.campaign.uuid],
            ),
        )

        self.assertEqual(response.status_code, 302)

        self.campaign.refresh_from_db()
        self.assertEqual(
            self.campaign.status,
            Campanha.Status.AGUARDANDO_APROVACAO,
        )
        self.assertIsNone(self.campaign.aprovada_em)

    def test_moderacao_post_e_exclusiva_master(self):
        self.campaign.status = Campanha.Status.AGUARDANDO_APROVACAO
        self.campaign.save(update_fields=['status', 'atualizado_em'])

        self.client.force_login(self.outsider)

        response = self.client.post(
            reverse(
                'gestao:publicidade_campanha_moderar',
                args=[self.campaign.uuid, 'REJEITAR'],
            ),
            {'motivo': 'Tentativa não autorizada.'},
        )

        self.assertEqual(response.status_code, 403)

        self.campaign.refresh_from_db()
        self.assertEqual(
            self.campaign.status,
            Campanha.Status.AGUARDANDO_APROVACAO,
        )

    def test_acao_de_moderacao_invalida_nao_altera_campanha(self):
        self.campaign.status = Campanha.Status.AGUARDANDO_APROVACAO
        self.campaign.save(update_fields=['status', 'atualizado_em'])

        self.client.force_login(self.master)

        response = self.client.post(
            reverse(
                'gestao:publicidade_campanha_moderar',
                args=[self.campaign.uuid, 'INVALIDA'],
            ),
        )

        self.assertEqual(response.status_code, 302)

        self.campaign.refresh_from_db()
        self.assertEqual(
            self.campaign.status,
            Campanha.Status.AGUARDANDO_APROVACAO,
        )

    def test_master_pode_pausar_campanha_ativa(self):
        self.campaign.status = Campanha.Status.ATIVA
        self.campaign.save(update_fields=['status', 'atualizado_em'])

        self.client.force_login(self.master)

        response = self.client.post(
            reverse(
                'gestao:publicidade_campanha_moderar',
                args=[self.campaign.uuid, 'PAUSAR'],
            ),
        )

        self.assertEqual(response.status_code, 302)

        self.campaign.refresh_from_db()
        self.assertEqual(
            self.campaign.status,
            Campanha.Status.PAUSADA,
        )

    def test_master_pode_reativar_campanha_pausada(self):
        self.campaign.status = Campanha.Status.PAUSADA
        self.campaign.save(update_fields=['status', 'atualizado_em'])

        self.client.force_login(self.master)

        response = self.client.post(
            reverse(
                'gestao:publicidade_campanha_moderar',
                args=[self.campaign.uuid, 'REATIVAR'],
            ),
        )

        self.assertEqual(response.status_code, 302)

        self.campaign.refresh_from_db()

        self.assertIn(
            self.campaign.status,
            {
                Campanha.Status.APROVADA,
                Campanha.Status.ATIVA,
            },
        )


class AdvertisingCommercialConfigurationTests(AdvertisingManagementTests):
    def test_configuracao_comercial_e_exclusiva_master(self):
        url = reverse('gestao:publicidade_configuracao')

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.master)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'gestao/publicidade/configuracao_comercial.html',
        )
        self.assertContains(response, self.plan.nome)
        self.assertContains(response, self.position.nome)

    def test_master_pode_criar_plano(self):
        self.client.force_login(self.master)

        response = self.client.post(
            reverse('gestao:publicidade_plano_novo'),
            {
                'nome': 'Standard Gestão',
                'nivel': PlanoPublicitario.Nivel.QUATRO,
                'descricao': 'Plano de teste da gestão.',
                'preco_diario': '25.00',
                'prioridade': '10',
                'limite_anunciantes': '0',
                'impressoes_por_usuario_dia': '3',
                'duracao_segundos': '8',
                'ativo': 'on',
            },
        )

        self.assertRedirects(
            response,
            reverse('gestao:publicidade_configuracao'),
        )

        plano = PlanoPublicitario.objects.get(nome='Standard Gestão')
        self.assertEqual(plano.preco_diario, Decimal('25.00'))
        self.assertFalse(plano.exclusivo)
        self.assertTrue(plano.ativo)

    def test_master_pode_editar_plano(self):
        self.client.force_login(self.master)

        response = self.client.post(
            reverse(
                'gestao:publicidade_plano_editar',
                args=[self.plan.pk],
            ),
            {
                'nome': self.plan.nome,
                'nivel': PlanoPublicitario.Nivel.ZERO,
                'descricao': 'Atualizado pela gestão.',
                'preco_diario': '150.00',
                'prioridade': '60',
                'exclusivo': 'on',
                'limite_anunciantes': '1',
                'impressoes_por_usuario_dia': '4',
                'duracao_segundos': '10',
                'ativo': 'on',
            },
        )

        self.assertRedirects(
            response,
            reverse('gestao:publicidade_configuracao'),
        )

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.preco_diario, Decimal('150.00'))
        self.assertEqual(self.plan.prioridade, 60)
        self.assertEqual(self.plan.limite_anunciantes, 1)

    def test_takeover_sem_exclusividade_e_rejeitado(self):
        self.client.force_login(self.master)

        response = self.client.post(
            reverse('gestao:publicidade_plano_novo'),
            {
                'nome': 'Takeover Inválido',
                'nivel': PlanoPublicitario.Nivel.ZERO,
                'descricao': '',
                'preco_diario': '100.00',
                'prioridade': '10',
                'limite_anunciantes': '1',
                'impressoes_por_usuario_dia': '3',
                'duracao_segundos': '8',
                'ativo': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            PlanoPublicitario.objects.filter(
                nome='Takeover Inválido',
            ).exists()
        )
        self.assertContains(response, 'Takeover deve ser exclusivo.')

    def test_master_pode_criar_posicionamento_e_normaliza_formatos(self):
        self.client.force_login(self.master)

        response = self.client.post(
            reverse('gestao:publicidade_posicionamento_novo'),
            {
                'nome': 'Sidebar Gestão',
                'codigo': 'sidebar-gestao-teste',
                'descricao': 'Posição criada pela gestão.',
                'contexto': 'public',
                'largura': '400',
                'altura': '600',
                'largura_mobile': '720',
                'altura_mobile': '360',
                'proporcao_recomendada': '2:3',
                'tamanho_maximo_bytes': str(5 * 1024 * 1024),
                'formatos_permitidos': '.JPG, png, jpg, WEBP',
                'permite_imagem': 'on',
                'permite_texto': 'on',
                'ativo': 'on',
            },
        )

        self.assertRedirects(
            response,
            reverse('gestao:publicidade_configuracao'),
        )

        posicionamento = Posicionamento.objects.get(
            codigo='sidebar-gestao-teste'
        )
        self.assertEqual(
            posicionamento.formatos_permitidos,
            ['jpg', 'png', 'webp'],
        )
        self.assertTrue(posicionamento.permite_imagem)
        self.assertFalse(posicionamento.permite_video)

    def test_master_pode_editar_posicionamento(self):
        self.client.force_login(self.master)

        response = self.client.post(
            reverse(
                'gestao:publicidade_posicionamento_editar',
                args=[self.position.pk],
            ),
            {
                'nome': 'Takeover Home Atualizado',
                'codigo': self.position.codigo,
                'descricao': '',
                'contexto': 'public',
                'largura': '1200',
                'altura': '300',
                'largura_mobile': '720',
                'altura_mobile': '360',
                'proporcao_recomendada': '4:1',
                'tamanho_maximo_bytes': str(5 * 1024 * 1024),
                'formatos_permitidos': 'jpg, png, webp',
                'permite_imagem': 'on',
                'aceita_takeover': 'on',
                'ativo': 'on',
            },
        )

        self.assertRedirects(
            response,
            reverse('gestao:publicidade_configuracao'),
        )

        self.position.refresh_from_db()
        self.assertEqual(
            self.position.nome,
            'Takeover Home Atualizado',
        )
        self.assertEqual(self.position.largura, 1200)
        self.assertEqual(self.position.altura, 300)

    def test_posicionamento_sem_tipo_de_criativo_e_rejeitado(self):
        self.client.force_login(self.master)

        response = self.client.post(
            reverse('gestao:publicidade_posicionamento_novo'),
            {
                'nome': 'Posição Inválida',
                'codigo': 'posicao-invalida-gestao',
                'descricao': '',
                'contexto': 'public',
                'largura': '400',
                'altura': '600',
                'largura_mobile': '',
                'altura_mobile': '',
                'proporcao_recomendada': '',
                'tamanho_maximo_bytes': str(5 * 1024 * 1024),
                'formatos_permitidos': 'jpg',
                'ativo': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Posicionamento.objects.filter(
                codigo='posicao-invalida-gestao',
            ).exists()
        )
        self.assertContains(
            response,
            'Permita ao menos um tipo de criativo.',
        )

    def test_usuario_comum_nao_pode_alterar_configuracao(self):
        self.client.force_login(self.outsider)

        urls = (
            reverse('gestao:publicidade_plano_novo'),
            reverse(
                'gestao:publicidade_plano_editar',
                args=[self.plan.pk],
            ),
            reverse('gestao:publicidade_posicionamento_novo'),
            reverse(
                'gestao:publicidade_posicionamento_editar',
                args=[self.position.pk],
            ),
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {}).status_code, 403)


class AdvertisingCreativeDeliveryTests(AdvertisingManagementTests):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.creative = Criativo.objects.create(
            campanha=cls.campaign,
            posicionamento=cls.position,
            tipo=Criativo.Tipo.TEXTO,
            titulo='Criativo Gestão Principal',
            texto='Conteúdo publicitário de teste.',
            url_destino='https://example.com/campanha',
            ativo=True,
        )

        cls.other_creative = Criativo.objects.create(
            campanha=cls.campaign,
            posicionamento=cls.position,
            tipo=Criativo.Tipo.TEXTO,
            titulo='Criativo Gestão Secundário',
            texto='Segundo conteúdo publicitário.',
            url_destino='https://example.com/secundario',
            ativo=False,
        )

        cls.delivery_clicked = EntregaPublicidade.objects.create(
            campanha=cls.campaign,
            criativo=cls.creative,
            posicionamento=cls.position,
            visitante_hash='visitante-gestao-1',
            contexto='home',
        )
        cls.delivery_clicked.clicado_em = timezone.now()
        cls.delivery_clicked.save(update_fields=['clicado_em'])

        cls.delivery_not_clicked = EntregaPublicidade.objects.create(
            campanha=cls.campaign,
            criativo=cls.creative,
            posicionamento=cls.position,
            visitante_hash='visitante-gestao-2',
            contexto='home',
        )

    def test_criativos_sao_exclusivos_master(self):
        list_url = reverse('gestao:publicidade_criativos')
        detail_url = reverse(
            'gestao:publicidade_criativo_detalhe',
            args=[self.creative.pk],
        )

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(list_url).status_code, 403)
        self.assertEqual(self.client.get(detail_url).status_code, 403)

        self.client.force_login(self.master)

        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'gestao/publicidade/criativos_lista.html',
        )
        self.assertContains(response, self.creative.titulo)

        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'gestao/publicidade/criativo_detalhe.html',
        )
        self.assertContains(response, self.creative.titulo)
        self.assertContains(response, self.campaign.nome)

    def test_criativos_filtram_busca_tipo_ativo_e_posicionamento(self):
        self.client.force_login(self.master)
        url = reverse('gestao:publicidade_criativos')

        response = self.client.get(url, {
            'q': 'Principal',
            'tipo': Criativo.Tipo.TEXTO,
            'ativo': '1',
            'posicionamento': str(self.position.pk),
        })

        self.assertContains(response, self.creative.titulo)
        self.assertNotContains(response, self.other_creative.titulo)

        response = self.client.get(url, {'ativo': '0'})
        self.assertContains(response, self.other_creative.titulo)
        self.assertNotContains(response, self.creative.titulo)

    def test_criativo_exibe_metricas_reais(self):
        self.client.force_login(self.master)

        response = self.client.get(
            reverse(
                'gestao:publicidade_criativo_detalhe',
                args=[self.creative.pk],
            )
        )

        self.assertEqual(response.context['criativo'].impressoes, 2)
        self.assertEqual(response.context['criativo'].cliques, 1)

    def test_entregas_sao_exclusivas_master_e_read_only(self):
        url = reverse('gestao:publicidade_entregas')

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.master)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'gestao/publicidade/entregas_lista.html',
        )
        self.assertEqual(response.context['metricas']['impressoes'], 2)
        self.assertEqual(response.context['metricas']['cliques'], 1)
        self.assertEqual(response.context['metricas']['ctr'], 50.0)

        before = EntregaPublicidade.objects.count()
        post_response = self.client.post(url, {})
        self.assertEqual(post_response.status_code, 200)
        self.assertEqual(EntregaPublicidade.objects.count(), before)

    def test_entregas_filtram_clique_e_posicionamento(self):
        self.client.force_login(self.master)
        url = reverse('gestao:publicidade_entregas')

        response = self.client.get(url, {
            'clique': '1',
            'posicionamento': str(self.position.pk),
        })

        self.assertEqual(response.context['metricas']['impressoes'], 1)
        self.assertEqual(response.context['metricas']['cliques'], 1)
        self.assertEqual(response.context['metricas']['ctr'], 100.0)
        self.assertEqual(
            list(response.context['page_obj'].object_list),
            [self.delivery_clicked],
        )

        response = self.client.get(url, {'clique': '0'})

        self.assertEqual(response.context['metricas']['impressoes'], 1)
        self.assertEqual(response.context['metricas']['cliques'], 0)
        self.assertEqual(response.context['metricas']['ctr'], 0)
        self.assertEqual(
            list(response.context['page_obj'].object_list),
            [self.delivery_not_clicked],
        )

    def test_entregas_filtram_por_busca(self):
        self.client.force_login(self.master)
        url = reverse('gestao:publicidade_entregas')

        response = self.client.get(
            url,
            {'q': self.creative.titulo},
        )

        self.assertEqual(response.context['metricas']['impressoes'], 2)
        self.assertContains(response, self.creative.titulo)

        response = self.client.get(
            url,
            {'q': 'INEXISTENTE-ENTREGA-XYZ'},
        )

        self.assertEqual(response.context['metricas']['impressoes'], 0)
        self.assertEqual(response.context['metricas']['cliques'], 0)
