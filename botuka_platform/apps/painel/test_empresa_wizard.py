from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import AgendaDisponibilidade, AgendaProfissional, AgendaProfissionalServico, Agendamento
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Capacidade, Empresa, EmpresaCapacidade, EmpresaUsuario
from apps.products.models import Produto
from apps.services.models import AreaProfissional, FormaCobranca, Profissao, Servico, Setor


class EmpresaWizardTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='wizard-owner', password='senha-forte'
        )
        self.client.force_login(self.usuario)
        pais = Pais.objects.create(
            nome='Brasil', codigo_iso_2='BR', codigo_iso_3='BRA'
        )
        self.estado = Estado.objects.create(pais=pais, nome='São Paulo', sigla='SP')
        self.cidade = Cidade.objects.create(estado=self.estado, nome='Botucatu')

    def _post_etapa(self, empresa, etapa, dados, acao='continuar'):
        return self.client.post(
            reverse('painel:empresa_configurar', kwargs={
                'uuid': empresa.uuid, 'etapa': etapa,
            }),
            {**dados, 'acao': acao},
        )

    def _executar_fluxo(self, atuacao, modalidade=''):
        response = self.client.post(reverse('painel:empresa_criar'), {
            'tipo_cadastro': Empresa.TipoCadastro.INFORMAL,
            'nome_fantasia': f'Empresa {atuacao}',
            'acao': 'continuar',
        })
        self.assertEqual(response.status_code, 302)
        empresa = Empresa.objects.get(nome_fantasia=f'Empresa {atuacao}')

        etapas = (
            (2, {'atuacao': atuacao}),
            (3, {'descricao_curta': 'Apresentação da empresa'}),
            (4, {'email': 'empresa@example.com'}),
            (5, {'estado': self.estado.pk, 'cidade': self.cidade.pk}),
            (6, {
                'modalidade_comercial': modalidade,
                'atende_online': 'on',
                'horario_atendimento': 'Segunda a sexta',
            }),
            (7, {'perfil_publico': 'on'}),
        )
        for etapa, dados in etapas:
            response = self._post_etapa(empresa, etapa, dados)
            self.assertNotEqual(response.status_code, 500, f'Falha no step {etapa}')
            self.assertEqual(response.status_code, 302, response.context and response.context['form'].errors)

        empresa.refresh_from_db()
        self.assertEqual(empresa.status, Empresa.Status.PENDENTE)
        return empresa

    def test_primeira_etapa_cria_rascunho_persistente_e_vinculo(self):
        response = self.client.post(reverse('painel:empresa_criar'), {
            'tipo_cadastro': Empresa.TipoCadastro.INFORMAL,
            'nome_fantasia': 'Negócio em configuração',
            'acao': 'continuar',
        })

        empresa = Empresa.objects.get(nome_fantasia='Negócio em configuração')
        self.assertRedirects(
            response,
            reverse('painel:empresa_configurar', kwargs={
                'uuid': empresa.uuid, 'etapa': 2,
            }),
        )
        self.assertEqual(empresa.status, Empresa.Status.RASCUNHO)
        self.assertEqual(empresa.cadastro_etapa, 2)
        self.assertTrue(EmpresaUsuario.objects.filter(
            empresa=empresa, usuario=self.usuario, proprietario=True,
        ).exists())

    def test_wizard_nao_rebaixa_empresa_concluida(self):
        empresa = Empresa.objects.create(
            usuario_proprietario=self.usuario,
            tipo_cadastro=Empresa.TipoCadastro.INFORMAL,
            nome_fantasia='Empresa ativa',
            status=Empresa.Status.ATIVA,
        )
        EmpresaUsuario.objects.create(
            empresa=empresa, usuario=self.usuario,
            funcao=EmpresaUsuario.Funcao.PROPRIETARIO,
            proprietario=True, administrador=True, pode_editar=True,
        )

        response = self.client.get(reverse('painel:empresa_configurar', kwargs={
            'uuid': empresa.uuid, 'etapa': 1,
        }))

        self.assertRedirects(
            response,
            reverse('painel:empresa_editar', kwargs={'uuid': empresa.uuid}),
        )
        empresa.refresh_from_db()
        self.assertEqual(empresa.status, Empresa.Status.ATIVA)

    def test_fluxo_completo_servicos_nao_valida_modalidade_ausente_no_step_7(self):
        empresa = self._executar_fluxo(Empresa.Atuacao.SERVICOS)
        self.assertEqual(empresa.modalidade_comercial, '')

    def test_fluxo_completo_comercio_exige_e_preserva_modalidade(self):
        empresa = self._executar_fluxo(
            Empresa.Atuacao.COMERCIO, Empresa.ModalidadeComercial.VAREJO,
        )
        self.assertEqual(empresa.modalidade_comercial, Empresa.ModalidadeComercial.VAREJO)

    def test_fluxo_completo_comercio_e_servicos_preserva_modalidade(self):
        empresa = self._executar_fluxo(
            Empresa.Atuacao.COMERCIO_E_SERVICOS,
            Empresa.ModalidadeComercial.AMBOS,
        )
        self.assertEqual(empresa.modalidade_comercial, Empresa.ModalidadeComercial.AMBOS)

    def test_servicos_oculta_modalidade_e_limpa_valor_legado(self):
        empresa = Empresa.objects.create(
            usuario_proprietario=self.usuario,
            tipo_cadastro=Empresa.TipoCadastro.INFORMAL,
            nome_fantasia='Serviços legado',
            atuacao=Empresa.Atuacao.SERVICOS,
        )
        EmpresaUsuario.objects.create(
            empresa=empresa, usuario=self.usuario,
            funcao=EmpresaUsuario.Funcao.PROPRIETARIO,
            proprietario=True, administrador=True, pode_editar=True,
        )
        Empresa.objects.filter(pk=empresa.pk).update(
            modalidade_comercial=Empresa.ModalidadeComercial.ATACADO
        )
        empresa.refresh_from_db()

        response = self.client.get(reverse('painel:empresa_configurar', kwargs={
            'uuid': empresa.uuid, 'etapa': 6,
        }))
        self.assertNotContains(response, 'name="modalidade_comercial"')
        response = self._post_etapa(empresa, 6, {'atende_local': 'on'})
        self.assertEqual(response.status_code, 302)
        empresa.refresh_from_db()
        self.assertEqual(empresa.modalidade_comercial, '')

    def test_outro_usuario_nao_acessa_wizard(self):
        empresa = Empresa.objects.create(
            usuario_proprietario=self.usuario,
            tipo_cadastro=Empresa.TipoCadastro.INFORMAL,
            nome_fantasia='Empresa protegida',
        )
        outro = get_user_model().objects.create_user('outro-wizard', password='senha')
        self.client.force_login(outro)
        response = self.client.get(reverse('painel:empresa_configurar', kwargs={
            'uuid': empresa.uuid, 'etapa': 2,
        }))
        self.assertEqual(response.status_code, 404)

    def test_dashboard_servicos_exibe_navegacao_e_cards_no_contexto_da_empresa(self):
        empresa = Empresa.objects.create(
            usuario_proprietario=self.usuario,
            tipo_cadastro=Empresa.TipoCadastro.INFORMAL,
            nome_fantasia='Painel Serviços',
            atuacao=Empresa.Atuacao.SERVICOS,
            status=Empresa.Status.ATIVA,
            perfil_publico=True,
            estado=self.estado,
            cidade=self.cidade,
        )
        EmpresaUsuario.objects.create(
            empresa=empresa, usuario=self.usuario,
            funcao=EmpresaUsuario.Funcao.PROPRIETARIO,
            proprietario=True, administrador=True, pode_editar=True,
            pode_gerenciar_equipe=True, pode_publicar_servico=True,
        )

        response = self.client.get(reverse('painel:empresa_detalhe', kwargs={
            'uuid': empresa.uuid,
        }))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Página pública')
        self.assertContains(response, 'Visão geral')
        self.assertContains(response, 'Serviços')
        self.assertContains(response, 'Agenda')
        self.assertContains(response, 'Equipe')
        self.assertContains(response, 'Capacidades')
        self.assertContains(response, 'QR Code')
        self.assertContains(response, 'Links')
        self.assertNotContains(response, '>Produtos</a>')
        self.assertContains(response, 'MINHA EMPRESA')
        self.assertContains(response, 'Agenda — configuração pendente')
        self.assertContains(response, 'data-navigation-open', count=2)
        self.assertNotContains(response, 'id="botukaExploreModal"')

    def test_dashboard_abre_rascunho_pendente_e_ativa_sem_consultar_limite_invalido(self):
        for indice, status in enumerate((
            Empresa.Status.RASCUNHO, Empresa.Status.PENDENTE, Empresa.Status.ATIVA,
        ), 1):
            empresa = Empresa.objects.create(
                usuario_proprietario=self.usuario,
                tipo_cadastro=Empresa.TipoCadastro.INFORMAL,
                nome_fantasia=f'Empresa Estado {indice}',
                atuacao=Empresa.Atuacao.COMERCIO,
                modalidade_comercial=Empresa.ModalidadeComercial.VAREJO,
                status=status,
            )
            EmpresaUsuario.objects.create(
                empresa=empresa, usuario=self.usuario,
                funcao=EmpresaUsuario.Funcao.PROPRIETARIO,
                proprietario=True, administrador=True, pode_editar=True,
            )
            with self.subTest(status=status):
                response = self.client.get(reverse('painel:empresa_detalhe', kwargs={
                    'uuid': empresa.uuid,
                }))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, empresa.get_status_display())
                self.assertContains(response, 'Gerenciar produtos')
                if status != Empresa.Status.ATIVA:
                    self.assertIsNone(response.context['painel_empresa']['produtos']['limite'])

    def test_dashboard_resume_produtos_e_servicos_realmente_vinculados(self):
        empresa = Empresa.objects.create(
            usuario_proprietario=self.usuario,
            tipo_cadastro=Empresa.TipoCadastro.INFORMAL,
            nome_fantasia='Empresa com operação',
            atuacao=Empresa.Atuacao.COMERCIO_E_SERVICOS,
            modalidade_comercial=Empresa.ModalidadeComercial.AMBOS,
            status=Empresa.Status.PENDENTE,
        )
        EmpresaUsuario.objects.create(
            empresa=empresa, usuario=self.usuario,
            funcao=EmpresaUsuario.Funcao.PROPRIETARIO,
            proprietario=True, administrador=True, pode_editar=True,
        )
        Produto.objects.create(
            nome='Produto vinculado', categoria='Teste',
            descricao_curta='Resumo', descricao_completa='Descrição',
            preco=Decimal('10.00'), titular_tipo=Produto.TitularTipo.EMPRESA,
            criador_registro=self.usuario, proprietario=self.usuario,
            responsavel=self.usuario, empresa_proprietaria=empresa,
            status=Produto.Status.PUBLICADO,
        )
        setor = Setor.objects.create(nome='Setor painel')
        area = AreaProfissional.objects.create(setor=setor, nome='Área painel')
        profissao = Profissao.objects.create(
            setor=setor, area=area, nome='Profissão painel'
        )
        cobranca = FormaCobranca.objects.create(nome='Por serviço')
        Servico.objects.create(
            usuario_responsavel=self.usuario,
            prestador_tipo=Servico.PrestadorTipo.EMPRESA,
            empresa=empresa, setor=setor, area=area, profissao=profissao,
            forma_cobranca=cobranca, titulo='Serviço vinculado',
            status=Servico.Status.PENDENTE,
        )

        response = self.client.get(reverse('painel:empresa_detalhe', kwargs={
            'uuid': empresa.uuid,
        }))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['painel_empresa']['produtos']['total'], 1)
        self.assertEqual(response.context['painel_empresa']['produtos']['publicados'], 1)
        self.assertEqual(response.context['painel_empresa']['servicos']['total'], 1)
        self.assertEqual(response.context['painel_empresa']['servicos']['pendentes'], 1)
        self.assertContains(response, 'Produto vinculado')
        self.assertContains(response, 'Serviço vinculado')

    def test_dashboard_resume_agenda_profissional_disponibilidade_e_agendamento(self):
        empresa = Empresa.objects.create(
            usuario_proprietario=self.usuario,
            tipo_cadastro=Empresa.TipoCadastro.INFORMAL,
            nome_fantasia='Empresa com Agenda', atuacao=Empresa.Atuacao.SERVICOS,
            status=Empresa.Status.ATIVA,
        )
        membro = EmpresaUsuario.objects.create(
            empresa=empresa, usuario=self.usuario,
            funcao=EmpresaUsuario.Funcao.PROPRIETARIO,
            proprietario=True, administrador=True, pode_editar=True,
            pode_gerenciar_equipe=True,
        )
        for codigo, nome in (
            ('PRESTAR_SERVICOS', 'Prestar serviços'),
            ('ACEITAR_AGENDAMENTOS', 'Aceitar agendamentos'),
        ):
            capacidade, _ = Capacidade.objects.get_or_create(
                codigo=codigo, defaults={'nome': nome},
            )
            EmpresaCapacidade.objects.create(
                empresa=empresa, capacidade=capacidade,
                status=EmpresaCapacidade.Status.APROVADA,
            )
        setor = Setor.objects.create(nome='Setor Agenda painel')
        area = AreaProfissional.objects.create(setor=setor, nome='Área Agenda painel')
        profissao = Profissao.objects.create(
            setor=setor, area=area, nome='Profissional Agenda painel'
        )
        cobranca = FormaCobranca.objects.create(nome='Por atendimento')
        servico = Servico.objects.create(
            usuario_responsavel=self.usuario,
            prestador_tipo=Servico.PrestadorTipo.EMPRESA,
            empresa=empresa, setor=setor, area=area, profissao=profissao,
            forma_cobranca=cobranca, titulo='Atendimento agendável',
            status=Servico.Status.PUBLICADO,
        )
        profissional = AgendaProfissional.objects.create(empresa_usuario=membro)
        vinculo = AgendaProfissionalServico.objects.create(
            profissional=profissional, servico=servico, duracao_minutos=60,
        )
        inicio = timezone.localtime(timezone.now() + timedelta(days=2)).replace(
            hour=9, minute=0, second=0, microsecond=0,
        )
        AgendaDisponibilidade.objects.create(
            profissional=profissional, dia_semana=0,
            hora_inicio=time(8), hora_fim=time(12),
        )
        AgendaDisponibilidade.objects.filter(profissional=profissional).update(
            dia_semana=inicio.weekday(),
        )
        Agendamento.objects.create(
            profissional_servico=vinculo, cliente=self.usuario,
            inicio=inicio, fim=inicio + timedelta(hours=1),
            status=Agendamento.Status.CONFIRMADO,
        )

        response = self.client.get(reverse('painel:empresa_detalhe', kwargs={
            'uuid': empresa.uuid,
        }))
        agenda = response.context['painel_empresa']['agenda']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(agenda['estado'], 'ATIVA')
        self.assertEqual(agenda['profissionais'], 1)
        self.assertEqual(agenda['servicos'], 1)
        self.assertEqual(agenda['disponibilidades'], 1)
        self.assertEqual(agenda['proximos_total'], 1)
        self.assertContains(response, 'Atendimento agendável')

    def test_explorer_multiplas_empresas_seleciona_comercio_e_respeita_atuacao(self):
        servicos = Empresa.objects.create(
            usuario_proprietario=self.usuario, tipo_cadastro=Empresa.TipoCadastro.INFORMAL,
            nome_fantasia='Empresa Serviços', atuacao=Empresa.Atuacao.SERVICOS,
        )
        comercio = Empresa.objects.create(
            usuario_proprietario=self.usuario, tipo_cadastro=Empresa.TipoCadastro.INFORMAL,
            nome_fantasia='Empresa Comércio', atuacao=Empresa.Atuacao.COMERCIO,
            modalidade_comercial=Empresa.ModalidadeComercial.VAREJO,
        )
        for empresa in (servicos, comercio):
            EmpresaUsuario.objects.create(
                empresa=empresa, usuario=self.usuario,
                funcao=EmpresaUsuario.Funcao.PROPRIETARIO,
                proprietario=True, administrador=True, pode_editar=True,
            )

        response = self.client.get(reverse('painel:dashboard'), {
            'empresa_menu': comercio.uuid,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-company-menu-select')
        self.assertContains(response, 'Empresa Serviços')
        self.assertContains(response, 'Empresa Comércio')
        self.assertContains(response, reverse('painel:empresa_produtos', kwargs={'empresa_uuid': comercio.uuid}))
        self.assertNotContains(response, f'?empresa={comercio.id}')

    def test_explorer_comercio_e_servicos_renderiza_produtos_servicos_e_agenda(self):
        empresa = Empresa.objects.create(
            usuario_proprietario=self.usuario, tipo_cadastro=Empresa.TipoCadastro.INFORMAL,
            nome_fantasia='Empresa Mista', atuacao=Empresa.Atuacao.COMERCIO_E_SERVICOS,
            modalidade_comercial=Empresa.ModalidadeComercial.AMBOS,
        )
        EmpresaUsuario.objects.create(
            empresa=empresa, usuario=self.usuario,
            funcao=EmpresaUsuario.Funcao.PROPRIETARIO,
            proprietario=True, administrador=True, pode_editar=True,
        )

        response = self.client.get(reverse('painel:dashboard'))

        self.assertContains(response, reverse('painel:empresa_produtos', kwargs={'empresa_uuid': empresa.uuid}))
        self.assertContains(response, f'?empresa={empresa.id}')
        self.assertContains(response, 'Agenda — configuração pendente')
