from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Empresa, EmpresaImportacaoExecucao, EmpresaPropriedade, EmpresaUsuario
from apps.organizations.services.empresa_importacao import SincronizacaoEmAndamento, sincronizar_empresas


def registro(cnpj='11222333000181', **extra):
    data = {
        'cnpj': cnpj, 'razao_social': 'Empresa Teste', 'nome_fantasia': 'Empresa Teste',
        'uf': 'SP', 'municipio': 'BOTUCATU', 'codigo_municipio_ibge': '3507506',
        'descricao_situacao_cadastral': 'ATIVA', 'cep': '18600000',
        'logradouro': 'Rua Teste', 'bairro': 'Centro', 'cnae_fiscal': '4711302',
        'cnae_fiscal_descricao': 'Comércio',
    }
    data.update(extra)
    return data


class ClientePaginas:
    def __init__(self, paginas):
        self.paginas = paginas
        self.calls = []

    def discover_batch(self, *, limit, cursor):
        self.calls.append((limit, cursor))
        valor = self.paginas[cursor]
        if isinstance(valor, Exception):
            raise valor
        return valor


class EmpresaImportacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        pais = Pais.objects.create(nome='Brasil sync', codigo_iso_2='BS', codigo_iso_3='BSY')
        estado = Estado.objects.create(pais=pais, nome='São Paulo sync', sigla='SP', codigo_ibge='35')
        Cidade.objects.create(estado=estado, nome='Botucatu', codigo_ibge='3507506')

    def test_varredura_multiplas_paginas_usa_1024_ate_cursor_final(self):
        cliente = ClientePaginas({
            None: {'data': [registro()], 'cursor': 'p2'},
            'p2': {'data': [registro()], 'cursor': None},
        })
        execucao = sincronizar_empresas(tipo_execucao='INICIAL', client=cliente)
        self.assertEqual(cliente.calls, [(1024, None), (1024, 'p2')])
        self.assertEqual(execucao.paginas_processadas, 2)
        self.assertEqual(execucao.registros_recebidos, 2)
        self.assertEqual(execucao.importados, 1)
        self.assertEqual(execucao.ja_existentes, 1)
        self.assertEqual(execucao.cursor_atual, '')
        empresa = Empresa.objects.get()
        self.assertEqual(empresa.origem_cadastro, Empresa.OrigemCadastro.API)
        self.assertTrue(empresa.perfil_publico and empresa.ativo)
        self.assertEqual(empresa.status, Empresa.Status.ATIVA)
        self.assertIsNone(empresa.usuario_proprietario)
        self.assertIsNone(empresa.criado_por)
        self.assertFalse(EmpresaUsuario.objects.exists())
        self.assertFalse(EmpresaPropriedade.objects.exists())

    def test_interrompe_quando_fonte_repete_o_mesmo_cursor(self):
        cliente = ClientePaginas({
            None: {'data': [registro()], 'cursor': 'p2'},
            'p2': {'data': [registro()], 'cursor': 'p2'},
        })

        with self.assertRaisesRegex(RuntimeError, 'Cursor repetido retornado pela fonte'):
            sincronizar_empresas(tipo_execucao='INICIAL', client=cliente)

        execucao = EmpresaImportacaoExecucao.objects.get()

        self.assertEqual(
            cliente.calls,
            [(1024, None), (1024, 'p2')],
        )
        self.assertEqual(execucao.status, EmpresaImportacaoExecucao.Status.ERRO)
        self.assertEqual(execucao.paginas_processadas, 2)
        self.assertEqual(execucao.cursor_atual, 'p2')
        self.assertIn('Cursor repetido', execucao.ultima_mensagem)

    def test_invalida_e_erro_individual_nao_interrompem_pagina(self):
        cliente = ClientePaginas({None: {'data': [registro(uf='PR'), registro()], 'cursor': None}})
        with patch('apps.organizations.services.botucatu_discovery.importar_registro', side_effect=RuntimeError('isolado')):
            execucao = sincronizar_empresas(tipo_execucao='INICIAL', client=cliente)
        self.assertEqual(execucao.status, 'CONCLUIDA')
        self.assertEqual(execucao.rejeitados, 2)
        self.assertEqual(execucao.erros, 1)

    def test_checkpoint_e_retomada_da_mesma_execucao(self):
        cliente = ClientePaginas({
            None: {'data': [registro()], 'cursor': 'p2'},
            'p2': RuntimeError('fonte caiu'),
        })
        with self.assertRaises(RuntimeError):
            sincronizar_empresas(tipo_execucao='INICIAL', client=cliente)
        execucao = EmpresaImportacaoExecucao.objects.get()
        self.assertEqual((execucao.paginas_processadas, execucao.cursor_atual), (1, 'p2'))
        retomada = ClientePaginas({'p2': {'data': [registro()], 'cursor': None}})
        final = sincronizar_empresas(tipo_execucao='INICIAL', retomar_id=execucao.pk, client=retomada)
        self.assertEqual(retomada.calls, [(1024, 'p2')])
        self.assertEqual(final.paginas_processadas, 2)

    def test_recusa_execucao_simultanea(self):
        EmpresaImportacaoExecucao.objects.create(
            tipo_execucao='SEMANAL', status='EXECUTANDO', iniciada_em=timezone.now(),
        )
        with self.assertRaises(SincronizacaoEmAndamento):
            sincronizar_empresas(tipo_execucao='MANUAL', client=ClientePaginas({}))

    def test_execucoes_semanais_novas_comecam_sem_cursor_anterior(self):
        primeiro = ClientePaginas({None: {'data': [], 'cursor': None}})
        segundo = ClientePaginas({None: {'data': [], 'cursor': None}})
        sincronizar_empresas(tipo_execucao='SEMANAL', client=primeiro)
        sincronizar_empresas(tipo_execucao='SEMANAL', client=segundo)
        self.assertEqual(primeiro.calls, [(1024, None)])
        self.assertEqual(segundo.calls, [(1024, None)])
        self.assertEqual(EmpresaImportacaoExecucao.objects.count(), 2)
