from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.models import Perfil, PerfilPermissao, Permissao
from apps.painel.navigation import painel_navigation


class PainelSharedInterfaceTests(SimpleTestCase):
    def test_shared_templates_compile(self):
        for template_name in (
            "painel/base.html",
            "painel/components/page_header.html",
            "painel/components/filter_bar.html",
            "painel/components/indicators.html",
            "painel/components/status_badge.html",
            "painel/components/pagination.html",
            "painel/components/empty_state.html",
            "painel/components/form_actions.html",
            "painel/components/confirm_modal.html",
            "painel/noticias/dashboard.html",
            "painel/yubotuka/dashboard.html",
            "painel/domain/list.html",
        ):
            self.assertIsNotNone(get_template(template_name))

    def test_module_dashboards_have_stable_routes(self):
        expected = {
            "painel:dashboard": "/painel/",
            "painel:news_dashboard": "/painel/noticias/",
            "painel:turismo_dashboard": "/painel/turismo/",
            "painel:yubotuka_dashboard": "/painel/yubotuka/",
            "painel:sports_dashboard": "/painel/esportes/",
            "painel:government_dashboard": "/painel/prefeitura/",
        }
        for name, path in expected.items():
            self.assertEqual(reverse(name), path)


class YuBotukaPanelIntegrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.autorizado = User.objects.create_user('painel_yu_autorizado', password='x')
        self.sem_permissao = User.objects.create_user('painel_yu_sem_permissao', password='x')
        perfil = Perfil.objects.create(nome='PAINEL_YUBOTUKA')
        self.autorizado.perfis_adicionais.add(perfil)
        for codigo in (
            'yubotuka.dashboard.visualizar',
            'yubotuka.programa.gerenciar',
            'yubotuka.temporada.gerenciar',
            'yubotuka.episodio.gerenciar',
            'yubotuka.transmissao.editar_todas',
        ):
            PerfilPermissao.objects.create(
                perfil=perfil,
                permissao=Permissao.objects.get(codigo=codigo),
            )
        self.factory = RequestFactory()

    def _navigation(self, user):
        request = self.factory.get('/painel/')
        request.user = user
        return painel_navigation(request)['painel_module_groups']

    def test_item_yubotuka_visivel_somente_para_usuario_autorizado(self):
        autorizado = str(self._navigation(self.autorizado))
        nao_autorizado = str(self._navigation(self.sem_permissao))
        self.assertIn('YuBotuka', autorizado)
        self.assertIn(reverse('painel:yubotuka_dashboard'), autorizado)
        self.assertNotIn('YuBotuka', nao_autorizado)

    def test_alias_antigo_e_dashboard_novo_funcionam(self):
        self.client.force_login(self.autorizado)
        novo = self.client.get('/painel/yubotuka/')
        antigo = self.client.get('/painel/ytv/')
        self.assertEqual(novo.status_code, 200)
        self.assertEqual(antigo.status_code, 200)
        self.assertContains(novo, 'YuBotuka')
        self.assertContains(novo, 'breadcrumb')

    def test_dashboard_expoe_links_principais_sem_rota_quebrada(self):
        self.client.force_login(self.autorizado)
        response = self.client.get(reverse('painel:yubotuka_dashboard'))
        self.assertEqual(response.status_code, 200)
        for route in (
            'painel:yubotuka_programas',
            'painel:yubotuka_temporadas',
            'painel:yubotuka_episodios',
            'painel:yubotuka_transmissoes',
        ):
            self.assertIn(reverse(route), response.content.decode())

    def test_menu_mobile_mantem_nome_acessivel(self):
        self.client.force_login(self.autorizado)
        response = self.client.get(
            reverse('painel:yubotuka_dashboard'),
            HTTP_USER_AGENT='Mozilla/5.0 (Linux; Android 14) Mobile',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'YuBotuka')

    def test_rotas_criticas_resolvem(self):
        for route in (
            'painel:yubotuka_dashboard',
            'painel:yubotuka_programas',
            'painel:yubotuka_transmissoes',
            'painel:media_episodio_lista',
        ):
            self.assertTrue(reverse(route).startswith('/painel/'))
