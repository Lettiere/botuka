from datetime import time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import AgendaDisponibilidade, AgendaProfissional, AgendaProfissionalServico, Agendamento
from apps.locations.models import Cidade, Estado, Pais
from apps.accounts.models import AcessoModulo, ConcessaoPermissao
from apps.core.models import Permissao
from apps.organizations.models import (
    Capacidade,
    Empresa,
    EmpresaCapacidade,
    EmpresaPropriedade,
    EmpresaUsuario,
)
from apps.products.models import Produto
from apps.services.models import AreaProfissional, FormaCobranca, Profissao, Servico, Setor
from apps.taxonomy.models import Categoria, Subcategoria


class EmpresaCadastroSimplesTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser(
            username='wizard-owner', password='senha-forte'
        )
        self.client.force_login(self.usuario)
        pais = Pais.objects.create(
            nome='Brasil', codigo_iso_2='BR', codigo_iso_3='BRA'
        )
        self.estado = Estado.objects.create(pais=pais, nome='São Paulo', sigla='SP')
        self.cidade = Cidade.objects.create(estado=self.estado, nome='Botucatu')
        self.categoria_empresa = Categoria.objects.create(
            nome='Categoria empresa teste'
        )
        self.subcategoria_empresa = Subcategoria.objects.create(
            categoria=self.categoria_empresa,
            nome='Segmento empresa teste',
        )

    def _conceder_empresas_criar(self, usuario):
        permissao, _ = Permissao.objects.get_or_create(
            codigo='empresas.criar',
            defaults={'nome': 'Criar empresas', 'descricao': 'Criar empresas'},
        )
        acesso = AcessoModulo.objects.create(
            usuario=usuario,
            modulo='empresas',
            concedido_por=self.usuario,
            justificativa='Teste do cadastro administrativo',
        )
        ConcessaoPermissao.objects.create(
            acesso=acesso,
            usuario=usuario,
            permissao=permissao,
            concedida_por=self.usuario,
            justificativa='Teste do cadastro administrativo',
        )

    def _dados_cadastro_simples(self, **overrides):
        dados = {
            'nome_fantasia': 'Estabelecimento simples',
            'categoria_empresa': self.categoria_empresa.pk,
            'subcategoria_empresa': self.subcategoria_empresa.pk,
            'estado': self.estado.pk,
            'cidade': self.cidade.pk,
            'email': 'contato@example.com',
            'status': Empresa.Status.ATIVA,
        }
        dados.update(overrides)
        return dados

    def test_master_acessa_cadastro_simples_e_renderiza_template(self):
        response = self.client.get(reverse('painel:empresa_adicionar'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['form'].fields['status'].initial,
            Empresa.Status.ATIVA,
        )
        self.assertTemplateUsed(
            response,
            'painel/empresas/cadastro_simples.html',
        )

    def test_cadastro_simples_cria_empresa_ativa_sem_proprietario_e_volta_ao_formulario(self):
        response = self.client.post(
            reverse('painel:empresa_adicionar'),
            self._dados_cadastro_simples(),
        )

        self.assertEqual(Empresa.objects.count(), 1)
        empresa = Empresa.objects.get()
        self.assertEqual(empresa.status, Empresa.Status.ATIVA)
        self.assertTrue(empresa.perfil_publico)
        self.assertTrue(empresa.ativo)
        self.assertEqual(empresa.cadastro_etapa, 1)
        self.assertIsNone(empresa.usuario_proprietario)
        self.assertEqual(empresa.criado_por, self.usuario)
        self.assertFalse(EmpresaUsuario.objects.filter(empresa=empresa).exists())
        self.assertFalse(EmpresaPropriedade.objects.filter(empresa=empresa).exists())
        self.assertRedirects(
            response,
            reverse('painel:empresa_adicionar'),
        )
        self.assertEqual(
            self.client.get(reverse('publico:empresa', args=[empresa.slug])).status_code,
            200,
        )
        self.assertContains(self.client.get(reverse('publico:empresas')), empresa.nome_fantasia)

    def test_cadastro_simples_aceita_rascunho(self):
        response = self.client.post(
            reverse('painel:empresa_adicionar'),
            self._dados_cadastro_simples(status=Empresa.Status.RASCUNHO),
        )

        self.assertRedirects(response, reverse('painel:empresa_adicionar'))
        empresa = Empresa.objects.get()
        self.assertEqual(empresa.status, Empresa.Status.RASCUNHO)
        self.assertTrue(empresa.ativo)
        self.assertFalse(empresa.perfil_publico)
        self.assertEqual(
            self.client.get(reverse('publico:empresa', args=[empresa.slug])).status_code,
            404,
        )
        listagem_response = self.client.get(reverse('publico:empresas'))
        self.assertNotIn(empresa, listagem_response.context['empresas'])

    def test_cadastro_simples_rejeita_status_nao_permitido(self):
        response = self.client.post(
            reverse('painel:empresa_adicionar'),
            self._dados_cadastro_simples(status=Empresa.Status.PENDENTE),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('status', response.context['form'].errors)
        self.assertFalse(Empresa.objects.exists())

    def test_usuario_com_empresas_criar_consegue_acessar(self):
        usuario_permitido = get_user_model().objects.create_user(
            username='cadastro-administrativo', password='senha-forte'
        )
        self._conceder_empresas_criar(usuario_permitido)
        self.client.force_login(usuario_permitido)

        response = self.client.get(reverse('painel:empresa_adicionar'))

        self.assertEqual(response.status_code, 200)

    def test_delegado_cria_ativa_e_rascunho_com_redirect_acessivel(self):
        delegado = get_user_model().objects.create_user(
            username='delegado-criacao', password='senha-forte'
        )
        self._conceder_empresas_criar(delegado)
        self.client.force_login(delegado)

        for status in (Empresa.Status.ATIVA, Empresa.Status.RASCUNHO):
            with self.subTest(status=status):
                response = self.client.post(
                    reverse('painel:empresa_adicionar'),
                    self._dados_cadastro_simples(
                        nome_fantasia=f'Empresa delegada {status}',
                        email=f'{status.lower()}@example.com',
                        status=status,
                    ),
                    follow=True,
                )
                self.assertEqual(
                    response.redirect_chain,
                    [(reverse('painel:empresa_adicionar'), 302)],
                )
                self.assertEqual(response.status_code, 200)
                empresa = Empresa.objects.get(nome_fantasia=f'Empresa delegada {status}')
                self.assertContains(response, empresa.nome_fantasia)
                self.assertContains(response, empresa.get_status_display())
                self.assertEqual(empresa.criado_por, delegado)
                self.assertIsNone(empresa.usuario_proprietario)
                self.assertFalse(EmpresaUsuario.objects.filter(empresa=empresa).exists())
                self.assertFalse(EmpresaPropriedade.objects.filter(empresa=empresa).exists())

    def test_modal_oculta_cadastro_simples_sem_permissao(self):
        usuario = get_user_model().objects.create_user(
            username='modal-sem-permissao', password='senha-forte'
        )
        self.client.force_login(usuario)

        response = self.client.get(reverse('home'))

        self.assertNotContains(response, 'Cadastro simplificado')

    def test_modal_exibe_cadastro_simples_com_permissao(self):
        usuario = get_user_model().objects.create_user(
            username='modal-com-permissao', password='senha-forte'
        )
        self._conceder_empresas_criar(usuario)
        self.client.force_login(usuario)

        response = self.client.get(reverse('home'))

        self.assertContains(response, 'Cadastro simplificado')

    def test_usuario_sem_permissao_nao_acessa_nem_cadastra(self):
        usuario_sem_permissao = get_user_model().objects.create_user(
            username='sem-cadastro-administrativo', password='senha-forte'
        )
        self.client.force_login(usuario_sem_permissao)

        get_response = self.client.get(reverse('painel:empresa_adicionar'))
        post_response = self.client.post(
            reverse('painel:empresa_adicionar'), self._dados_cadastro_simples()
        )

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        self.assertFalse(Empresa.objects.exists())

    def test_cadastro_simples_post_invalido_nao_cria_empresa(self):
        response = self.client.post(reverse('painel:empresa_adicionar'), {})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Empresa.objects.exists())

    def test_cadastro_simples_exige_algum_contato(self):
        response = self.client.post(
            reverse('painel:empresa_adicionar'),
            self._dados_cadastro_simples(email=''),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Informe pelo menos um contato')
        self.assertFalse(Empresa.objects.exists())

    def test_cadastro_simples_rejeita_subcategoria_de_outra_categoria(self):
        outra_categoria = Categoria.objects.create(nome='Outra categoria')
        outra_subcategoria = Subcategoria.objects.create(
            categoria=outra_categoria,
            nome='Outro tipo',
        )

        response = self.client.post(
            reverse('painel:empresa_adicionar'),
            self._dados_cadastro_simples(
                subcategoria_empresa=outra_subcategoria.pk,
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Empresa.objects.exists())
        self.assertIn('subcategoria_empresa', response.context['form'].errors)

    def test_cadastro_simples_rejeita_cidade_de_outro_estado(self):
        outro_estado = Estado.objects.create(
            pais=self.estado.pais,
            nome='Paraná',
            sigla='PR',
        )
        outra_cidade = Cidade.objects.create(
            estado=outro_estado,
            nome='Curitiba',
        )

        response = self.client.post(
            reverse('painel:empresa_adicionar'),
            self._dados_cadastro_simples(cidade=outra_cidade.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Empresa.objects.exists())
        self.assertIn('cidade', response.context['form'].errors)

    def test_cadastro_simples_rejeita_subcategoria_removida(self):
        self.subcategoria_empresa.delete()

        response = self.client.post(
            reverse('painel:empresa_adicionar'),
            self._dados_cadastro_simples(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Empresa.objects.exists())
        self.assertIn('subcategoria_empresa', response.context['form'].errors)

    def test_cadastro_simples_ignora_limite_comercial_do_executor(self):
        Empresa.objects.create(
            usuario_proprietario=self.usuario,
            nome_fantasia='Empresa já existente',
        )

        response = self.client.post(
            reverse('painel:empresa_adicionar'),
            self._dados_cadastro_simples(),
        )

        self.assertRedirects(response, reverse('painel:empresa_adicionar'))
        self.assertEqual(Empresa.objects.count(), 2)

    def test_cadastro_simples_reverte_empresa_se_salvamento_falhar(self):
        salvar_original = Empresa.save

        def salvar_e_falhar(instance, *args, **kwargs):
            salvar_original(instance, *args, **kwargs)
            raise RuntimeError('falha simulada após persistência')

        with patch.object(Empresa, 'save', new=salvar_e_falhar):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse('painel:empresa_adicionar'),
                    self._dados_cadastro_simples(),
                )

        self.assertFalse(Empresa.objects.exists())


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
        self.categoria_empresa = Categoria.objects.create(
            nome='Categoria empresa teste'
        )
        self.subcategoria_empresa = Subcategoria.objects.create(
            categoria=self.categoria_empresa,
            nome='Segmento empresa teste',
        )

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
            (2, {
                'atuacao': atuacao,
                'categoria_empresa': self.categoria_empresa.pk,
                'subcategoria_empresa': self.subcategoria_empresa.pk,
            }),
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
                self.assertContains(response, '>Produtos</span>')
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
            EmpresaCapacidade.objects.update_or_create(
                empresa=empresa, capacidade=capacidade,
                defaults={
                    'status': EmpresaCapacidade.Status.APROVADA,
                    'ativo': True,
                },
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
        self.assertEqual(agenda['estado'], 'PENDENTE DE CONFIGURAÇÃO')
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
