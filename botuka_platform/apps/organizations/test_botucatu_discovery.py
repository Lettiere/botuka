import urllib.error
import json
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.cache import cache
from django.test import TestCase, SimpleTestCase
from django.urls import reverse

from apps.integrations.minha_receita.client import MinhaReceitaClient
from apps.integrations.minha_receita.exceptions import MinhaReceitaProviderError
from apps.integrations.cnpj.enrichment import enriquecer_registro
from apps.integrations.cnpj.exceptions import CNPJProviderError
from apps.integrations.cnpj.providers.brasil_api import BrasilAPIProvider
from apps.integrations.cnpj.providers.open_cnpj import OpenCNPJProvider
from apps.integrations.cnpj.schemas import CNPJData
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import (
    CNPJConsulta, CNAE, Empresa, EmpresaCNAE, EmpresaPropriedade, EmpresaUsuario,
)
from apps.organizations.services.botucatu_discovery import (
    classificar_registro,
    discover_batch,
    importar_registro,
)
from apps.core.search import GlobalSearchService
from apps.core.services.home.adapters.organizations import obter_empresas_destaque
from apps.painel.forms import EmpresaCadastroSimplesForm


class FakeClient:
    def __init__(self, data, cursor='cursor-seguinte'):
        self.data = data
        self.cursor = cursor
        self.calls = []

    def discover_batch(self, *, limit, cursor):
        self.calls.append((limit, cursor))
        return {'data': self.data, 'cursor': self.cursor}


class FakeProvider:
    def __init__(self, name, data=None, error=None):
        self.name = name
        self.data = data or CNPJData(cnpj='11222333000181')
        self.error = error
        self.calls = []

    def consultar(self, cnpj):
        self.calls.append(cnpj)
        if self.error:
            raise self.error
        return self.data


class ProviderPorCNPJ:
    name = 'OpenCNPJ'

    def __init__(self):
        self.calls = []

    def consultar(self, cnpj):
        self.calls.append(cnpj)
        if cnpj == '11222333000181':
            raise CNPJProviderError('falha isolada')
        return CNPJData(cnpj=cnpj, email='segunda@example.com')


def registro_valido(**overrides):
    registro = {
        'cnpj': '11.222.333/0001-81',
        'razao_social': 'Empresa Botucatu Ltda',
        'nome_fantasia': 'Empresa Botucatu',
        'porte': 'ME',
        'natureza_juridica': 'Sociedade Empresária Limitada',
        'data_inicio_atividade': '2020-01-02',
        'situacao_cadastral': 2,
        'descricao_situacao_cadastral': 'ATIVA',
        'cep': '18600-000',
        'uf': 'SP',
        'municipio': 'BOTUCATU',
        'codigo_municipio': 6241,
        'codigo_municipio_ibge': 3507506,
        'bairro': 'Centro',
        'numero': '10',
        'logradouro': 'Amando de Barros',
        'descricao_tipo_de_logradouro': 'Rua',
        'complemento': 'Sala 1',
        'email': 'CONTATO@EXAMPLE.COM',
        'ddd_telefone_1': '(14) 3811-1111',
        'ddd_telefone_2': '(14) 99999-9999',
        'cnae_fiscal': 4711302,
        'cnae_fiscal_descricao': 'Comércio varejista',
        'cnaes_secundarios': [
            {'codigo': 6201501, 'descricao': 'Desenvolvimento de programas'},
            {'codigo': 8599604, 'descricao': 'Treinamento profissional'},
        ],
    }
    registro.update(overrides)
    return registro


class FiltroBotucatuTests(SimpleTestCase):
    def test_aceita_botucatu_sp_ativa(self):
        self.assertEqual(classificar_registro(registro_valido())[0], 'CANDIDATA')

    def test_rejeita_bauru_sp(self):
        self.assertEqual(classificar_registro(registro_valido(municipio='Bauru'))[0], 'FORA_MUNICIPIO')

    def test_rejeita_botucatu_em_outra_uf(self):
        self.assertEqual(classificar_registro(registro_valido(uf='PR'))[0], 'FORA_MUNICIPIO')

    def test_rejeita_empresa_baixada(self):
        self.assertEqual(
            classificar_registro(registro_valido(descricao_situacao_cadastral='BAIXADA'))[0],
            'INATIVA',
        )

    def test_aceita_municipio_com_normalizacao(self):
        self.assertEqual(classificar_registro(registro_valido(municipio='  Botucatú '))[0], 'CANDIDATA')

    def test_exige_codigo_ibge_correto(self):
        self.assertEqual(
            classificar_registro(registro_valido(codigo_municipio_ibge=3506003))[0],
            'FORA_MUNICIPIO',
        )

    @patch('apps.integrations.minha_receita.client.urllib.request.urlopen')
    def test_timeout_da_fonte_e_tratado(self, urlopen):
        urlopen.side_effect = TimeoutError
        with self.assertRaises(MinhaReceitaProviderError):
            MinhaReceitaClient().discover_batch(limit=10)


