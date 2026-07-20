from django.contrib.auth import get_user_model
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
        self.assertTrue(self.user.tem_permissao('news.criar'))

    def test_root_administra_todos_os_modulos(self):
        perfil = Perfil.objects.create(nome='ROOT')
        self.user.perfil = perfil
        self.user.save(update_fields=['perfil'])
        self.assertTrue(self.user.tem_permissao('sports.publicar'))
        self.assertTrue(self.user.tem_permissao('media.publicar'))
        self.assertTrue(self.user.tem_permissao('news.publicar'))
        self.assertTrue(self.user.tem_permissao('government.publicar'))
