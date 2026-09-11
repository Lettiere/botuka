from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import (
    CNAE, Empresa, EmpresaCNAE, EmpresaImportacaoExecucao, EmpresaPropriedade, EmpresaUsuario,
)
from apps.painel.navigation import painel_navigation


class EmpresasImportadasPainelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.master = get_user_model().objects.create_superuser('master-importadas', password='x')
        cls.usuario = get_user_model().objects.create_user('usuario-importadas', password='x')
        cls.outro = get_user_model().objects.create_user('outro-importadas', password='x')
        pais = Pais.objects.create(nome='Brasil importadas', codigo_iso_2='BI', codigo_iso_3='BIR')
        cls.estado = Estado.objects.create(pais=pais, nome='São Paulo importadas', sigla='SP')
        cls.cidade = Cidade.objects.create(estado=cls.estado, nome='Botucatu importadas')

    def _empresa(self, nome, **kwargs):
        defaults = {
            'nome_fantasia': nome, 'razao_social': f'{nome} Ltda',
            'tipo_cadastro': Empresa.TipoCadastro.EMPRESA,
            'status': Empresa.Status.ATIVA, 'ativo': True, 'perfil_publico': True,
            'estado': self.estado, 'cidade': self.cidade,
        }
        defaults.update(kwargs)
        return Empresa.objects.create(**defaults)

    def _navigation(self, usuario):
        request = RequestFactory().get(reverse('painel:dashboard'))
        request.user = usuario
        request.session = {}
        return painel_navigation(request)

    def test_importada_sem_vinculos_nao_aparece_no_select_inclusive_para_master(self):
        importada = self._empresa('Importada sem vínculo')
        self.assertNotIn(importada, self._navigation(self.usuario)['empresas_nav'])
        self.assertNotIn(importada, self._navigation(self.master)['empresas_nav'])

    def test_empresa_usuario_ativo_e_propriedade_atual_aparecem(self):
        por_vinculo = self._empresa('Empresa vinculada')
        EmpresaUsuario.objects.create(empresa=por_vinculo, usuario=self.usuario, ativo=True)
        por_propriedade = self._empresa('Empresa por propriedade')
        EmpresaPropriedade.objects.create(empresa=por_propriedade, usuario=self.usuario, atual=True)
        empresas = self._navigation(self.usuario)['empresas_nav']
        self.assertIn(por_vinculo, empresas)
        self.assertIn(por_propriedade, empresas)

    def test_proprietario_legado_aparece_e_empresa_de_outro_usuario_nao(self):
        propria = self._empresa('Proprietário legado', usuario_proprietario=self.usuario)
        alheia = self._empresa('Empresa alheia', usuario_proprietario=self.outro)
        empresas = self._navigation(self.usuario)['empresas_nav']
        self.assertIn(propria, empresas)
        self.assertNotIn(alheia, empresas)

    def test_card_importadas_so_aparece_para_autorizado(self):
        self.client.force_login(self.master)
        self.assertContains(self.client.get(reverse('painel:dashboard')), 'Empresas importadas')
        self.client.force_login(self.usuario)
        self.assertNotContains(self.client.get(reverse('painel:dashboard')), 'Empresas importadas')

    def test_view_exige_permissao(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse('painel:empresas_importadas')).status_code, 403)
        self.client.force_login(self.master)
        self.assertEqual(self.client.get(reverse('painel:empresas_importadas')).status_code, 200)

    def test_status_da_ultima_sincronizacao_aparece(self):
        EmpresaImportacaoExecucao.objects.create(
            tipo_execucao='SEMANAL', status='CONCLUIDA', paginas_processadas=3,
            registros_recebidos=2049, importados=12, ja_existentes=2000,
            rejeitados=37, erros=1,
        )
        self.client.force_login(self.master)
        response = self.client.get(reverse('painel:empresas_importadas'))
        self.assertContains(response, 'Status da sincronização')
        self.assertContains(response, '2049')
        self.assertContains(response, 'Próxima execução prevista')

    def test_sincronizacao_manual_exige_permissao_e_usa_orquestrador(self):
        url = reverse('painel:empresas_importadas_sincronizar')
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.post(url).status_code, 403)
        execucao = EmpresaImportacaoExecucao(tipo_execucao='MANUAL', status='CONCLUIDA')
        execucao.pk = 99
        self.client.force_login(self.master)
        from unittest.mock import patch
        with patch('apps.painel.views.sincronizar_empresas', return_value=execucao) as servico:
            response = self.client.post(url)
        self.assertRedirects(response, reverse('painel:empresas_importadas'))
        servico.assert_called_once_with(tipo_execucao='MANUAL')

    def test_listagem_paginada_e_sem_classificacao_nao_quebra(self):
        for numero in range(26):
            self._empresa(f'Importada {numero:02d}')
        self.client.force_login(self.master)
        response = self.client.get(reverse('painel:empresas_importadas'))
        self.assertEqual(len(response.context['empresas']), 25)
        self.assertEqual(response.context['page_obj'].paginator.count, 26)
        self.assertContains(response, '—')

    def test_filtros_nome_cnpj_e_cnae(self):
        alvo = self._empresa('Alvo filtros', cpf_cnpj='11222333000181')
        self._empresa('Outra empresa', cpf_cnpj='99888777000166')
        cnae = CNAE.objects.create(codigo='4711302', descricao='Comércio varejista filtros')
        EmpresaCNAE.objects.create(empresa=alvo, cnae=cnae, principal=True, ativo=True)
        self.client.force_login(self.master)
        url = reverse('painel:empresas_importadas')
        for params in ({'busca': 'Alvo'}, {'cnpj': '11.222.333/0001-81'}, {'cnae': '4711302'}):
            response = self.client.get(url, params)
            self.assertEqual(list(response.context['empresas']), [alvo])

    def test_consulta_nao_cria_vinculos_e_empresa_permanece_publica(self):
        importada = self._empresa('Importada pública')
        self.client.force_login(self.master)
        self.client.get(reverse('painel:empresas_importadas'))
        self.assertFalse(EmpresaUsuario.objects.filter(empresa=importada).exists())
        self.assertFalse(EmpresaPropriedade.objects.filter(empresa=importada).exists())
        self.client.force_login(self.usuario)
        self.assertContains(self.client.get(reverse('publico:empresas')), importada.nome_fantasia)
