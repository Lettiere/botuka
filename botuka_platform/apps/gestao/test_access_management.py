from django.contrib.auth import get_user_model
from django.test import TestCase
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