class EnriquecimentoUnitarioTests(SimpleTestCase):
    def test_registro_completo_nao_consulta_nem_sobrescreve(self):
        provider = FakeProvider('OpenCNPJ', CNPJData(
            cnpj='11222333000181', razao_social='Outra razão', telefone='14999999999',
        ))
        resultado = enriquecer_registro(registro_valido(), providers=(provider,))
        self.assertEqual(provider.calls, [])
        self.assertEqual(resultado.registro['razao_social'], 'Empresa Botucatu Ltda')
        self.assertEqual(resultado.registro['ddd_telefone_1'], '(14) 3811-1111')

    def test_primario_completa_campo_ausente(self):
        provider = FakeProvider('OpenCNPJ', CNPJData(
            cnpj='11222333000181', nome_fantasia='Nome enriquecido',
        ))
        resultado = enriquecer_registro(
            registro_valido(nome_fantasia=''), providers=(provider,),
        )
        self.assertEqual(resultado.registro['nome_fantasia'], 'Nome enriquecido')
        self.assertEqual(resultado.fontes_por_campo['nome_fantasia'], 'OpenCNPJ')

    def test_falha_do_primario_aciona_fallback(self):
        primario = FakeProvider('OpenCNPJ', error=CNPJProviderError('indisponível'))
        fallback = FakeProvider('BrasilAPI', CNPJData(
            cnpj='11222333000181', email='fallback@example.com',
        ))
        resultado = enriquecer_registro(
            registro_valido(email=''), providers=(primario, fallback),
        )
        self.assertEqual(resultado.registro['email'], 'fallback@example.com')
        self.assertEqual(resultado.fonte_resumo, 'BrasilAPI')
        self.assertEqual(len(resultado.erros), 1)

    def test_ambos_falham_e_original_e_preservado(self):
        providers = (
            FakeProvider('OpenCNPJ', error=CNPJProviderError('erro 1')),
            FakeProvider('BrasilAPI', error=CNPJProviderError('erro 2')),
        )
        original = registro_valido(email='')
        resultado = enriquecer_registro(original, providers=providers)
        self.assertEqual(resultado.registro, original)
        self.assertEqual(resultado.fonte_resumo, 'nenhuma')
        self.assertEqual(len(resultado.erros), 2)

    def test_telefone_existente_nao_e_substituido(self):
        provider = FakeProvider('OpenCNPJ', CNPJData(
            cnpj='11222333000181', telefone='14988887777', email='novo@example.com',
        ))
        resultado = enriquecer_registro(
            registro_valido(email=''), providers=(provider,),
        )
        self.assertEqual(resultado.registro['ddd_telefone_1'], '(14) 3811-1111')

    def test_endereco_ausente_pode_ser_complementado(self):
        provider = FakeProvider('OpenCNPJ', CNPJData(
            cnpj='11222333000181', logradouro='Rua Nova',
        ))
        resultado = enriquecer_registro(
            registro_valido(logradouro='', descricao_tipo_de_logradouro=''), providers=(provider,),
        )
        self.assertEqual(resultado.registro['logradouro'], 'Rua Nova')

    def test_cnae_enriquecido_e_deduplicado(self):
        provider = FakeProvider('OpenCNPJ', CNPJData(cnpj='11222333000181', cnaes=[
            {'codigo': '6201501', 'descricao': 'Duplicado', 'principal': False},
            {'codigo': '6201501', 'descricao': 'Duplicado novamente', 'principal': False},
            {'codigo': '5611201', 'descricao': 'Restaurante', 'principal': False},
        ]))
        resultado = enriquecer_registro(
            registro_valido(email=''), providers=(provider,),
        )
        codigos = [str(item['codigo']) for item in resultado.registro['cnaes_secundarios']]
        self.assertEqual(codigos.count('6201501'), 1)
        self.assertEqual(codigos.count('5611201'), 1)

    @patch('apps.integrations.cnpj.providers.http.urllib.request.urlopen')
    def test_providers_ignoram_qsa_e_segundo_telefone(self, urlopen):
        payload = registro_valido(qsa=[{'nome_socio': 'Dado pessoal'}])
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps(payload).encode()
        for provider in (OpenCNPJProvider(), BrasilAPIProvider()):
            dados = provider.consultar('11222333000181')
            self.assertEqual(dados.telefone, '(14) 3811-1111')
            self.assertEqual(dados.raw, {})
            self.assertNotIn('qsa', dados.as_dict())

    @patch('apps.integrations.minha_receita.client.urllib.request.urlopen')
    def test_erro_http_da_fonte_e_tratado(self, urlopen):
        urlopen.side_effect = urllib.error.URLError('offline')
        with self.assertRaises(MinhaReceitaProviderError):
            MinhaReceitaClient().discover_batch(limit=10)


class DescobertaPersistenciaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        pais = Pais.objects.create(nome='Brasil', codigo_iso_2='BR', codigo_iso_3='BRA')
        cls.estado = Estado.objects.create(pais=pais, nome='São Paulo', sigla='SP', codigo_ibge='35')
        cls.cidade = Cidade.objects.create(
            estado=cls.estado, nome='Botucatu', codigo_ibge='3507506'
        )

    def test_paginacao_repassa_e_retorna_cursor(self):
        client = FakeClient([registro_valido()], cursor='pagina-2')
        resultado = discover_batch(limit=10, cursor='pagina-1', client=client)
        self.assertEqual(client.calls, [(10, 'pagina-1')])
        self.assertEqual(resultado.proximo_cursor, 'pagina-2')
        self.assertEqual(resultado.recebidas, 1)
        self.assertEqual(resultado.ativas_validas, 1)

    def test_pagina_aceita_ate_1024_registros(self):
        registros = [registro_valido() for _ in range(1024)]
        client = FakeClient(registros, cursor='pagina-seguinte')
        resultado = discover_batch(limit=1024, dry_run=True, client=client)
        self.assertEqual(client.calls, [(1024, None)])
        self.assertEqual(resultado.recebidas, 1024)
        self.assertEqual(resultado.proximo_cursor, 'pagina-seguinte')

    def test_dry_run_nao_grava_empresa_cnae_nem_vinculo(self):
        resultado = discover_batch(limit=10, dry_run=True, client=FakeClient([registro_valido()]))
        self.assertEqual(resultado.candidatas, 1)
        self.assertEqual(resultado.importadas, 0)
        self.assertFalse(Empresa.objects.exists())
        self.assertFalse(CNAE.objects.exists())
        self.assertFalse(EmpresaCNAE.objects.exists())

    def test_dry_run_enriquecido_nao_grava_nenhuma_tabela(self):
        provider = FakeProvider('OpenCNPJ', CNPJData(
            cnpj='11222333000181', email='enriquecido@example.com',
        ))
        resultado = discover_batch(
            limit=10, dry_run=True, enriquecer=True,
            client=FakeClient([registro_valido(email='')]),
            enrichment_providers=(provider,),
        )
        self.assertEqual(resultado.itens[0].email, 'enriquecido@example.com')
        self.assertFalse(Empresa.objects.exists())
        self.assertFalse(CNAE.objects.exists())
        self.assertFalse(EmpresaCNAE.objects.exists())
        self.assertFalse(CNPJConsulta.objects.exists())

    def test_enriquecimento_nao_altera_filtro_geografico(self):
        provider = FakeProvider('OpenCNPJ', CNPJData(
            cnpj='11222333000181', municipio='BOTUCATU', uf='SP',
        ))
        resultado = discover_batch(
            limit=10, dry_run=True, enriquecer=True,
            client=FakeClient([registro_valido(municipio='Bauru')]),
            enrichment_providers=(provider,),
        )
        self.assertEqual(resultado.itens[0].resultado, 'FORA_MUNICIPIO')
        self.assertEqual(provider.calls, [])

    def test_erro_em_uma_candidata_nao_interrompe_as_demais(self):
        provider = ProviderPorCNPJ()
        primeira = registro_valido(email='')
        segunda = registro_valido(cnpj='19.131.243/0001-97', email='')
        resultado = discover_batch(
            limit=10, dry_run=True, enriquecer=True,
            client=FakeClient([primeira, segunda]), enrichment_providers=(provider,),
        )
        self.assertEqual(len(resultado.itens), 2)
        self.assertEqual(resultado.itens[0].fonte_enriquecimento, 'nenhuma')
        self.assertEqual(resultado.itens[1].email, 'segunda@example.com')

    @patch('apps.organizations.services.botucatu_discovery.MinhaReceitaClient')
    def test_enriquecer_sem_importar_continua_em_dry_run(self, client):
        client.return_value = FakeClient([registro_valido()])
        saida = StringIO()
        call_command('descobrir_empresas_botucatu', enriquecer=True, stdout=saida)
        self.assertIn('MODO: DRY-RUN', saida.getvalue())
        self.assertFalse(Empresa.objects.exists())

    @patch('apps.organizations.services.botucatu_discovery.MinhaReceitaClient')
    @patch('apps.organizations.services.botucatu_discovery.enriquecer_registro')
    def test_comando_permite_importacao_enriquecida(self, enriquecer, client):
        client.return_value = FakeClient([registro_valido()])
        enriquecido = registro_valido(email='enriquecido@example.com')
        enriquecer.return_value.registro = enriquecido
        enriquecer.return_value.fonte_resumo = 'OpenCNPJ'
        enriquecer.return_value.fontes_por_campo = {'email': 'OpenCNPJ'}
        enriquecer.return_value.erros = []

        call_command('descobrir_empresas_botucatu', importar=True, enriquecer=True)

        self.assertEqual(Empresa.objects.get().email, 'enriquecido@example.com')

    @patch('apps.organizations.services.botucatu_discovery.MinhaReceitaClient')
    def test_comando_detalhado_exibe_candidata_sem_dados_pessoais_ou_gravacao(self, client):
        registro = registro_valido(qsa=[{'nome_socio': 'Pessoa que não deve aparecer'}])
        client.return_value = FakeClient([registro])
        saida = StringIO()

        call_command(
            'descobrir_empresas_botucatu', limit=10, dry_run=True, detalhado=True,
            stdout=saida,
        )

        texto = saida.getvalue()
        self.assertIn('Razão social: Empresa Botucatu Ltda', texto)
        self.assertIn('Logradouro/endereço: Rua Amando de Barros', texto)
        self.assertIn('CNAE principal: 4711302 - Comércio varejista', texto)
        self.assertIn('6201501 - Desenvolvimento de programas', texto)
        self.assertIn('Resultado da classificação: CANDIDATA', texto)
        self.assertIn('WhatsApp: não informado', texto)
        self.assertNotIn('Pessoa que não deve aparecer', texto)
        self.assertNotIn('(14) 99999-9999', texto)
        self.assertFalse(Empresa.objects.exists())
        self.assertFalse(CNAE.objects.exists())
        self.assertFalse(EmpresaCNAE.objects.exists())

    def test_comando_detalhado_rejeita_importacao(self):
        with self.assertRaisesMessage(CommandError, '--detalhado só pode ser usado em dry-run'):
            call_command('descobrir_empresas_botucatu', importar=True, detalhado=True)

    def test_cnpj_existente_nao_duplica_nem_sobrescreve(self):
        original = Empresa.objects.create(nome_fantasia='Cadastro manual', cpf_cnpj='11222333000181')
        resultado = discover_batch(limit=10, dry_run=False, client=FakeClient([registro_valido()]))
        self.assertEqual(Empresa.objects.count(), 1)
        self.assertEqual(Empresa.objects.get(), original)
        self.assertEqual(original.nome_fantasia, 'Cadastro manual')
        self.assertEqual(resultado.ja_existentes, 1)
        self.assertEqual(resultado.itens[0].resultado, 'JA_EXISTE')

    def test_importacao_sem_proprietario_nasce_ativa_e_publica(self):
        empresa, criada = importar_registro(registro_valido())
        self.assertTrue(criada)
        self.assertIsNone(empresa.usuario_proprietario)
        self.assertIsNone(empresa.criado_por)
        self.assertEqual(empresa.status, Empresa.Status.ATIVA)
        self.assertTrue(empresa.perfil_publico)
        self.assertTrue(empresa.ativo)
        self.assertFalse(EmpresaUsuario.objects.filter(empresa=empresa).exists())
        self.assertFalse(EmpresaPropriedade.objects.filter(empresa=empresa).exists())

    def test_importacao_nao_presume_que_segundo_telefone_seja_whatsapp(self):
        empresa, _ = importar_registro(registro_valido())
        self.assertEqual(empresa.telefone, '1438111111')
        self.assertEqual(empresa.whatsapp, '')

    def test_importacao_armazena_dados_oficiais_com_destino(self):
        empresa, _ = importar_registro(registro_valido())
        self.assertEqual(empresa.razao_social, 'Empresa Botucatu Ltda')
        self.assertEqual(empresa.natureza_juridica, 'Sociedade Empresária Limitada')
        self.assertEqual(empresa.porte, 'ME')
        self.assertEqual(str(empresa.data_abertura), '2020-01-02')
        self.assertEqual(empresa.situacao_cadastral, 'ATIVA')
        self.assertEqual(empresa.endereco, 'Rua Amando de Barros')
        self.assertEqual(empresa.complemento, 'Sala 1')
        self.assertEqual(empresa.cidade, self.cidade)
        self.assertEqual(empresa.estado, self.estado)
        self.assertIsNone(empresa.categoria_empresa)
        self.assertIsNone(empresa.subcategoria_empresa)

    def test_importada_sem_categoria_aparece_no_diretorio_detalhe_busca_e_home(self):
        empresa, _ = importar_registro(registro_valido())

        diretorio = self.client.get(reverse('publico:empresas'))
        detalhe = self.client.get(reverse('publico:empresa', args=[empresa.slug]))
        resultados_nome = GlobalSearchService().search('Empresa Botucatu')[0]
        resultados_razao = GlobalSearchService().search('Botucatu Ltda')[0]
        cache.clear()

        self.assertContains(diretorio, empresa.nome_fantasia)
        self.assertEqual(detalhe.status_code, 200)
        self.assertContains(detalhe, empresa.nome_fantasia)
        self.assertIn(empresa.nome_fantasia, [item.title for item in resultados_nome])
        self.assertIn(empresa.nome_fantasia, [item.title for item in resultados_razao])
        self.assertIn(empresa, obter_empresas_destaque())

    def test_cadastro_manual_continua_exigindo_categoria_e_subcategoria(self):
        form = EmpresaCadastroSimplesForm()
        self.assertTrue(form.fields['categoria_empresa'].required)
        self.assertTrue(form.fields['subcategoria_empresa'].required)

    def test_cnae_principal_e_secundarios(self):
        empresa, _ = importar_registro(registro_valido())
        vinculos = EmpresaCNAE.objects.filter(empresa=empresa).select_related('cnae')
        self.assertEqual(vinculos.count(), 3)
        principal = vinculos.get(principal=True, ativo=True)
        self.assertEqual(principal.cnae.codigo, '4711302')
        self.assertEqual(principal.origem, EmpresaCNAE.Origem.RECEITA)
        self.assertSetEqual(
            set(vinculos.filter(principal=False, ativo=True).values_list('cnae__codigo', flat=True)),
            {'6201501', '8599604'},
        )

    def test_importacao_idempotente(self):
        primeira, criada = importar_registro(registro_valido())
        segunda, criada_novamente = importar_registro(registro_valido())
        self.assertTrue(criada)
        self.assertFalse(criada_novamente)
        self.assertEqual(primeira, segunda)
        self.assertEqual(Empresa.objects.count(), 1)
        self.assertEqual(CNAE.objects.count(), 3)
        self.assertEqual(EmpresaCNAE.objects.count(), 3)

    def test_dry_run_e_importacao_enriquecidos_usam_o_mesmo_registro_final(self):
        provider_dry_run = FakeProvider('OpenCNPJ', CNPJData(
            cnpj='11222333000181', email='enriquecido@example.com',
        ))
        provider_importacao = FakeProvider('OpenCNPJ', CNPJData(
            cnpj='11222333000181', email='enriquecido@example.com',
        ))
        original = registro_valido(email='')

        dry_run = discover_batch(
            limit=10, dry_run=True, enriquecer=True,
            client=FakeClient([original]), enrichment_providers=(provider_dry_run,),
        )
        importacao = discover_batch(
            limit=10, dry_run=False, enriquecer=True,
            client=FakeClient([original]), enrichment_providers=(provider_importacao,),
        )

        self.assertEqual(dry_run.itens[0].registro_final, importacao.itens[0].registro_final)
        self.assertEqual(Empresa.objects.get().email, dry_run.itens[0].email)

    def test_fallback_brasil_api_e_persistido_sem_sobrescrever_minha_receita(self):
        providers = (
            FakeProvider('OpenCNPJ', error=CNPJProviderError('indisponível')),
            FakeProvider('BrasilAPI', CNPJData(
                cnpj='11222333000181', email='fallback@example.com',
                razao_social='Razão que não deve sobrescrever',
            )),
        )

        discover_batch(
            limit=10, dry_run=False, enriquecer=True,
            client=FakeClient([registro_valido(email='')]), enrichment_providers=providers,
        )

        empresa = Empresa.objects.get()
        self.assertEqual(empresa.email, 'fallback@example.com')
        self.assertEqual(empresa.razao_social, 'Empresa Botucatu Ltda')

    def test_falha_do_enriquecimento_importa_dados_originais_elegiveis(self):
        providers = (
            FakeProvider('OpenCNPJ', error=CNPJProviderError('erro 1')),
            FakeProvider('BrasilAPI', error=CNPJProviderError('erro 2')),
        )

        resultado = discover_batch(
            limit=10, dry_run=False, enriquecer=True,
            client=FakeClient([registro_valido(email='')]), enrichment_providers=providers,
        )

        empresa = Empresa.objects.get()
        self.assertEqual(resultado.importadas, 1)
        self.assertEqual(empresa.razao_social, 'Empresa Botucatu Ltda')
        self.assertEqual(empresa.email, '')

    def test_rejeitada_nao_e_enriquecida_nem_importada(self):
        provider = FakeProvider('OpenCNPJ', CNPJData(
            cnpj='11222333000181', email='nao-usar@example.com',
        ))

        resultado = discover_batch(
            limit=10, dry_run=False, enriquecer=True,
            client=FakeClient([registro_valido(descricao_situacao_cadastral='BAIXADA')]),
            enrichment_providers=(provider,),
        )

        self.assertEqual(provider.calls, [])
        self.assertEqual(resultado.importadas, 0)
        self.assertFalse(Empresa.objects.exists())

    def test_cnaes_enriquecidos_sao_persistidos_sem_duplicidade(self):
        provider = FakeProvider('OpenCNPJ', CNPJData(cnpj='11222333000181', cnaes=[
            {'codigo': '6201501', 'descricao': 'Duplicado', 'principal': False},
            {'codigo': '6201501', 'descricao': 'Duplicado novamente', 'principal': False},
            {'codigo': '5611201', 'descricao': 'Restaurante', 'principal': False},
        ]))

        discover_batch(
            limit=10, dry_run=False, enriquecer=True,
            client=FakeClient([registro_valido(email='')]), enrichment_providers=(provider,),
        )

        codigos = list(EmpresaCNAE.objects.values_list('cnae__codigo', flat=True))
        self.assertEqual(codigos.count('6201501'), 1)
        self.assertEqual(codigos.count('5611201'), 1)

    def test_rejeicao_ocorre_antes_de_qualquer_criacao(self):
        with self.assertRaisesMessage(ValidationError, 'Município diferente'):
            importar_registro(registro_valido(municipio='Bauru'))
        self.assertFalse(Empresa.objects.exists())
        self.assertFalse(CNAE.objects.exists())
        self.assertFalse(EmpresaCNAE.objects.exists())

    @patch('apps.organizations.services.botucatu_discovery.importar_registro')
    def test_falha_em_um_registro_nao_interrompe_os_demais(self, importar):
        segunda = registro_valido(cnpj='19.131.243/0001-97')
        empresa = Empresa(nome_fantasia='Segunda')
        importar.side_effect = [ValidationError('falha isolada'), (empresa, True)]

        resultado = discover_batch(
            limit=2, dry_run=False, client=FakeClient([registro_valido(), segunda]),
        )

        self.assertEqual(importar.call_count, 2)
        self.assertEqual(resultado.itens[0].resultado, 'ERRO')
        self.assertEqual(resultado.importadas, 1)
