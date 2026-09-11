from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase
from django.urls import reverse

from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import CNAE, Empresa, EmpresaCNAE, EmpresaPropriedade, EmpresaUsuario
from apps.painel.views import DESCOBERTA_SALT
from apps.taxonomy.models import Categoria, Subcategoria


def registro_valido(**alteracoes):
    registro = {
        'cnpj': '11222333000181', 'razao_social': 'Empresa Botucatu Ltda',
        'nome_fantasia': 'Empresa Botucatu', 'natureza_juridica': 'Sociedade limitada',
        'porte': 'ME', 'data_inicio_atividade': '2020-01-02',
        'descricao_situacao_cadastral': 'ATIVA', 'cep': '18600000',
        'uf': 'SP', 'municipio': 'BOTUCATU', 'codigo_municipio_ibge': '3507506',
        'logradouro': 'Amando de Barros', 'descricao_tipo_de_logradouro': 'Rua',
        'numero': '10', 'complemento': '', 'bairro': 'Centro',
        'ddd_telefone_1': '1438111111', 'email': 'contato@example.com',
        'cnae_fiscal': '4711302', 'cnae_fiscal_descricao': 'Comércio varejista',
        'cnaes_secundarios': [{'codigo': '6201501', 'descricao': 'Software'}],
    }
    registro.update(alteracoes)
    return registro


def item_descoberta(resultado='CANDIDATA', **alteracoes):
    dados = {
        'resultado': resultado, 'registro_final': registro_valido(),
        'nome': 'Empresa Botucatu', 'nome_fantasia': 'Empresa Botucatu',
        'razao_social': 'Empresa Botucatu Ltda', 'cnpj': '11222333000181',
        'situacao': 'ATIVA', 'detalhe': '', 'endereco': 'Rua Amando',
        'numero': '10', 'bairro': 'Centro', 'cidade': 'Botucatu', 'uf': 'SP',
        'telefone': '', 'email': '', 'cnae_principal': '4711302',
        'cnae_principal_descricao': 'Comércio', 'cnaes_secundarios': [],
        'natureza_juridica': '', 'porte': '', 'data_abertura': '', 'complemento': '',
        'fonte_enriquecimento': 'OpenCNPJ', 'completude': 'COMPLETO',
        'campos_ausentes_revisao': [],
    }
    dados.update(alteracoes)
    return SimpleNamespace(**dados)


def resultado_descoberta(itens, cursor='pagina-2', **alteracoes):
    dados = {
        'itens': itens, 'proximo_cursor': cursor, 'recebidas': len(itens),
        'rejeitadas': 0, 'ja_existentes': 0,
        'candidatas': sum(item.resultado == 'CANDIDATA' for item in itens),
    }
    dados.update(alteracoes)
    return SimpleNamespace(**dados)


class EmpresaDescobertaPainelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('admin-descoberta', password='x')
        cls.comum = get_user_model().objects.create_user('comum-descoberta', password='x')
        pais = Pais.objects.create(nome='Brasil', codigo_iso_2='BR', codigo_iso_3='BRA')
        cls.estado = Estado.objects.create(pais=pais, nome='São Paulo', sigla='SP', codigo_ibge='35')
        cls.cidade = Cidade.objects.create(estado=cls.estado, nome='Botucatu', codigo_ibge='3507506')
        cls.categoria = Categoria.objects.create(nome='Comércio descoberta')
        cls.subcategoria = Subcategoria.objects.create(categoria=cls.categoria, nome='Loja descoberta')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_usuario_sem_permissao_nao_acessa_descoberta(self):
        self.client.force_login(self.comum)
        self.assertEqual(self.client.get(reverse('painel:empresas_descoberta')).status_code, 403)

    @patch('apps.painel.views.discover_batch')
    def test_get_nao_consulta_api_nem_grava(self, descobrir):
        response = self.client.get(reverse('painel:empresas_descoberta'))
        self.assertEqual(response.status_code, 200)
        descobrir.assert_not_called()
        self.assertFalse(Empresa.objects.exists())

    @patch('apps.painel.views.discover_batch')
    def test_consulta_exibe_registro_final_e_preserva_cursor(self, descobrir):
        item = item_descoberta()
        descobrir.return_value = resultado_descoberta([item])
        response = self.client.post(reverse('painel:empresas_descoberta'), {'acao': 'consultar', 'quantidade': '10'})
        self.assertContains(response, '11222333000181')
        self.assertContains(response, 'OpenCNPJ')
        self.assertTrue(response.context['cursor'])
        self.assertEqual(signing.loads(response.context['cursor'], salt='painel.empresas.descoberta.cursor.v1'), 'pagina-2')
        descobrir.assert_called_once_with(limit=10, cursor=None, dry_run=True, enriquecer=True)
        self.assertFalse(Empresa.objects.exists())

    def test_payload_adulterado_e_rejeitado(self):
        response = self.client.post(reverse('painel:empresas_descoberta'), {'acao': 'importar', 'registro': ['alterado']}, follow=True)
        self.assertContains(response, 'alterada ou expirou')
        self.assertFalse(Empresa.objects.exists())

    def test_importacao_preserva_invariantes_e_cnaes(self):
        token = signing.dumps(registro_valido(), salt=DESCOBERTA_SALT)
        response = self.client.post(reverse('painel:empresas_descoberta'), {'acao': 'importar', 'registro': [token]})
        self.assertRedirects(response, reverse('painel:empresas_lista') + '?status=ATIVA', fetch_redirect_response=False)
        empresa = Empresa.objects.get(cpf_cnpj='11222333000181')
        self.assertEqual(empresa.status, Empresa.Status.ATIVA)
        self.assertTrue(empresa.perfil_publico)
        self.assertTrue(empresa.ativo)
        self.assertIsNone(empresa.usuario_proprietario)
        self.assertIsNone(empresa.criado_por)
        self.assertIsNone(empresa.categoria_empresa)
        self.assertIsNone(empresa.subcategoria_empresa)
        self.assertEqual(empresa.whatsapp, '')
        self.assertEqual(EmpresaUsuario.objects.filter(empresa=empresa).count(), 0)
        self.assertEqual(EmpresaPropriedade.objects.filter(empresa=empresa).count(), 0)
        self.assertEqual(EmpresaCNAE.objects.filter(empresa=empresa, ativo=True).count(), 2)

    def test_existente_nao_e_sobrescrita(self):
        empresa = Empresa.objects.create(nome_fantasia='Original', cpf_cnpj='11222333000181')
        token = signing.dumps(registro_valido(nome_fantasia='Sobrescrita'), salt=DESCOBERTA_SALT)
        self.client.post(reverse('painel:empresas_descoberta'), {'acao': 'importar', 'registro': [token]})
        empresa.refresh_from_db()
        self.assertEqual(empresa.nome_fantasia, 'Original')
        self.assertEqual(Empresa.objects.count(), 1)

    def test_filtro_pendentes_inclui_pendente_e_exclui_ativa(self):
        pendente = Empresa.objects.create(nome_fantasia='Pendente fila', status=Empresa.Status.PENDENTE)
        ativa = Empresa.objects.create(nome_fantasia='Ativa fora', status=Empresa.Status.ATIVA)
        response = self.client.get(reverse('painel:empresas_lista'), {'status': 'PENDENTE'})
        self.assertIn(pendente, response.context['empresas'])
        self.assertNotIn(ativa, response.context['empresas'])
        self.assertContains(response, 'Revisar')

    def test_aprovacao_exige_permissao_e_post(self):
        empresa = Empresa.objects.create(nome_fantasia='Revisão', status=Empresa.Status.PENDENTE)
        self.assertEqual(self.client.get(reverse('painel:empresa_aprovar', args=[empresa.uuid])).status_code, 405)
        self.client.force_login(self.comum)
        self.assertEqual(self.client.post(reverse('painel:empresa_aprovar', args=[empresa.uuid])).status_code, 403)

    def test_aprovacao_exige_categoria_e_subcategoria(self):
        empresa = Empresa.objects.create(nome_fantasia='Sem classificação', estado=self.estado, cidade=self.cidade, status=Empresa.Status.PENDENTE)
        self.client.post(reverse('painel:empresa_aprovar', args=[empresa.uuid]))
        empresa.refresh_from_db()
        self.assertEqual(empresa.status, Empresa.Status.PENDENTE)
        self.assertFalse(empresa.perfil_publico)

    def test_aprovacao_publica_sem_criar_propriedade(self):
        empresa = Empresa.objects.create(
            nome_fantasia='Pronta', estado=self.estado, cidade=self.cidade,
            categoria_empresa=self.categoria, subcategoria_empresa=self.subcategoria,
            status=Empresa.Status.PENDENTE, perfil_publico=False,
        )
        self.client.post(reverse('painel:empresa_aprovar', args=[empresa.uuid]))
        empresa.refresh_from_db()
        self.assertEqual(empresa.status, Empresa.Status.ATIVA)
        self.assertTrue(empresa.perfil_publico)
        self.assertIsNone(empresa.usuario_proprietario)
        self.assertFalse(EmpresaUsuario.objects.filter(empresa=empresa).exists())
        self.assertFalse(EmpresaPropriedade.objects.filter(empresa=empresa).exists())

    def test_publico_exibe_somente_ativa_com_perfil_publico(self):
        publicada = Empresa.objects.create(
            nome_fantasia='Publicada correta', status=Empresa.Status.ATIVA,
            perfil_publico=True,
        )
        Empresa.objects.create(
            nome_fantasia='Pendente oculta', status=Empresa.Status.PENDENTE,
            perfil_publico=True,
        )
        Empresa.objects.create(
            nome_fantasia='Rejeitada oculta', status=Empresa.Status.REJEITADA,
            perfil_publico=True,
        )
        Empresa.objects.create(
            nome_fantasia='Ativa privada', status=Empresa.Status.ATIVA,
            perfil_publico=False,
        )

        response = self.client.get(reverse('publico:empresas'))

        self.assertContains(response, publicada.nome_fantasia)
        self.assertNotContains(response, 'Pendente oculta')
        self.assertNotContains(response, 'Rejeitada oculta')
        self.assertNotContains(response, 'Ativa privada')

    def test_botao_gerenciar_empresas_respeita_permissao(self):
        response = self.client.get(reverse('publico:empresas'))
        self.assertContains(response, 'Gerenciar empresas')

        self.client.force_login(self.comum)
        response = self.client.get(reverse('publico:empresas'))
        self.assertNotContains(response, 'Gerenciar empresas')

    def test_seletor_global_publico_nao_exibe_empresa_pendente(self):
        pendente = Empresa.objects.create(
            usuario_proprietario=self.comum, nome_fantasia='Pendente do seletor',
            status=Empresa.Status.PENDENTE, perfil_publico=False,
        )
        publicada = Empresa.objects.create(
            usuario_proprietario=self.comum, nome_fantasia='Publicada do seletor',
            status=Empresa.Status.ATIVA, perfil_publico=True,
        )
        self.client.force_login(self.comum)

        response = self.client.get(reverse('publico:empresas'))

        self.assertNotIn(pendente, response.context['empresas_nav'])
        self.assertIn(publicada, response.context['empresas_nav'])
        self.assertNotContains(response, pendente.nome_fantasia)
        self.assertContains(response, publicada.nome_fantasia)

        self.client.logout()
        response = self.client.get(reverse('publico:empresas'))
        self.assertNotContains(response, 'Gerenciar empresas')

    def test_fila_padrao_contem_pendente_e_nao_contem_ativa(self):
        pendente = Empresa.objects.create(
            nome_fantasia='Na fila', status=Empresa.Status.PENDENTE,
        )
        ativa = Empresa.objects.create(
            nome_fantasia='Fora da fila', status=Empresa.Status.ATIVA,
        )

        response = self.client.get(reverse('painel:empresas_pendentes'))

        empresas_na_fila = response.context['empresas']
        self.assertIn(pendente, empresas_na_fila)
        self.assertNotIn(ativa, empresas_na_fila)

    def test_fila_filtra_cnae_principal_por_codigo_e_descricao(self):
        empresa = Empresa.objects.create(nome_fantasia='Fretamento principal', status=Empresa.Status.PENDENTE)
        cnae = CNAE.objects.create(
            codigo='4929902',
            descricao='Transporte rodoviário coletivo de passageiros sob regime de fretamento',
        )
        EmpresaCNAE.objects.create(empresa=empresa, cnae=cnae, principal=True, ativo=True)

        por_codigo = self.client.get(reverse('painel:empresas_pendentes'), {'cnae_principal': '4929902'})
        por_descricao = self.client.get(reverse('painel:empresas_pendentes'), {'cnae_principal': 'fretamento'})

        self.assertContains(por_codigo, empresa.nome_fantasia)
        self.assertContains(por_descricao, empresa.nome_fantasia)

    def test_fila_filtra_cnae_secundario(self):
        empresa = Empresa.objects.create(nome_fantasia='Fretamento secundário', status=Empresa.Status.PENDENTE)
        cnae = CNAE.objects.create(codigo='4929901', descricao='Fretamento municipal')
        EmpresaCNAE.objects.create(empresa=empresa, cnae=cnae, principal=False, ativo=True)

        response = self.client.get(
            reverse('painel:empresas_pendentes'), {'cnae_secundario': '4929901'},
        )

        self.assertContains(response, empresa.nome_fantasia)

    def test_consulta_da_fila_nao_persiste_sugestao_taxonomica(self):
        empresa = Empresa.objects.create(nome_fantasia='Sem classificação automática', status=Empresa.Status.PENDENTE)
        cnae = CNAE.objects.create(codigo='4929902', descricao='Fretamento intermunicipal')
        EmpresaCNAE.objects.create(empresa=empresa, cnae=cnae, principal=True, ativo=True)

        self.client.get(reverse('painel:empresas_pendentes'))

        empresa.refresh_from_db()
        self.assertIsNone(empresa.categoria_empresa_id)
        self.assertIsNone(empresa.subcategoria_empresa_id)

    def test_aprovacao_torna_empresa_elegivel_ao_diretorio_publico(self):
        empresa = Empresa.objects.create(
            nome_fantasia='Aprovar para publicar', status=Empresa.Status.PENDENTE,
            perfil_publico=False, categoria_empresa=self.categoria,
            subcategoria_empresa=self.subcategoria, estado=self.estado, cidade=self.cidade,
        )
        self.assertNotContains(self.client.get(reverse('publico:empresas')), empresa.nome_fantasia)

        self.client.post(reverse('painel:empresa_aprovar', args=[empresa.uuid]))

        empresa.refresh_from_db()
        self.assertEqual(empresa.status, Empresa.Status.ATIVA)
        self.assertTrue(empresa.perfil_publico)
        self.assertIsNone(empresa.usuario_proprietario)
        self.assertContains(self.client.get(reverse('publico:empresas')), empresa.nome_fantasia)

    @patch('apps.painel.views.discover_batch')
    def test_baixada_e_contabilizada_mas_nao_aparece_na_previa(self, descobrir):
        item = item_descoberta(
            'INATIVA', nome='Rejeitada', cnpj='99888777000166', situacao='BAIXADA',
            detalhe='Situação cadastral não ativa', registro_final={},
        )
        descobrir.return_value = resultado_descoberta(
            [item], cursor='pagina-2', rejeitadas=1, candidatas=0,
        )
        response = self.client.post(reverse('painel:empresas_descoberta'), {'acao': 'consultar'})
        self.assertContains(response, 'Inativas/fora dos critérios ignoradas: 1')
        self.assertNotContains(response, '99888777000166')
        self.assertNotContains(response, 'name="registro"')
        self.assertContains(response, 'Nenhuma nova empresa elegível foi encontrada neste lote')
        self.assertTrue(response.context['cursor'])

    @patch('apps.painel.views.discover_batch')
    def test_outra_cidade_e_existente_nao_aparecem_e_so_candidata_recebe_payload(self, descobrir):
        bauru = item_descoberta(
            'FORA_MUNICIPIO', nome='Empresa Bauru', cnpj='45723174000110',
            cidade='Bauru', detalhe='Município diferente de Botucatu', registro_final={},
        )
        existente = item_descoberta(
            'JA_EXISTE', nome='Empresa Existente', cnpj='19131243000197',
            detalhe='CNPJ já cadastrado', registro_final=registro_valido(cnpj='19131243000197'),
        )
        candidata = item_descoberta()
        descobrir.return_value = resultado_descoberta(
            [bauru, existente, candidata], recebidas=3, rejeitadas=1,
            ja_existentes=1, candidatas=1,
        )

        response = self.client.post(reverse('painel:empresas_descoberta'), {'acao': 'consultar'})

        self.assertNotContains(response, '45723174000110')
        self.assertNotContains(response, '19131243000197')
        self.assertContains(response, '11222333000181')
        self.assertContains(response, 'name="registro"', count=1)
        self.assertFalse(hasattr(bauru, 'payload_assinado'))
        self.assertFalse(hasattr(existente, 'payload_assinado'))
        self.assertTrue(candidata.payload_assinado)
        self.assertContains(response, 'Já cadastradas: 1')

    @patch('apps.painel.views.discover_batch')
    def test_proxima_consulta_usa_cursor_recebido(self, descobrir):
        descobrir.return_value = resultado_descoberta([], cursor='pagina-3')
        cursor = signing.dumps('pagina-2', salt='painel.empresas.descoberta.cursor.v1')

        response = self.client.post(reverse('painel:empresas_descoberta'), {
            'acao': 'consultar', 'quantidade': '20', 'cursor': cursor,
        })

        self.assertEqual(response.status_code, 200)
        descobrir.assert_called_once_with(
            limit=20, cursor='pagina-2', dry_run=True, enriquecer=True,
        )
        self.assertEqual(
            signing.loads(response.context['cursor'], salt='painel.empresas.descoberta.cursor.v1'),
            'pagina-3',
        )
