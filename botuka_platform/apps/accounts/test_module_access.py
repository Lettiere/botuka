from datetime import timedelta

from django.contrib.auth import get_user_model
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
