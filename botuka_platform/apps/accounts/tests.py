from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import UsuarioPerfil
from apps.accounts.permissions import usuario_e_master, usuario_tem_permissao
from apps.accounts.master_services import garantir_usuario_master
from apps.core.models import Perfil, Permissao, PerfilPermissao
from apps.gestao.forms import UsuarioForm


class MasterAccessTests(TestCase):
    def setUp(self):
        self.master, _ = garantir_usuario_master(
            email='master-test@example.com', username='master-test', senha='SenhaSegura#2026',
        )
        self.comum = get_user_model().objects.create_user('comum-master-test', password='SenhaSegura#2026')

    def test_master_acessa_admin_e_painel_comum(self):
        self.client.force_login(self.master)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)
        self.assertEqual(self.client.get(reverse('painel:dashboard')).status_code, 200)

    def test_perfil_master_principal_ou_adicional_e_reconhecido(self):
        perfil = Perfil.objects.get(nome='MASTER')
        adicional = get_user_model().objects.create_user('master-adicional', password='SenhaSegura#2026')
        UsuarioPerfil.objects.create(usuario=adicional, perfil=perfil)
        self.assertTrue(usuario_e_master(self.master))
        self.assertTrue(usuario_e_master(adicional))
        self.assertTrue(adicional.tem_permissao('qualquer.modulo'))

    def test_usuario_comum_nao_se_promove_para_master(self):
        perfil = Perfil.objects.get(nome='MASTER')
        form = UsuarioForm(
            {'email': self.comum.email or 'comum@example.com', 'perfil': perfil.pk, 'is_active': True},
            instance=self.comum,
            ator=self.comum,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('perfil', form.errors)

    def test_master_consegue_criar_outro_master(self):
        perfil = Perfil.objects.get(nome='MASTER')
        form = UsuarioForm(
            {'email': 'outro-master@example.com', 'perfil': perfil.pk, 'is_active': True},
            ator=self.master,
        )
        self.assertTrue(form.is_valid(), form.errors)
        outro = form.save()
        self.assertTrue(usuario_e_master(outro))
        self.assertTrue(outro.is_staff)
        self.assertTrue(outro.is_superuser)

    @patch(
        'apps.accounts.management.commands.criar_master_botuka.getpass',
        side_effect=['SenhaComando#2026', 'SenhaComando#2026'] * 2,
    )
    def test_comando_e_idempotente_e_nao_expoe_senha(self, _getpass):
        saida = StringIO()
        call_command('criar_master_botuka', email='command-master@example.com', stdout=saida)
        call_command('criar_master_botuka', email='command-master@example.com', stdout=saida)
        self.assertEqual(get_user_model().objects.filter(email='command-master@example.com').count(), 1)
        self.assertNotIn('SenhaComando#2026', saida.getvalue())

    def test_nao_master_nao_altera_permissoes_criticas(self):
        perfil = Perfil.objects.create(nome='GESTOR_LIMITADO')
        permissao = Permissao.objects.create(codigo='perfis.gerenciar', nome='Gerenciar perfis')
        PerfilPermissao.objects.create(perfil=perfil, permissao=permissao)
        self.comum.perfil = perfil
        self.comum.is_staff = True
        self.comum.save(update_fields=['perfil', 'is_staff'])
        self.client.force_login(self.comum)
        self.assertEqual(self.client.get(reverse('gestao:perfis_novo')).status_code, 403)
        self.assertEqual(self.client.get(reverse('gestao:configuracoes_lista')).status_code, 403)


class AnonymousPermissionRegressionTests(TestCase):
    def test_admin_login_abre_para_anonimo(self):
        response = self.client.get(reverse('admin:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'botuka-admin.css')
        self.assertContains(response, 'botuka-admin.js')
        self.assertContains(response, 'botuka-login-card')

    def test_admin_redireciona_anonimo_para_login(self):
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response.url)

    def test_painel_continua_protegido(self):
        response = self.client.get(reverse('painel:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_helper_rejeita_anonymous_user_sem_attribute_error(self):
        self.assertFalse(usuario_tem_permissao(AnonymousUser(), 'qualquer.permissao'))
        self.assertFalse(usuario_tem_permissao(None, 'qualquer.permissao'))

    def test_usuario_comum_sem_permissao_retorna_false(self):
        comum = get_user_model().objects.create_user(
            username='comum-permissao-segura', password='SenhaSegura#2026',
        )
        self.assertFalse(usuario_tem_permissao(comum, 'qualquer.permissao'))

    def test_master_mantem_acesso(self):
        master, _ = garantir_usuario_master(
            email='master-permissao-segura@example.com',
            username='master-permissao-segura',
            senha='SenhaSegura#2026',
        )
        self.assertTrue(usuario_tem_permissao(master, 'qualquer.permissao'))

    def test_tema_admin_preserva_listagem_edicao_e_historico(self):
        master, _ = garantir_usuario_master(
            email='master-tema-admin@example.com',
            username='master-tema-admin',
            senha='SenhaSegura#2026',
        )
        self.client.force_login(master)
        urls = (
            reverse('admin:index'),
            reverse('admin:accounts_usuario_changelist'),
            reverse('admin:accounts_usuario_change', args=(master.pk,)),
            reverse('admin:accounts_usuario_history', args=(master.pk,)),
            reverse('admin:organizations_empresa_changelist'),
            reverse('admin:services_servico_changelist'),
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'botuka-admin.css')
