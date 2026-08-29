from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Auditoria
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Assinatura, Empresa, Plano, UsuarioLimitePersonalizado
from apps.organizations.plans import (
    LimiteUsuarioService,
    obter_limite_empresas,
    obter_limite_servicos,
    total_servicos_utilizados,
    usuario_pode_criar_servico,
)
from apps.organizations.services.commercial_limits import salvar_limite_personalizado
from apps.services.models import AreaProfissional, FormaCobranca, Profissao, Servico, Setor, TipoServico


class SubscriptionLimitsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user('quota_owner', password='senha-forte')
        cls.collaborator = User.objects.create_user('quota_collab', password='senha-forte')
        pais = Pais.objects.create(nome='Brasil Quota', codigo_iso_2='BQ', codigo_iso_3='BQT')
        estado = Estado.objects.create(pais=pais, nome='Estado Quota', sigla='EQ')
        cidade = Cidade.objects.create(estado=estado, nome='Cidade Quota')
        cls.company = Empresa.objects.create(
            usuario_proprietario=cls.owner, nome_fantasia='Empresa da Cota',
            cidade=cidade, estado=estado, status=Empresa.Status.ATIVA,
        )
        cls.sector = Setor.objects.create(nome='Setor Cota')
        cls.area = AreaProfissional.objects.create(
            setor=cls.sector, nome='Área da Cota'
        )
        cls.profession = Profissao.objects.create(
            setor=cls.sector, area=cls.area, nome='Profissão Cota'
        )
        cls.service_type = TipoServico.objects.create(nome='Tipo Cota')
        cls.billing = FormaCobranca.objects.create(nome='Cobrança Cota')

    def create_service(self, title, provider=Servico.PrestadorTipo.PESSOA_FISICA,
                       responsible=None, company=None, status=Servico.Status.RASCUNHO):
        return Servico.objects.create(
            usuario_responsavel=responsible or self.owner,
            empresa=company,
            prestador_tipo=provider,
            setor=self.sector,
            area=self.area,
            profissao=self.profession,
            tipo_servico=self.service_type,
            forma_cobranca=self.billing,
            titulo=title,
            status=status,
        )

    def test_initial_plan_service_limits_and_nullable_prices(self):
        expected = {
            Plano.Codigo.GRATUITO: 3, Plano.Codigo.BRONZE: 6,
            Plano.Codigo.PRATA: 12, Plano.Codigo.OURO: 18,
            Plano.Codigo.PREMIUM: 30, Plano.Codigo.EMPRESARIAL: 50,
            Plano.Codigo.CORPORATIVO: 100, Plano.Codigo.PERSONALIZADO: None,
        }
        for code, limit in expected.items():
            with self.subTest(code=code):
                plan = Plano.objects.get(codigo=code)
                self.assertEqual(plan.limite_servicos, limit)
                self.assertEqual(plan.empresas_inclusas, 1)
                self.assertEqual(plan.preco_empresa_adicional, Decimal('50.00'))
                self.assertIsNone(plan.preco_mensal_pf)
                self.assertIsNone(plan.preco_mensal_pj)
                self.assertFalse(plan.ilimitado_servicos)
                self.assertFalse(plan.ilimitado_empresas)

    def test_enterprise_and_corporate_ranges_are_validated(self):
        empresarial = Plano.objects.get(codigo=Plano.Codigo.EMPRESARIAL)
        empresarial.limite_servicos = 49
        with self.assertRaises(ValidationError):
            empresarial.full_clean()
        corporativo = Plano.objects.get(codigo=Plano.Codigo.CORPORATIVO)
        corporativo.limite_servicos = 201
        with self.assertRaises(ValidationError):
            corporativo.full_clean()

    def test_free_combines_pf_and_company_services_under_owner(self):
        self.create_service('PF 1')
        self.create_service('PF 2', status=Servico.Status.PAUSADO)
        self.create_service(
            'PJ colaborador', provider=Servico.PrestadorTipo.EMPRESA,
            responsible=self.collaborator, company=self.company,
            status=Servico.Status.REJEITADO,
        )
        self.assertEqual(total_servicos_utilizados(self.owner), 3)
        self.assertEqual(total_servicos_utilizados(self.collaborator), 0)
        self.assertFalse(usuario_pode_criar_servico(self.owner).permitido)

    def test_only_soft_deleted_service_stops_counting(self):
        service = self.create_service('Será removido', status=Servico.Status.BLOQUEADO)
        self.assertEqual(total_servicos_utilizados(self.owner), 1)
        service.delete()
        self.assertEqual(total_servicos_utilizados(self.owner), 0)

    def test_active_subscription_changes_service_limit(self):
        bronze = Plano.objects.get(codigo=Plano.Codigo.BRONZE)
        Assinatura.objects.create(usuario=self.owner, plano=bronze)
        self.assertEqual(obter_limite_servicos(self.owner), 6)

    def test_personalized_limit_comes_from_subscription_contract(self):
        personalized = Plano.objects.get(codigo=Plano.Codigo.PERSONALIZADO)
        Assinatura.objects.create(
            usuario=self.owner, plano=personalized,
            limite_servicos_contratado=175,
        )
        self.assertEqual(obter_limite_servicos(self.owner), 175)

    def test_corporate_contract_limit_respects_range(self):
        corporate = Plano.objects.get(codigo=Plano.Codigo.CORPORATIVO)
        subscription = Assinatura(
            usuario=self.owner, plano=corporate,
            limite_servicos_contratado=201,
        )
        with self.assertRaises(ValidationError):
            subscription.full_clean()

    def test_service_pf_pj_database_constraint(self):
        invalid = Servico(
            usuario_responsavel=self.owner, empresa=self.company,
            prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA,
            setor=self.sector, profissao=self.profession,
            tipo_servico=self.service_type, forma_cobranca=self.billing,
            titulo='PF inválido', slug='pf-invalido',
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Servico.all_objects.bulk_create([invalid])

    def test_subscription_pf_pj_database_constraint(self):
        bronze = Plano.objects.get(codigo=Plano.Codigo.BRONZE)
        invalid = Assinatura(
            usuario=self.owner, plano=bronze,
            tipo_contratante=Assinatura.TipoContratante.PF,
            empresa_contratante=self.company,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Assinatura.objects.bulk_create([invalid])


class PersonalizedCommercialLimitsTests(SubscriptionLimitsTests):
    def _beneficio(self, **overrides):
        defaults = {
            'usuario': self.owner,
            'ativo': True,
            'empresas_ilimitadas': False,
            'servicos_ilimitados': False,
            'limite_empresas': 5,
            'limite_servicos': 30,
            'inicio': timezone.now() - timedelta(days=1),
            'motivo': 'Cliente especial',
            'concedido_por': self.master,
        }
        defaults.update(overrides)
        return UsuarioLimitePersonalizado.objects.create(**defaults)

    def setUp(self):
        self.master = get_user_model().objects.create_superuser(
            username='master-limites', email='master-limites@example.com',
            password='SenhaSegura#2026',
        )

    def test_limite_personalizado_fica_acima_do_plano(self):
        self._beneficio()
        self.assertEqual(obter_limite_empresas(self.owner), 5)
        self.assertEqual(obter_limite_servicos(self.owner), 30)
        self.assertTrue(LimiteUsuarioService.obter_limites(self.owner).personalizado)

    def test_beneficio_ilimitado(self):
        self._beneficio(
            empresas_ilimitadas=True, servicos_ilimitados=True,
            limite_empresas=None, limite_servicos=None,
        )
        self.assertIsNone(obter_limite_empresas(self.owner))
        self.assertIsNone(obter_limite_servicos(self.owner))

    def test_beneficio_expirado_ou_suspenso_volta_ao_gratuito(self):
        self._beneficio(fim=timezone.now() - timedelta(minutes=1))
        self.assertEqual(obter_limite_empresas(self.owner), 1)
        self.assertEqual(obter_limite_servicos(self.owner), 3)
        UsuarioLimitePersonalizado.objects.update(fim=None, ativo=False)
        self.assertEqual(obter_limite_empresas(self.owner), 1)
        self.assertEqual(obter_limite_servicos(self.owner), 3)

    def test_planos_pagos_continuam_sendo_resolvidos_sem_override(self):
        expected = {
            Plano.Codigo.BRONZE: 6, Plano.Codigo.PRATA: 12,
            Plano.Codigo.OURO: 18, Plano.Codigo.PREMIUM: 30,
        }
        for codigo, limite in expected.items():
            Assinatura.objects.filter(usuario=self.owner).delete()
            Assinatura.objects.create(
                usuario=self.owner, plano=Plano.objects.get(codigo=codigo),
            )
            self.assertEqual(obter_limite_servicos(self.owner), limite)

    def test_master_concede_e_audita_sem_promover_usuario(self):
        dados = {
            'ativo': True, 'empresas_ilimitadas': False,
            'servicos_ilimitados': False, 'limite_empresas': 10,
            'limite_servicos': 100, 'inicio': timezone.now(), 'fim': None,
            'motivo': 'Rede de restaurantes', 'observacoes': '',
        }
        salvar_limite_personalizado(
            executor=self.master, usuario=self.owner, dados=dados,
        )
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_staff)
        self.assertFalse(self.owner.is_superuser)
        self.assertTrue(Auditoria.objects.filter(
            acao='LIMITE_PERSONALIZADO_CONCEDER',
        ).exists())

    def test_usuario_comum_e_administrador_nao_concedem(self):
        dados = {
            'ativo': True, 'empresas_ilimitadas': False,
            'servicos_ilimitados': False, 'limite_empresas': 5,
            'limite_servicos': 30, 'inicio': timezone.now(), 'fim': None,
            'motivo': 'Tentativa', 'observacoes': '',
        }
        for executor in (self.owner, self.collaborator):
            executor.is_staff = executor == self.collaborator
            executor.save(update_fields=['is_staff'])
            with self.assertRaises(PermissionDenied):
                salvar_limite_personalizado(
                    executor=executor, usuario=self.owner, dados=dados,
                )

    def test_idor_da_tela_master_e_bloqueado(self):
        self.client.force_login(self.owner)
        resposta = self.client.post(reverse(
            'painel:limite_comercial_editar', kwargs={'uuid': self.owner.uuid},
        ), {'limite_empresas': 99, 'limite_servicos': 999})
        self.assertEqual(resposta.status_code, 403)

    def test_limite_backend_bloqueia_e_override_libera_empresa_e_servico(self):
        self.assertFalse(LimiteUsuarioService.pode_criar_empresa(self.owner).permitido)
        for numero in range(3):
            self.create_service(f'Serviço limite {numero}')
        self.assertFalse(LimiteUsuarioService.pode_criar_servico(self.owner).permitido)
        self._beneficio(limite_empresas=2, limite_servicos=4)
        self.assertTrue(LimiteUsuarioService.pode_criar_empresa(self.owner).permitido)
        self.assertTrue(LimiteUsuarioService.pode_criar_servico(self.owner).permitido)
