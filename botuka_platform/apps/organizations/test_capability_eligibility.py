from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Capacidade, Empresa, EmpresaCapacidade
from apps.painel.forms import EmpresaCapacidadeForm


class CapabilityEligibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.owner = Usuario.objects.create_user(
            username='eligibility-owner',
            email='eligibility-owner@example.com',
            password='test-only',
        )
        cls.other = Usuario.objects.create_user(
            username='eligibility-other',
            email='eligibility-other@example.com',
            password='test-only',
        )
        pais = Pais.objects.create(
            nome='Brasil Elegibilidade', codigo_iso_2='BE', codigo_iso_3='BEL',
        )
        cls.estado = Estado.objects.create(
            pais=pais, nome='Estado Elegibilidade', sigla='EE',
        )
        cls.cidade = Cidade.objects.create(
            estado=cls.estado, nome='Cidade Elegibilidade',
        )
        cls.capacidades = {}
        for codigo in (
            'VENDER_PRODUTOS',
            'PRESTAR_SERVICOS',
            'GERENCIAR_EQUIPE',
            'ACEITAR_AGENDAMENTOS',
            'PUBLICAR_ARTIGOS',
        ):
            cls.capacidades[codigo], _ = Capacidade.objects.get_or_create(
                codigo=codigo, defaults={'nome': codigo},
            )

    def empresa(self, atuacao, *, owner=None, nome=None):
        modalidade = (
            Empresa.ModalidadeComercial.VAREJO
            if atuacao in {
                Empresa.Atuacao.COMERCIO,
                Empresa.Atuacao.COMERCIO_E_SERVICOS,
            }
            else ''
        )
        return Empresa.objects.create(
            usuario_proprietario=owner or self.owner,
            nome_fantasia=nome or f'Empresa {atuacao or "legada"}',
            cidade=self.cidade,
            estado=self.estado,
            status=Empresa.Status.ATIVA,
            atuacao=atuacao,
            modalidade_comercial=modalidade,
        )

    def aprovar(self, empresa, codigo):
        vinculo, _ = EmpresaCapacidade.objects.update_or_create(
            empresa=empresa,
            capacidade=self.capacidades[codigo],
            defaults={
                'status': EmpresaCapacidade.Status.APROVADA,
                'ativo': True,
            },
        )
        return vinculo

    def test_servicos_recebe_prestar_servicos_aprovada_automaticamente(self):
        empresa = self.empresa(Empresa.Atuacao.SERVICOS)
        vinculo = empresa.capacidades_empresa.get(
            capacidade=self.capacidades['PRESTAR_SERVICOS'],
        )
        self.assertEqual(vinculo.status, EmpresaCapacidade.Status.APROVADA)
        self.assertTrue(vinculo.ativo)
        self.assertIsNotNone(vinculo.aprovado_em)
        self.assertIsNone(vinculo.aprovado_por)
        self.assertTrue(empresa.pode_publicar_servico)

    def test_comercio_e_servicos_recebe_aprovacao_automatica(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO_E_SERVICOS)
        self.assertTrue(empresa.capacidades_empresa.filter(
            capacidade=self.capacidades['PRESTAR_SERVICOS'],
            status=EmpresaCapacidade.Status.APROVADA,
            ativo=True,
        ).exists())

    def test_comercio_nao_recebe_prestar_servicos_automaticamente(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO)
        self.assertFalse(empresa.capacidades_empresa.filter(
            capacidade=self.capacidades['PRESTAR_SERVICOS'],
        ).exists())

    def test_pendente_existente_vira_aprovada_sem_duplicar(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO)
        vinculo = EmpresaCapacidade.objects.create(
            empresa=empresa,
            capacidade=self.capacidades['PRESTAR_SERVICOS'],
            status=EmpresaCapacidade.Status.PENDENTE,
            ativo=True,
        )
        empresa.atuacao = Empresa.Atuacao.SERVICOS
        empresa.save(update_fields=['atuacao', 'atualizado_em'])
        vinculo.refresh_from_db()
        self.assertEqual(vinculo.status, EmpresaCapacidade.Status.APROVADA)
        self.assertIsNotNone(vinculo.aprovado_em)
        self.assertEqual(empresa.capacidades_empresa.filter(
            capacidade=self.capacidades['PRESTAR_SERVICOS'],
        ).count(), 1)

    def test_mudanca_de_perfil_preserva_demais_capacidades(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO)
        extra = EmpresaCapacidade.objects.create(
            empresa=empresa,
            capacidade=self.capacidades['PUBLICAR_ARTIGOS'],
            status=EmpresaCapacidade.Status.PENDENTE,
            ativo=True,
        )
        empresa.atuacao = Empresa.Atuacao.COMERCIO_E_SERVICOS
        empresa.save(update_fields=['atuacao', 'atualizado_em'])
        extra.refresh_from_db()
        self.assertEqual(extra.status, EmpresaCapacidade.Status.PENDENTE)

    def opcoes_form(self, empresa):
        return set(
            EmpresaCapacidadeForm(empresa=empresa)
            .fields['capacidade']
            .queryset.values_list('codigo', flat=True)
        )

    def test_comercio_pode_solicitar_vender_produtos(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO)
        self.assertTrue(empresa.pode_solicitar_capacidade('VENDER_PRODUTOS'))
        self.assertIn('VENDER_PRODUTOS', self.opcoes_form(empresa))

    def test_comercio_nao_pode_solicitar_prestar_servicos(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO)
        self.assertFalse(empresa.pode_solicitar_capacidade('PRESTAR_SERVICOS'))

    def test_comercio_nao_pode_solicitar_aceitar_agendamentos(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO)
        self.assertFalse(empresa.pode_solicitar_capacidade('ACEITAR_AGENDAMENTOS'))

    def test_servicos_pode_solicitar_prestar_servicos(self):
        empresa = self.empresa(Empresa.Atuacao.SERVICOS)
        self.assertTrue(empresa.pode_solicitar_capacidade('PRESTAR_SERVICOS'))

    def test_servicos_nao_pode_solicitar_vender_produtos(self):
        empresa = self.empresa(Empresa.Atuacao.SERVICOS)
        self.assertFalse(empresa.pode_solicitar_capacidade('VENDER_PRODUTOS'))

    def test_servicos_com_capacidade_automatica_pode_solicitar_agenda(self):
        empresa = self.empresa(Empresa.Atuacao.SERVICOS)
        self.assertTrue(empresa.pode_solicitar_capacidade('ACEITAR_AGENDAMENTOS'))
        self.assertIn('ACEITAR_AGENDAMENTOS', self.opcoes_form(empresa))

    def test_servicos_com_prestar_servicos_pode_solicitar_agenda(self):
        empresa = self.empresa(Empresa.Atuacao.SERVICOS)
        self.aprovar(empresa, 'PRESTAR_SERVICOS')
        self.assertTrue(empresa.pode_solicitar_capacidade('ACEITAR_AGENDAMENTOS'))
        self.assertIn('ACEITAR_AGENDAMENTOS', self.opcoes_form(empresa))

    def test_comercio_e_servicos_pode_solicitar_vender_produtos(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO_E_SERVICOS)
        self.assertTrue(empresa.pode_solicitar_capacidade('VENDER_PRODUTOS'))

    def test_comercio_e_servicos_pode_solicitar_prestar_servicos(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO_E_SERVICOS)
        self.assertTrue(empresa.pode_solicitar_capacidade('PRESTAR_SERVICOS'))

    def test_comercio_e_servicos_com_prestar_servicos_solicita_agenda(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO_E_SERVICOS)
        self.aprovar(empresa, 'PRESTAR_SERVICOS')
        self.assertTrue(empresa.pode_solicitar_capacidade('ACEITAR_AGENDAMENTOS'))

    def test_capacidade_incompativel_existente_nao_e_apagada(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO)
        historica = self.aprovar(empresa, 'PRESTAR_SERVICOS')
        EmpresaCapacidadeForm(empresa=empresa)
        self.assertTrue(EmpresaCapacidade.objects.filter(pk=historica.pk).exists())
        self.assertFalse(historica.compativel_com_atuacao)

    def test_capacidade_aprovada_existente_continua_operacional(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO)
        self.aprovar(empresa, 'PRESTAR_SERVICOS')
        self.assertTrue(empresa.pode_publicar_servico)

    def test_empresa_legada_nao_perde_capacidades_existentes(self):
        empresa = self.empresa(None)
        self.aprovar(empresa, 'VENDER_PRODUTOS')
        self.aprovar(empresa, 'PRESTAR_SERVICOS')
        self.assertTrue(empresa.pode_publicar_produto)
        self.assertTrue(empresa.pode_publicar_servico)
        self.assertTrue(empresa.pode_solicitar_capacidade('GERENCIAR_EQUIPE'))

    def test_post_manual_de_capacidade_incompativel_e_bloqueado(self):
        empresa = self.empresa(Empresa.Atuacao.COMERCIO)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('painel:empresa_capacidades', kwargs={'uuid': empresa.uuid}),
            {'capacidade': self.capacidades['PRESTAR_SERVICOS'].pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EmpresaCapacidade.objects.filter(
            empresa=empresa,
            capacidade=self.capacidades['PRESTAR_SERVICOS'],
        ).exists())

    def test_empresa_a_nao_solicita_capacidade_para_empresa_b(self):
        empresa_b = self.empresa(
            Empresa.Atuacao.SERVICOS,
            owner=self.other,
            nome='Empresa B elegibilidade',
        )
        capacidades_antes = set(
            EmpresaCapacidade.objects.filter(empresa=empresa_b)
            .values_list('pk', flat=True)
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('painel:empresa_capacidades', kwargs={'uuid': empresa_b.uuid}),
            {'capacidade': self.capacidades['PRESTAR_SERVICOS'].pk},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            set(
                EmpresaCapacidade.objects.filter(empresa=empresa_b)
                .values_list('pk', flat=True)
            ),
            capacidades_antes,
        )
