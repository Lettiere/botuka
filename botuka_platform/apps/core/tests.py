from django.contrib.auth import get_user_model
from django.templatetags.static import static
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import UsuarioPerfil
from apps.core.models import Perfil, Permissao, PerfilPermissao


class CityModulePermissionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('cidadao', password='x')

    def test_usuario_sem_permissao_bloqueado(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('painel:news_artigo_lista')).status_code, 403)

    def test_perfil_adicional_concede_permissao(self):
        perfil = Perfil.objects.create(nome='NEWS_REPORTER')
        permissao = Permissao.objects.create(codigo='news.criar', nome='Criar notícia')
        PerfilPermissao.objects.create(perfil=perfil, permissao=permissao)
        UsuarioPerfil.objects.create(usuario=self.user, perfil=perfil)
        self.assertTrue(self.user.tem_perfil('NEWS_REPORTER'))
        self.assertTrue(self.user.tem_permissao('news.criar'))

    def test_root_administra_todos_os_modulos(self):
        perfil = Perfil.objects.create(nome='ROOT')
        self.user.perfil = perfil
        self.user.save(update_fields=['perfil'])
        self.assertTrue(self.user.tem_permissao('sports.publicar'))
        self.assertTrue(self.user.tem_permissao('media.publicar'))
        self.assertTrue(self.user.tem_permissao('news.publicar'))
        self.assertTrue(self.user.tem_permissao('government.publicar'))


class HomeProfileRegressionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('home-comum', password='x')
        self.master_profile = Perfil.objects.create(nome='MASTER')
        self.master = get_user_model().objects.create_user(
            'home-master', password='x', perfil=self.master_profile,
        )

    def test_home_abre_para_usuario_anonimo(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="public-shell"')

    def test_home_abre_para_usuario_comum_autenticado(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)

    def test_home_abre_para_usuario_master(self):
        self.client.force_login(self.master)
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)

    def test_assets_publicos_usam_url_absoluta(self):
        self.assertEqual(static('css/platform/style.css'), '/static/css/platform/style.css')
        self.assertEqual(static('js/platform/main.js'), '/static/js/platform/main.js')
