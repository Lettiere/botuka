from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Perfil, PerfilPermissao, Permissao

from .authorization import pode
from .models import AcessoModulo, AuditoriaPermissao
from .permission_services import alterar_status_acesso, salvar_acesso_modulo


class ModuleAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.actor = User.objects.create_superuser("master-access", password="x")
        self.user = User.objects.create_user("module-user", password="x")
        self.news_access = Permissao.objects.get(codigo="news.acessar")
        self.news_create = Permissao.objects.get(codigo="news.cadastrar")
        self.media_access = Permissao.objects.get(codigo="media.acessar")

    def grant(self, module, permissions, **kwargs):
        return salvar_acesso_modulo(
            ator=self.actor, beneficiado=self.user, modulo=module,
            permissoes=permissions, justificativa="Teste automatizado", **kwargs,
        )

    def test_modulos_sao_independentes(self):
        news = self.grant("news", [self.news_access, self.news_create])
        media = self.grant("media", [self.media_access])
        self.assertTrue(pode(self.user, "news.cadastrar"))
        self.assertTrue(pode(self.user, "media.acessar"))
        alterar_status_acesso(
            ator=self.actor, acesso=news, status=AcessoModulo.Status.REVOGADO,
            justificativa="Revogação de teste",
        )
        self.assertFalse(pode(self.user, "news.cadastrar"))
        self.assertTrue(pode(self.user, "media.acessar"))
        self.assertEqual(media.status, AcessoModulo.Status.ATIVO)

    def test_expirado_revogado_e_suspenso_nao_autorizam(self):
        access = self.grant(
            "news", [self.news_access, self.news_create],
            valida_ate=timezone.now() - timedelta(minutes=1),
        )
        self.assertFalse(pode(self.user, "news.cadastrar"))
        access.valida_ate = None
        access.status = AcessoModulo.Status.SUSPENSO
        access.save()
        self.assertFalse(pode(self.user, "news.cadastrar"))

    def test_perfil_aplica_matriz_inicial_e_audita(self):
        profile = Perfil.objects.create(nome="NEWS_TEST_PROFILE")
        PerfilPermissao.objects.create(perfil=profile, permissao=self.news_access)
        PerfilPermissao.objects.create(perfil=profile, permissao=self.news_create)
        access = self.grant("news", [], perfil=profile)
        self.assertEqual(access.concessoes.filter(revogada_em__isnull=True).count(), 2)
        self.assertTrue(AuditoriaPermissao.objects.filter(usuario_beneficiado=self.user).exists())

    def test_superusuario_tem_acesso_global(self):
        self.assertTrue(pode(self.actor, "qualquer.acao"))

    def test_um_acesso_corrente_por_usuario_e_modulo(self):
        self.grant("news", [self.news_access])
        self.grant("news", [self.news_access, self.news_create])
        self.assertEqual(
            AcessoModulo.objects.filter(usuario=self.user, modulo="news").count(), 1,
        )


    def test_gestor_nao_pode_alterar_o_proprio_acesso(self):
        manager = get_user_model().objects.create_user(
            "access-manager-self",
            password="x",
        )
        gestao_access = Permissao.objects.get(codigo="gestao.acessar")
        manage_permissions = Permissao.objects.get(
            codigo="gestao.gerenciar_permissoes"
        )
        manager_access = salvar_acesso_modulo(
            ator=self.actor,
            beneficiado=manager,
            modulo="gestao",
            permissoes=[gestao_access, manage_permissions],
            justificativa="Preparação do gestor para teste",
        )

        with self.assertRaises(PermissionDenied):
            alterar_status_acesso(
                ator=manager,
                acesso=manager_access,
                status=AcessoModulo.Status.SUSPENSO,
                justificativa="Tentativa de autoalteração",
            )

        manager_access.refresh_from_db()
        self.assertEqual(manager_access.status, AcessoModulo.Status.ATIVO)


    def test_nao_master_nao_pode_alterar_acesso_de_master(self):
        User = get_user_model()
        manager = User.objects.create_user(
            "access-manager-master-target",
            password="x",
        )
        gestao_access = Permissao.objects.get(codigo="gestao.acessar")
        manage_permissions = Permissao.objects.get(
            codigo="gestao.gerenciar_permissoes"
        )
        salvar_acesso_modulo(
            ator=self.actor,
            beneficiado=manager,
            modulo="gestao",
            permissoes=[gestao_access, manage_permissions],
            justificativa="Preparação do gestor para teste",
        )

        master_target = User.objects.create_superuser(
            "protected-master-target",
            password="x",
        )
        protected_access = AcessoModulo.objects.create(
            usuario=master_target,
            modulo="news",
            concedido_por=self.actor,
            justificativa="Acesso MASTER protegido",
        )

        with self.assertRaises(PermissionDenied):
            alterar_status_acesso(
                ator=manager,
                acesso=protected_access,
                status=AcessoModulo.Status.SUSPENSO,
                justificativa="Tentativa indevida",
            )

        protected_access.refresh_from_db()
        self.assertEqual(protected_access.status, AcessoModulo.Status.ATIVO)


    def test_gestor_nao_pode_alterar_acesso_com_permissao_protegida(self):
        User = get_user_model()
        manager = User.objects.create_user(
            "access-manager-protected-permission",
            password="x",
        )
        target = User.objects.create_user(
            "access-target-protected-permission",
            password="x",
        )

        gestao_access = Permissao.objects.get(codigo="gestao.acessar")
        manage_permissions = Permissao.objects.get(
            codigo="gestao.gerenciar_permissoes"
        )
        salvar_acesso_modulo(
            ator=self.actor,
            beneficiado=manager,
            modulo="gestao",
            permissoes=[gestao_access, manage_permissions],
            justificativa="Preparação do gestor para teste",
        )

        protected_permission = Permissao.objects.create(
            modulo="news",
            grupo="Teste",
            codigo="news.protegida_status_teste",
            nome="Permissão protegida para teste de status",
            criticidade=Permissao.Criticidade.PROTEGIDA,
            protegida=True,
        )
        protected_access = salvar_acesso_modulo(
            ator=self.actor,
            beneficiado=target,
            modulo="news",
            permissoes=[self.news_access, protected_permission],
            justificativa="Acesso protegido para teste",
        )

        with self.assertRaises(PermissionDenied):
            alterar_status_acesso(
                ator=manager,
                acesso=protected_access,
                status=AcessoModulo.Status.SUSPENSO,
                justificativa="Tentativa sobre permissão protegida",
            )

        protected_access.refresh_from_db()
        self.assertEqual(protected_access.status, AcessoModulo.Status.ATIVO)


    def test_acesso_revogado_nao_pode_ser_reativado_diretamente(self):
        access = self.grant(
            "news",
            [self.news_access, self.news_create],
        )

        alterar_status_acesso(
            ator=self.actor,
            acesso=access,
            status=AcessoModulo.Status.REVOGADO,
            justificativa="Revogação definitiva para teste",
        )

        access.refresh_from_db()
        self.assertEqual(access.status, AcessoModulo.Status.REVOGADO)
        self.assertIsNotNone(access.revogado_em)
        self.assertIsNotNone(access.revogado_por)

        with self.assertRaises(ValidationError):
            alterar_status_acesso(
                ator=self.actor,
                acesso=access,
                status=AcessoModulo.Status.ATIVO,
                justificativa="Tentativa de reativação direta",
            )

        access.refresh_from_db()
        self.assertEqual(access.status, AcessoModulo.Status.REVOGADO)


    def test_suspensao_e_reativacao_normal_continuam_funcionando(self):
        access = self.grant(
            "news",
            [self.news_access, self.news_create],
        )
        self.assertTrue(pode(self.user, "news.cadastrar"))

        alterar_status_acesso(
            ator=self.actor,
            acesso=access,
            status=AcessoModulo.Status.SUSPENSO,
            justificativa="Suspensão temporária de teste",
        )
        access.refresh_from_db()
        self.assertEqual(access.status, AcessoModulo.Status.SUSPENSO)
        self.assertFalse(pode(self.user, "news.cadastrar"))

        alterar_status_acesso(
            ator=self.actor,
            acesso=access,
            status=AcessoModulo.Status.ATIVO,
            justificativa="Reativação após suspensão",
        )
        access.refresh_from_db()
        self.assertEqual(access.status, AcessoModulo.Status.ATIVO)
        self.assertTrue(pode(self.user, "news.cadastrar"))


    def test_revogacao_revoga_concessoes_e_registra_auditoria(self):
        access = self.grant(
            "news",
            [self.news_access, self.news_create],
        )
        self.assertEqual(
            access.concessoes.filter(revogada_em__isnull=True).count(),
            2,
        )

        alterar_status_acesso(
            ator=self.actor,
            acesso=access,
            status=AcessoModulo.Status.REVOGADO,
            justificativa="Revogação auditada de teste",
        )

        access.refresh_from_db()
        self.assertEqual(access.status, AcessoModulo.Status.REVOGADO)
        self.assertEqual(
            access.concessoes.filter(revogada_em__isnull=True).count(),
            0,
        )
        self.assertTrue(
            AuditoriaPermissao.objects.filter(
                usuario_beneficiado=self.user,
                acao=AuditoriaPermissao.Acao.REVOGAR,
            ).exists()
        )
        self.assertTrue(
            AuditoriaPermissao.objects.filter(
                usuario_beneficiado=self.user,
                acao=AuditoriaPermissao.Acao.ALTERAR,
            ).exists()
        )


    def test_gestor_nao_pode_conceder_acesso_a_superusuario(self):
        User = get_user_model()

        manager = User.objects.create_user(
            "access-manager-superuser-target",
            password="x",
        )
        gestao_access = Permissao.objects.get(codigo="gestao.acessar")
        manage_permissions = Permissao.objects.get(
            codigo="gestao.gerenciar_permissoes"
        )

        salvar_acesso_modulo(
            ator=self.actor,
            beneficiado=manager,
            modulo="gestao",
            permissoes=[gestao_access, manage_permissions],
            justificativa="Preparação do gestor para teste",
        )

        master_target = User.objects.create_superuser(
            "access-superuser-target",
            password="x",
        )

        with self.assertRaises(PermissionDenied):
            salvar_acesso_modulo(
                ator=manager,
                beneficiado=master_target,
                modulo="news",
                permissoes=[self.news_access],
                justificativa="Tentativa sobre superusuário",
            )

        self.assertFalse(
            AcessoModulo.objects.filter(
                usuario=master_target,
                modulo="news",
            ).exists()
        )


    def test_gestor_nao_pode_herdar_permissao_protegida_por_perfil(self):
        User = get_user_model()

        manager = User.objects.create_user(
            "access-manager-protected-profile",
            password="x",
        )
        target = User.objects.create_user(
            "access-target-protected-profile",
            password="x",
        )

        gestao_access = Permissao.objects.get(codigo="gestao.acessar")
        manage_permissions = Permissao.objects.get(
            codigo="gestao.gerenciar_permissoes"
        )

        salvar_acesso_modulo(
            ator=self.actor,
            beneficiado=manager,
            modulo="gestao",
            permissoes=[gestao_access, manage_permissions],
            justificativa="Preparação do gestor para teste",
        )

        protected_permission = Permissao.objects.create(
            modulo="news",
            grupo="Teste",
            codigo="news.protegida_perfil_teste",
            nome="Permissão protegida herdada por perfil",
            criticidade=Permissao.Criticidade.PROTEGIDA,
            protegida=True,
        )

        protected_profile = Perfil.objects.create(
            nome="NEWS_PROTECTED_PROFILE_TEST"
        )
        PerfilPermissao.objects.create(
            perfil=protected_profile,
            permissao=protected_permission,
        )

        with self.assertRaises(PermissionDenied):
            salvar_acesso_modulo(
                ator=manager,
                beneficiado=target,
                modulo="news",
                permissoes=[],
                perfil=protected_profile,
                justificativa="Tentativa de herança protegida",
            )

        self.assertFalse(
            AcessoModulo.objects.filter(
                usuario=target,
                modulo="news",
            ).exists()
        )
