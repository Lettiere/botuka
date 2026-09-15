from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import AcessoModulo, ConcessaoPermissao
from apps.core.models import Permissao
from apps.core.models import Perfil, PerfilPermissao


class GestaoAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.master = User.objects.create_superuser("gestao-master", password="x")
        self.user = User.objects.create_user("gestao-user", password="x")
        self.target = User.objects.create_user("gestao-target", password="x")

    def grant(self, *codes):
        access = AcessoModulo.objects.create(
            usuario=self.user, modulo="gestao", concedido_por=self.master,
            justificativa="Teste",
        )
        for code in codes:
            permission = Permissao.objects.get(codigo=code)
            ConcessaoPermissao.objects.create(
                acesso=access, usuario=self.user, permissao=permission,
                concedida_por=self.master, justificativa="Teste",
            )

    def test_sem_acesso_recebe_403(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("gestao:dashboard")).status_code, 403)

    def test_gestao_acessar_entra_no_dashboard(self):
        self.grant("gestao.acessar")
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("gestao:dashboard")).status_code, 200)

    def test_gerenciar_permissoes_abre_acessos(self):
        self.grant("gestao.acessar", "gestao.gerenciar_permissoes")
        self.client.force_login(self.user)
        response = self.client.get(reverse("gestao:usuario_acessos", args=[self.target.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acessos e permissões")

    def test_url_legada_redireciona(self):
        self.client.force_login(self.master)
        response = self.client.get(reverse("gestao:usuario_permissoes", args=[self.target.uuid]))
        self.assertRedirects(response, reverse("gestao:usuario_acessos", args=[self.target.uuid]))

    def access_post(self, **overrides):
        permission = Permissao.objects.get(codigo='media.acessar')
        data = {
            'modulo': 'media', 'perfil': '', 'escopo': 'PROPRIOS',
            'justificativa': 'Teste de formulário', 'observacao': '',
            'permissoes': [permission.pk],
        }
        data.update(overrides)
        return self.client.post(
            reverse('gestao:usuario_acesso_novo', args=[self.target.uuid]) + '?modulo=yubotuka',
            data,
        )

    def test_perfil_vazio_e_ausente_nao_geram_uuid_error(self):
        self.client.force_login(self.master)
        self.assertEqual(self.access_post(perfil='').status_code, 302)
        other = get_user_model().objects.create_user('target-sem-perfil', password='x')
        self.target = other
        response = self.access_post()
        self.assertEqual(response.status_code, 302)

    def test_uuid_invalido_e_perfil_de_outro_modulo_sao_erros_de_formulario(self):
        self.client.force_login(self.master)
        response = self.access_post(perfil='uuid-invalido')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Faça uma escolha válida')
        news_permission = Permissao.objects.get(codigo='news.acessar')
        profile = Perfil.objects.create(nome='NEWS_ONLY_TEST')
        PerfilPermissao.objects.create(perfil=profile, permissao=news_permission)
        response = self.access_post(perfil=profile.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Faça uma escolha válida')

    def test_modulo_invalido_e_matriz_vazia_sao_bloqueados(self):
        self.client.force_login(self.master)
        response = self.access_post(modulo='inexistente')
        self.assertEqual(response.status_code, 200)
        response = self.access_post(permissoes=[])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Selecione ao menos uma permissão')

    def test_profile_defaults_are_applied_when_existing_access_is_edited(self):
        self.client.force_login(self.master)
        self.assertEqual(self.access_post().status_code, 302)
        permission = Permissao.objects.get(codigo='media.acessar')
        extra = Permissao.objects.create(
            modulo='media', grupo='Teste', codigo='media.profile_extra',
            nome='Permissão adicional do perfil',
        )
        profile = Perfil.objects.create(nome='MEDIA_PROFILE_UPDATE')
        PerfilPermissao.objects.create(perfil=profile, permissao=extra)
        access = AcessoModulo.objects.get(usuario=self.target, modulo='media')
        response = self.client.post(reverse(
            'gestao:usuario_acesso_editar', args=[self.target.uuid, access.uuid],
        ), {
            'modulo': 'media', 'perfil': profile.pk, 'escopo': 'PROPRIOS',
            'justificativa': 'Aplicar perfil em acesso existente',
            'observacao': '', 'permissoes': [permission.pk],
        })
        self.assertRedirects(response, reverse(
            'gestao:usuario_acessos', args=[self.target.uuid],
        ))
        self.assertTrue(ConcessaoPermissao.objects.filter(
            acesso=access, permissao=extra, revogada_em__isnull=True,
        ).exists())


    def create_manager_with_access_permission(self, username):
        manager = get_user_model().objects.create_user(
            username,
            password="x",
            is_staff=True,
        )
        gestao_access = Permissao.objects.get(codigo="gestao.acessar")
        manage_permissions = Permissao.objects.get(
            codigo="gestao.gerenciar_permissoes"
        )
        access = AcessoModulo.objects.create(
            usuario=manager,
            modulo="gestao",
            concedido_por=self.master,
            justificativa="Preparação de gestor para teste HTTP",
        )
        for permission in (gestao_access, manage_permissions):
            ConcessaoPermissao.objects.create(
                acesso=access,
                usuario=manager,
                permissao=permission,
                concedida_por=self.master,
                justificativa="Preparação de gestor para teste HTTP",
            )
        return manager, access


    def test_status_acesso_get_retorna_405(self):
        access = AcessoModulo.objects.create(
            usuario=self.target,
            modulo="media",
            concedido_por=self.master,
            justificativa="Teste GET",
        )
        self.client.force_login(self.master)

        response = self.client.get(
            reverse(
                "gestao:usuario_acesso_status",
                args=[self.target.uuid, access.uuid],
            )
        )

        self.assertEqual(response.status_code, 405)


    def test_status_acesso_post_valido_retorna_302_e_suspende(self):
        access = AcessoModulo.objects.create(
            usuario=self.target,
            modulo="media",
            concedido_por=self.master,
            justificativa="Teste POST válido",
        )
        self.client.force_login(self.master)

        response = self.client.post(
            reverse(
                "gestao:usuario_acesso_status",
                args=[self.target.uuid, access.uuid],
            ),
            {
                "status": AcessoModulo.Status.SUSPENSO,
                "justificativa": "Suspensão via Gestão",
            },
        )

        self.assertEqual(response.status_code, 302)
        access.refresh_from_db()
        self.assertEqual(access.status, AcessoModulo.Status.SUSPENSO)


    def test_status_acesso_bloqueia_autoalteracao(self):
        manager, own_access = self.create_manager_with_access_permission(
            "gestao-manager-self-http"
        )
        self.client.force_login(manager)

        response = self.client.post(
            reverse(
                "gestao:usuario_acesso_status",
                args=[manager.uuid, own_access.uuid],
            ),
            {
                "status": AcessoModulo.Status.SUSPENSO,
                "justificativa": "Tentativa de autoalteração via HTTP",
            },
        )

        self.assertEqual(response.status_code, 403)
        own_access.refresh_from_db()
        self.assertEqual(own_access.status, AcessoModulo.Status.ATIVO)
        self.assertEqual(self.client.get(reverse(
            'gestao:usuario_acesso_editar', args=[manager.uuid, own_access.uuid],
        )).status_code, 403)


    def test_status_acesso_nao_master_nao_altera_master(self):
        manager, _ = self.create_manager_with_access_permission(
            "gestao-manager-master-http"
        )
        protected_master = get_user_model().objects.create_superuser(
            "gestao-protected-master-http",
            password="x",
        )
        access = AcessoModulo.objects.create(
            usuario=protected_master,
            modulo="media",
            concedido_por=self.master,
            justificativa="Acesso protegido MASTER",
        )
        self.client.force_login(manager)

        response = self.client.post(
            reverse(
                "gestao:usuario_acesso_status",
                args=[protected_master.uuid, access.uuid],
            ),
            {
                "status": AcessoModulo.Status.SUSPENSO,
                "justificativa": "Tentativa indevida via HTTP",
            },
        )

        self.assertEqual(response.status_code, 403)
        access.refresh_from_db()
        self.assertEqual(access.status, AcessoModulo.Status.ATIVO)


    def test_status_acesso_exige_csrf(self):
        access = AcessoModulo.objects.create(
            usuario=self.target,
            modulo="media",
            concedido_por=self.master,
            justificativa="Teste CSRF",
        )

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.master)

        response = client.post(
            reverse(
                "gestao:usuario_acesso_status",
                args=[self.target.uuid, access.uuid],
            ),
            {
                "status": AcessoModulo.Status.SUSPENSO,
                "justificativa": "POST sem CSRF",
            },
        )

        self.assertEqual(response.status_code, 403)
        access.refresh_from_db()
        self.assertEqual(access.status, AcessoModulo.Status.ATIVO)


    def test_status_acesso_revogado_nao_reativa_e_nao_gera_500(self):
        access = AcessoModulo.objects.create(
            usuario=self.target,
            modulo="media",
            concedido_por=self.master,
            justificativa="Acesso revogado para teste HTTP",
            status=AcessoModulo.Status.REVOGADO,
        )

        self.client.force_login(self.master)

        response = self.client.post(
            reverse(
                "gestao:usuario_acesso_status",
                args=[self.target.uuid, access.uuid],
            ),
            {
                "status": AcessoModulo.Status.ATIVO,
                "justificativa": "Tentativa de reativação via HTTP",
            },
        )

        self.assertEqual(response.status_code, 302)

        access.refresh_from_db()
        self.assertEqual(
            access.status,
            AcessoModulo.Status.REVOGADO,
        )
