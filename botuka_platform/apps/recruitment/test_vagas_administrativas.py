from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Empresa, EmpresaUsuario

from .models import Candidatura, CandidaturaHistorico, Curriculo, Vaga, VagaAuditoria


class VagasAdministrativasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.dono = User.objects.create_user('dono-vaga', password='senha')
        cls.pessoa = User.objects.create_user('pessoa-vaga', password='senha')
        cls.terceiro = User.objects.create_user('terceiro-vaga', password='senha')
        pais = Pais.objects.create(nome='Brasil Vagas', codigo_iso_2='BV', codigo_iso_3='BVG')
        cls.estado = Estado.objects.create(pais=pais, nome='São Paulo Vagas', sigla='SV')
        cls.cidade = Cidade.objects.create(estado=cls.estado, nome='Botucatu Vagas')
        cls.empresa = Empresa.objects.create(
            usuario_proprietario=cls.dono, razao_social='Empresa Vagas Ltda',
            nome_fantasia='Empresa Vagas', cpf_cnpj='11222333000181',
            cidade=cls.cidade, estado=cls.estado, status=Empresa.Status.ATIVA,
            perfil_publico=True,
        )

    def dados(self, **extra):
        dados = {
            'tipo_responsavel': 'EMPRESA', 'empresa': self.empresa.pk,
            'titulo': 'Analista de sistemas', 'descricao': 'Descrição pública',
            'tipo_contrato': 'CLT', 'modalidade': 'PRESENCIAL',
            'quantidade': 1, 'cidade': 'Botucatu', 'estado': 'SP',
            'bairro': 'Centro', 'endereco_privado': 'Rua Privada, 999',
            'visibilidade_localizacao': Vaga.VisibilidadeLocalizacao.PUBLICA,
        }
        dados.update(extra)
        return dados

    def completar_pessoa(self):
        self.pessoa.first_name = 'Pessoa'
        self.pessoa.last_name = 'Contratante'
        self.pessoa.cpf = '52998224725'
        self.pessoa.cpf_validado_em = timezone.now()
        self.pessoa.telefone = '14999999999'
        self.pessoa.cidade = self.cidade
        self.pessoa.estado = self.estado
        self.pessoa.bairro = 'Região central'
        self.pessoa.endereco = 'Rua Residencial'
        self.pessoa.termos_contratante_aceitos_em = timezone.now()
        self.pessoa.save()

    def test_pessoa_sem_cpf_nao_publica(self):
        self.client.force_login(self.pessoa)
        response = self.client.post(reverse('painel:vaga_criar'), self.dados(
            tipo_responsavel='PESSOA_FISICA', empresa='',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Vaga.objects.filter(perfil_pessoa_fisica=self.pessoa).exists())

    def test_pessoa_com_perfil_valido_cria_rascunho_e_publica(self):
        self.completar_pessoa()
        self.client.force_login(self.pessoa)
        response = self.client.post(reverse('painel:vaga_criar'), self.dados(
            tipo_responsavel='PESSOA_FISICA', empresa='',
        ))
        self.assertEqual(response.status_code, 302)
        vaga = Vaga.objects.get(perfil_pessoa_fisica=self.pessoa)
        self.assertEqual(vaga.status, Vaga.Status.RASCUNHO)
        self.assertEqual(vaga.usuario_criador, self.pessoa)
        self.client.post(reverse('painel:vaga_status', args=[vaga.uuid]), {'status': Vaga.Status.PUBLICADA})
        vaga.refresh_from_db()
        self.assertEqual(vaga.status, Vaga.Status.PUBLICADA)

    def test_dados_privados_nunca_aparecem_na_pagina_publica(self):
        self.completar_pessoa()
        vaga = Vaga.objects.create(
            perfil_pessoa_fisica=self.pessoa, usuario_criador=self.pessoa,
            usuario_responsavel=self.pessoa, titulo='Oportunidade privada',
            descricao='Descrição', tipo_contrato='AUTONOMO', modalidade='PRESENCIAL',
            cidade='Botucatu', estado='SP', bairro='Bairro secreto',
            endereco_privado='Rua Super Secreta, 123', status=Vaga.Status.PUBLICADA,
        )
        html = self.client.get(reverse('recruitment_public:vaga', args=[vaga.slug])).content.decode()
        self.assertNotIn(self.pessoa.cpf, html)
        self.assertNotIn('Rua Super Secreta', html)
        self.assertNotIn('Bairro secreto', html)

    def test_empresa_sem_autorizacao_nao_pode_ser_selecionada(self):
        self.client.force_login(self.terceiro)
        response = self.client.post(reverse('painel:vaga_criar'), self.dados())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Vaga.objects.filter(usuario_criador=self.terceiro).exists())

    def test_isolamento_de_vaga_e_candidaturas(self):
        vaga = Vaga.objects.create(
            empresa=self.empresa, usuario_criador=self.dono,
            usuario_responsavel=self.dono, titulo='Isolada', descricao='Descrição',
            tipo_contrato='CLT', modalidade='REMOTO', cidade='Botucatu', estado='SP',
        )
        self.client.force_login(self.terceiro)
        self.assertEqual(self.client.get(reverse('painel:vaga_detalhe', args=[vaga.uuid])).status_code, 404)
        self.assertEqual(self.client.get(reverse('painel:candidaturas_empresa', args=[vaga.uuid])).status_code, 404)

    def test_administrador_autorizado_administra_empresa(self):
        EmpresaUsuario.objects.create(
            empresa=self.empresa, usuario=self.terceiro, administrador=True, ativo=True,
        )
        vaga = Vaga.objects.create(
            empresa=self.empresa, usuario_criador=self.dono,
            usuario_responsavel=self.dono, titulo='Administrável', descricao='Descrição',
            tipo_contrato='CLT', modalidade='REMOTO', cidade='Botucatu', estado='SP',
        )
        self.client.force_login(self.terceiro)
        self.assertEqual(self.client.get(reverse('painel:vaga_detalhe', args=[vaga.uuid])).status_code, 200)

    def test_transicoes_auditoria_filtros_e_responsividade(self):
        vaga = Vaga.objects.create(
            empresa=self.empresa, usuario_criador=self.dono,
            usuario_responsavel=self.dono, titulo='Filtrável', descricao='Descrição',
            tipo_contrato='CLT', modalidade='REMOTO', cidade='Botucatu', estado='SP',
        )
        self.client.force_login(self.dono)
        self.client.post(reverse('painel:vaga_status', args=[vaga.uuid]), {'status': Vaga.Status.PUBLICADA})
        self.assertTrue(VagaAuditoria.objects.filter(vaga=vaga, acao='publicada').exists())
        response = self.client.get(reverse('painel:vagas_lista'), {'status': Vaga.Status.PUBLICADA, 'q': 'Filtrável'})
        self.assertContains(response, 'Filtrável')
        self.assertContains(response, 'jobs-stats')
        self.assertContains(response, 'data-jobs-filter-toggle')
        exportacao = self.client.get(reverse('painel:candidaturas_exportar', args=[vaga.uuid]))
        self.assertEqual(exportacao.status_code, 200)
        self.assertEqual(exportacao['Content-Type'], 'text/csv; charset=utf-8')
        self.assertTrue(VagaAuditoria.objects.filter(vaga=vaga, acao='exportacao_candidatos').exists())

    def test_layout_administrativo_rotas_botoes_e_breadcrumbs(self):
        vaga = Vaga.objects.create(
            empresa=self.empresa, usuario_criador=self.dono,
            usuario_responsavel=self.dono, titulo='Layout administrativo',
            descricao='Descrição', tipo_contrato='CLT', modalidade='REMOTO',
            cidade='Botucatu', estado='SP',
        )
        self.client.force_login(self.dono)
        lista = self.client.get(reverse('painel:vagas_lista'))
        self.assertContains(lista, 'jobs-hero')
        self.assertContains(lista, 'Painel')
        self.assertContains(lista, 'Nova vaga')
        self.assertContains(lista, 'Exportar')
        self.assertContains(lista, '/static/painel/css/vagas.css')
        detalhe = self.client.get(reverse('painel:vaga_detalhe', args=[vaga.uuid]))
        for texto in ('Informações gerais', 'Candidaturas', 'Auditoria', 'Configurações'):
            self.assertContains(detalhe, texto)
        self.assertNotContains(detalhe, '11.222.333/0001-81')
        formulario = self.client.get(reverse('painel:vaga_editar', args=[vaga.uuid]))
        for texto in ('Identificação', 'Responsável', 'Contratação', 'Localização', 'Conteúdo', 'Publicação'):
            self.assertContains(formulario, texto)
        self.assertContains(formulario, 'Salvar e publicar')
        self.assertEqual(self.client.get(reverse('painel:vaga_auditoria', args=[vaga.uuid])).status_code, 200)
        self.assertEqual(self.client.get(reverse('painel:vaga_remover', args=[vaga.uuid])).status_code, 200)

    def test_rotas_publicar_pausar_encerrar_duplicar_e_remover(self):
        vaga = Vaga.objects.create(
            empresa=self.empresa, usuario_criador=self.dono,
            usuario_responsavel=self.dono, titulo='Fluxo de ações',
            descricao='Descrição', tipo_contrato='CLT', modalidade='REMOTO',
            cidade='Botucatu', estado='SP',
        )
        self.client.force_login(self.dono)
        self.client.post(reverse('painel:vaga_publicar', args=[vaga.uuid]))
        vaga.refresh_from_db(); self.assertEqual(vaga.status, Vaga.Status.PUBLICADA)
        self.client.post(reverse('painel:vaga_pausar', args=[vaga.uuid]))
        vaga.refresh_from_db(); self.assertEqual(vaga.status, Vaga.Status.PAUSADA)
        self.client.post(reverse('painel:vaga_publicar', args=[vaga.uuid]))
        self.client.post(reverse('painel:vaga_encerrar', args=[vaga.uuid]))
        vaga.refresh_from_db(); self.assertEqual(vaga.status, Vaga.Status.ENCERRADA)
        self.client.post(reverse('painel:vaga_duplicar', args=[vaga.uuid]))
        self.assertTrue(Vaga.objects.filter(titulo__startswith='Cópia de').exists())
        self.client.post(reverse('painel:vaga_remover', args=[vaga.uuid]))
        self.assertFalse(Vaga.objects.filter(pk=vaga.pk).exists())
        self.assertTrue(Vaga.all_objects.filter(pk=vaga.pk, excluido_em__isnull=False).exists())

    def test_candidatura_tem_pagina_e_historico_de_etapa(self):
        vaga = Vaga.objects.create(
            empresa=self.empresa, usuario_criador=self.dono,
            usuario_responsavel=self.dono, titulo='Seleção',
            descricao='Descrição', tipo_contrato='CLT', modalidade='REMOTO',
            cidade='Botucatu', estado='SP', status=Vaga.Status.PUBLICADA,
        )
        curriculo = Curriculo.objects.create(usuario=self.terceiro, titulo_profissional='Pessoa candidata')
        candidatura = Candidatura.objects.create(vaga=vaga, usuario=self.terceiro, curriculo=curriculo)
        vaga.status = Vaga.Status.PAUSADA
        vaga.save()
        self.client.force_login(self.dono)
        pagina = self.client.get(reverse('painel:candidaturas_empresa', args=[vaga.uuid]))
        self.assertContains(pagina, 'Pessoa candidata')
        response = self.client.post(
            reverse('painel:candidatura_status', args=[vaga.uuid, candidatura.uuid]),
            {'status': Candidatura.Status.EM_ANALISE, 'observacao': 'Triagem concluída'},
        )
        self.assertEqual(response.status_code, 302)
        candidatura.refresh_from_db()
        self.assertEqual(candidatura.status, Candidatura.Status.EM_ANALISE)
        self.assertTrue(CandidaturaHistorico.objects.filter(
            candidatura=candidatura, observacao='Triagem concluída',
        ).exists())
