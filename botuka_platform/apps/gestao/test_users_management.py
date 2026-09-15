from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import AcessoModulo, ConcessaoPermissao
from apps.core.models import Perfil, Permissao
from apps.organizations.models import Capacidade, UsuarioCapacidade


class GestaoUsersManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.master = User.objects.create_superuser('users-master', password='x')
        cls.operator = User.objects.create_user('users-operator', email='operator@test.local', password='x')
        cls.target = User.objects.create_user('users-target', email='target@test.local', password='x')
        gestao_access = AcessoModulo.objects.create(
            usuario=cls.operator, modulo='gestao', concedido_por=cls.master,
            justificativa='Teste da Gestão',
        )
        users_access = AcessoModulo.objects.create(
            usuario=cls.operator, modulo='usuarios', concedido_por=cls.master,
            justificativa='Teste de usuários',
        )
        for code in ('gestao.acessar', 'usuarios.visualizar', 'usuarios.criar', 'usuarios.editar', 'usuarios.desativar'):
            permission, _ = Permissao.objects.get_or_create(
                codigo=code,
                defaults={
                    'modulo': code.split('.', 1)[0], 'grupo': 'Gestão',
                    'nome': code, 'descricao': 'Permissão da fixture da Etapa 4',
                },
            )
            ConcessaoPermissao.objects.create(
                acesso=gestao_access if code == 'gestao.acessar' else users_access,
                usuario=cls.operator, permissao=permission,
                concedida_por=cls.master, justificativa='Teste',
            )

    def user_data(self, **overrides):
        data = {
            'first_name': 'Pessoa', 'last_name': 'Teste', 'nome_exibicao': '',
            'email': 'new-user@test.local', 'telefone': '', 'celular': '',
            'cpf': '', 'data_nascimento': '', 'biografia': '', 'estado': '',
            'cidade': '', 'perfil': '', 'is_active': 'on',
        }
        data.update(overrides)
        return data

    def test_user_crud_search_detail_validation_and_no_password_exposure(self):
        self.client.force_login(self.operator)
        listing = self.client.get(reverse('gestao:usuarios_lista'), {'q': 'target@test.local'})
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, self.target.email)
        detail = self.client.get(reverse('gestao:usuarios_detalhe', args=[self.target.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, self.target.password)
        create_url = reverse('gestao:usuarios_novo')
        self.assertEqual(self.client.post(create_url, self.user_data(email='')).status_code, 200)
        response = self.client.post(create_url, self.user_data(is_staff='on'))
        created = get_user_model().objects.get(email='new-user@test.local')
        self.assertRedirects(response, reverse('gestao:usuarios_lista'))
        self.assertFalse(created.is_staff)
        self.assertFalse(created.has_usable_password())

    def test_non_master_cannot_promote_user_to_staff_or_global_profile(self):
        global_profile = Perfil.objects.get(nome='ADMIN_GLOBAL')
        self.client.force_login(self.operator)
        data = self.user_data(email=self.target.email, perfil=global_profile.pk, is_staff='on')
        response = self.client.post(reverse('gestao:usuarios_editar', args=[self.target.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_staff)
        self.assertIsNone(self.target.perfil_id)

    def test_regular_edit_cannot_demote_superuser_or_expose_access_actions(self):
        protected = get_user_model().objects.create_superuser(
            'protected-master', email='protected@test.local', password='x',
        )
        self.client.force_login(self.master)
        response = self.client.post(
            reverse('gestao:usuarios_editar', args=[protected.pk]),
            self.user_data(email=protected.email, first_name='Protegido'),
        )
        self.assertRedirects(response, reverse('gestao:usuarios_lista'))
        protected.refresh_from_db()
        self.assertTrue(protected.is_superuser)
        self.assertTrue(protected.is_staff)

        self.client.force_login(self.operator)
        detail = self.client.get(reverse('gestao:usuarios_detalhe', args=[self.target.pk]))
        self.assertNotContains(
            detail, reverse('gestao:usuario_acessos', args=[self.target.uuid]),
        )

    def test_self_deactivation_is_blocked(self):
        self.client.force_login(self.operator)
        self.assertEqual(self.client.post(reverse(
            'gestao:usuarios_desativar', args=[self.operator.pk],
        )).status_code, 403)
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.is_active)

    def test_profile_and_permission_detail_status_are_master_only_and_csrf_protected(self):
        profile = Perfil.objects.create(nome='PERFIL_GESTAO_TESTE')
        permission = Permissao.objects.create(
            modulo='teste', grupo='Teste', nome='Permissão teste',
            codigo='teste.gestao_etapa4', descricao='Teste',
        )
        self.client.force_login(self.master)
        for kind, instance in (('perfis', profile), ('permissoes', permission)):
            detail_url = reverse('gestao:controle_detalhe', args=[kind, instance.pk])
            status_url = reverse('gestao:controle_status', args=[kind, instance.pk])
            self.assertEqual(self.client.get(detail_url).status_code, 200)
            self.assertEqual(self.client.get(status_url).status_code, 405)
            self.assertRedirects(self.client.post(status_url), detail_url)
            instance.refresh_from_db()
            self.assertFalse(instance.ativo)
            self.assertIsNotNone(instance.removido_em)
            self.assertTrue(type(instance).all_objects.filter(pk=instance.pk).exists())
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.master)
        self.assertEqual(csrf_client.post(reverse(
            'gestao:controle_status', args=['perfis', profile.pk],
        )).status_code, 403)
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(reverse(
            'gestao:controle_detalhe', args=['perfis', profile.pk],
        )).status_code, 403)

    def test_master_and_protected_permission_cannot_be_inactivated(self):
        master_profile = Perfil.objects.get(nome='MASTER')
        protected = Permissao.objects.filter(protegida=True).first()
        self.client.force_login(self.master)
        self.assertEqual(self.client.post(reverse(
            'gestao:controle_status', args=['perfis', master_profile.pk],
        )).status_code, 403)
        if protected:
            self.assertEqual(self.client.post(reverse(
                'gestao:controle_status', args=['permissoes', protected.pk],
            )).status_code, 403)

    def test_global_role_uses_protected_post_service(self):
        self.client.force_login(self.master)
        url = reverse('gestao:usuario_papel_global', args=[self.target.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(
            self.client.post(url, {'papel': 'ADMIN_GLOBAL'}),
            reverse('gestao:usuarios_detalhe', args=[self.target.pk]),
        )
        self.target.refresh_from_db()
        self.assertEqual(self.target.perfil.nome, 'ADMIN_GLOBAL')
        self.assertRedirects(
            self.client.post(url, {'papel': ''}),
            reverse('gestao:usuarios_detalhe', args=[self.target.pk]),
        )
        self.target.refresh_from_db()
        self.assertIsNone(self.target.perfil_id)
        self.assertFalse(self.target.is_staff)
        self.assertFalse(self.target.is_superuser)
        self.client.force_login(self.operator)
        self.assertEqual(self.client.post(url, {'papel': 'MASTER'}).status_code, 403)

    def test_user_filters_pagination_and_read_only_relations(self):
        capability = Capacidade.objects.create(codigo='PESSOAL_TESTE', nome='Pessoal teste')
        UsuarioCapacidade.objects.create(usuario=self.target, capacidade=capability)
        User = get_user_model()
        for index in range(22):
            User.objects.create_user(f'page-user-{index}', email=f'page-{index}@test.local')
        self.client.force_login(self.operator)
        response = self.client.get(reverse('gestao:usuarios_lista'), {
            'ativo': '1', 'staff': '0', 'q': 'page-',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['page_obj'].has_next())
        self.assertEqual(len(response.context['page_obj'].object_list), 20)
        detail = self.client.get(reverse('gestao:usuarios_detalhe', args=[self.target.pk]))
        self.assertContains(detail, 'Pessoal teste')
        self.assertContains(detail, 'Somente leitura')

    def test_gestao_access_filter_and_critical_query_limits(self):
        self.client.force_login(self.operator)
        with CaptureQueriesContext(connection) as list_queries:
            response = self.client.get(reverse('gestao:usuarios_lista'), {'gestao': '1'})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, self.operator.email)
        # Inclui os context processors globais da plataforma; o teto impede
        # crescimento por linha/N+1 na listagem paginada.
        self.assertLessEqual(len(list_queries), 55)

        self.client.force_login(self.master)
        with CaptureQueriesContext(connection) as detail_queries:
            response = self.client.get(reverse('gestao:usuarios_detalhe', args=[self.target.pk]))
            self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(detail_queries), 20)

    def test_profile_and_permission_valid_invalid_create_and_update(self):
        self.client.force_login(self.master)
        invalid_profile = self.client.post(reverse('gestao:perfis_novo'), {
            'nome': '', 'descricao': '', 'ativo': 'on',
        })
        self.assertEqual(invalid_profile.status_code, 200)
        created_profile = self.client.post(reverse('gestao:perfis_novo'), {
            'nome': 'PERFIL_CRUD_TESTE', 'descricao': 'Criado', 'ativo': 'on',
        })
        self.assertRedirects(created_profile, reverse('gestao:perfis_lista'))
        profile = Perfil.objects.get(nome='PERFIL_CRUD_TESTE')
        updated_profile = self.client.post(reverse('gestao:perfis_editar', args=[profile.pk]), {
            'nome': 'PERFIL_CRUD_TESTE', 'descricao': 'Atualizado', 'ativo': 'on',
        })
        self.assertRedirects(updated_profile, reverse('gestao:perfis_lista'))
        invalid_permission = self.client.post(reverse('gestao:permissoes_nova'), {
            'modulo': 'teste', 'grupo': 'Teste', 'nome': '', 'codigo': '',
            'descricao': '', 'criticidade': 0, 'ativo': 'on',
        })
        self.assertEqual(invalid_permission.status_code, 200)
        created_permission = self.client.post(reverse('gestao:permissoes_nova'), {
            'modulo': 'teste', 'grupo': 'Teste', 'nome': 'Permissão CRUD',
            'codigo': 'teste.crud_etapa4', 'descricao': 'Criada',
            'criticidade': 10, 'ativo': 'on',
        })
        self.assertRedirects(created_permission, reverse('gestao:permissoes_lista'))
        permission = Permissao.objects.get(codigo='teste.crud_etapa4')
        updated_permission = self.client.post(reverse('gestao:permissoes_editar', args=[permission.pk]), {
            'modulo': 'teste', 'grupo': 'Teste', 'nome': 'Permissão atualizada',
            'codigo': permission.codigo, 'descricao': 'Atualizada',
            'criticidade': 10, 'ativo': 'on',
        })
        self.assertRedirects(updated_permission, reverse('gestao:permissoes_lista'))
