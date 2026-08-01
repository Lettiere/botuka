from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Auditoria, Perfil, Permissao, PerfilPermissao
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.authorization import acao_autorizada, organizacoes_no_escopo
from apps.organizations.models import (
    Capacidade, Empresa, EmpresaCapacidade, EmpresaUsuario,
    EmpresaUsuarioPermissao, StatusCapacidadeMixin,
)
from apps.organizations.services.institutional import (
    atribuir_papel_global, atualizar_identidade_institucional,
    conceder_capacidade, convidar_membro,
)
from apps.painel.forms import EmpresaForm, EmpresaInstitucionalForm


class AuthorizationFoundationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.master = Usuario.objects.create_superuser(
            username='root-foundation', email='root@example.com', password='test-only',
        )
        cls.comum = Usuario.objects.create_user(
            username='common-foundation', email='common@example.com', password='test-only',
        )
        cls.outro = Usuario.objects.create_user(
            username='other-foundation', email='other@example.com', password='test-only',
        )
        pais = Pais.objects.create(nome='Brasil', codigo_iso_2='BR', codigo_iso_3='BRA')
        estado = Estado.objects.create(pais=pais, nome='São Paulo', sigla='SP')
        cidade = Cidade.objects.create(estado=estado, nome='Botucatu')
        cls.empresa = Empresa.objects.create(
            usuario_proprietario=cls.comum, nome_fantasia='Organização A',
            cidade=cidade, estado=estado,
        )
        cls.outra_empresa = Empresa.objects.create(
            usuario_proprietario=cls.outro, nome_fantasia='Organização B',
            cidade=cidade, estado=estado,
        )
        cls.vinculo = EmpresaUsuario.objects.create(
            empresa=cls.empresa, usuario=cls.comum,
            funcao=EmpresaUsuario.Funcao.PROPRIETARIO, proprietario=True,
        )
        cls.capacidade, _ = Capacidade.objects.get_or_create(
            codigo='PUBLICAR_ARTIGOS', defaults={'nome': 'Publicar artigos'},
        )

    def test_master_ve_todas_as_organizacoes_e_acessa_painel(self):
        self.assertEqual(organizacoes_no_escopo(self.master).count(), 2)
        self.client.force_login(self.master)
        self.assertEqual(
            self.client.get(reverse('painel:administracao_plataforma')).status_code, 200,
        )
        self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_master_cria_institucional_concede_e_revoga_capacidade(self):
        atualizar_identidade_institucional(
            executor=self.master, empresa=self.empresa,
            dados={'institucional': True, 'oficial': True, 'selo_oficial': True},
        )
        vinculo = conceder_capacidade(
            executor=self.master, empresa=self.empresa, codigo='PUBLICAR_ARTIGOS',
        )
        self.empresa.refresh_from_db()
        self.assertTrue(self.empresa.oficial)
        self.assertEqual(vinculo.status, StatusCapacidadeMixin.Status.APROVADA)
        self.assertTrue(Auditoria.objects.filter(acao='CAPACIDADE_CONCEDER').exists())

    def test_usuario_comum_nao_altera_institucional_e_tentativa_e_auditada(self):
        with self.assertRaises(PermissionDenied):
            atualizar_identidade_institucional(
                executor=self.comum, empresa=self.empresa, dados={'oficial': True},
            )
        self.empresa.refresh_from_db()
        self.assertFalse(self.empresa.oficial)
        self.assertTrue(Auditoria.objects.filter(
            acao='INSTITUCIONAL_ALTERAR_NEGADO', sucesso=False,
        ).exists())

    def test_capacidade_e_permissao_sao_exigidas_juntas(self):
        EmpresaUsuarioPermissao.objects.create(
            empresa_usuario=self.vinculo, codigo='CONTEUDO_PUBLICAR', permitido=True,
        )
        self.assertFalse(acao_autorizada(
            self.comum, self.empresa, capacidade='PUBLICAR_ARTIGOS',
            permissao='CONTEUDO_PUBLICAR',
        ))
        EmpresaCapacidade.objects.create(
            empresa=self.empresa, capacidade=self.capacidade,
            status=StatusCapacidadeMixin.Status.APROVADA, ativo=True,
        )
        self.assertTrue(acao_autorizada(
            self.comum, self.empresa, capacidade='PUBLICAR_ARTIGOS',
            permissao='CONTEUDO_PUBLICAR',
        ))

    def test_idor_e_queryset_ficam_restritos_a_organizacao(self):
        self.assertFalse(acao_autorizada(
            self.comum, self.outra_empresa, permissao='ORGANIZACAO_VISUALIZAR',
        ))
        self.assertQuerySetEqual(
            organizacoes_no_escopo(self.comum), [self.empresa], transform=lambda x: x,
        )

    def test_campos_institucionais_nao_estao_no_formulario_publico(self):
        form = EmpresaForm(usuario=self.comum)
        self.assertNotIn('oficial', form.fields)
        self.assertNotIn('tipo_organizacao', form.fields)
        self.assertIn('oficial', EmpresaInstitucionalForm().fields)

    def test_comum_nao_ve_aba_institucional_nem_forca_post(self):
        self.client.force_login(self.comum)
        resposta = self.client.get(reverse(
            'painel:empresa_institucional', kwargs={'uuid': self.empresa.uuid},
        ))
        self.assertEqual(resposta.status_code, 403)

    def test_somente_master_concede_papel_global_e_sem_autoelevacao(self):
        perfil, _ = Perfil.objects.get_or_create(nome='ADMIN_GLOBAL')
        with self.assertRaises(PermissionDenied):
            atribuir_papel_global(
                executor=self.comum, usuario=self.comum, papel='ADMIN_GLOBAL',
            )
        atribuir_papel_global(
            executor=self.master, usuario=self.outro, papel='ADMIN_GLOBAL',
        )
        self.outro.refresh_from_db()
        self.assertEqual(self.outro.perfil, perfil)

    def test_admin_global_so_age_com_permissao_delegada(self):
        perfil, _ = Perfil.objects.get_or_create(nome='ADMIN_GLOBAL')
        permissao, _ = Permissao.objects.get_or_create(
            codigo='institucional.gerenciar', defaults={'nome': 'Institucional'},
        )
        admin = get_user_model().objects.create_user(
            username='admin-global-foundation', perfil=perfil,
        )
        with self.assertRaises(PermissionDenied):
            atualizar_identidade_institucional(
                executor=admin, empresa=self.empresa, dados={'oficial': True},
            )
        PerfilPermissao.objects.get_or_create(perfil=perfil, permissao=permissao)
        atualizar_identidade_institucional(
            executor=admin, empresa=self.empresa, dados={'oficial': True},
        )
        self.empresa.refresh_from_db()
        self.assertTrue(self.empresa.oficial)

    def test_master_nomeia_administrador_institucional(self):
        vinculo = convidar_membro(
            executor=self.master, empresa=self.empresa, usuario=self.outro,
            funcao=EmpresaUsuario.Funcao.ADMINISTRADOR_INSTITUCIONAL,
        )
        self.assertEqual(vinculo.empresa, self.empresa)
