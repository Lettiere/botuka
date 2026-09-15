from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import AcessoModulo, ConcessaoPermissao
from apps.core.models import Permissao
from apps.locations.models import Bairro, Cidade, Estado, Pais
from apps.organizations.models import (
    Capacidade,
    CNAE,
    Empresa,
    EmpresaCapacidade,
    EmpresaCNAE,
    EmpresaPropriedade,
    EmpresaSolicitacao,
    EmpresaUsuario,
    EmpresaFuncao,
    Endereco,
    Organizacao,
    Unidade,
)
from apps.taxonomy.models import Categoria


class GestaoCompaniesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.master = users.objects.create_superuser('company-master', password='x')
        cls.limited = users.objects.create_user('company-limited', password='x')
        cls.owner = users.objects.create_user(
            'company-owner', email='owner@example.com', password='x',
        )
        cls.member = users.objects.create_user(
            'company-member', email='member@example.com', password='x',
        )
        cls.access = AcessoModulo.objects.create(
            usuario=cls.limited, modulo='gestao', concedido_por=cls.master,
            justificativa='Teste',
        )
        permission = Permissao.objects.get(codigo='gestao.acessar')
        ConcessaoPermissao.objects.create(
            acesso=cls.access, usuario=cls.limited, permissao=permission,
            concedida_por=cls.master, justificativa='Teste',
        )
        country = Pais.objects.create(nome='Brasil Empresas', codigo_iso_2='BE', codigo_iso_3='BRE')
        cls.state = Estado.objects.create(pais=country, nome='São Paulo Empresas', sigla='EE')
        cls.city = Cidade.objects.create(estado=cls.state, nome='Botucatu Empresas')
        cls.neighborhood = Bairro.objects.create(cidade=cls.city, nome='Centro Empresas')
        cls.category = Categoria.objects.create(nome='Categoria Empresa Legada')
        cls.company = Empresa.objects.create(
            nome_fantasia='Empresa Auditada', usuario_proprietario=cls.owner,
            tipo_cadastro=Empresa.TipoCadastro.INFORMAL,
            origem_cadastro=Empresa.OrigemCadastro.ADMIN,
            atuacao=Empresa.Atuacao.SERVICOS, estado=cls.state, cidade=cls.city,
            status=Empresa.Status.ATIVA, ativo=True,
        )
        cls.owner_link = EmpresaUsuario.objects.create(
            empresa=cls.company, usuario=cls.owner,
            funcao=EmpresaUsuario.Funcao.PROPRIETARIO,
        )
        EmpresaPropriedade.objects.create(
            empresa=cls.company, usuario=cls.owner,
            origem=EmpresaPropriedade.Origem.CADASTRO, atual=True,
        )
        cls.request = EmpresaSolicitacao.objects.create(
            empresa=cls.company, usuario_solicitante=cls.member,
            tipo_solicitacao=EmpresaSolicitacao.TipoSolicitacao.REIVINDICACAO,
            status=EmpresaSolicitacao.Status.PENDENTE,
        )
        capability = Capacidade.objects.create(
            codigo='TESTAR_GESTAO', nome='Testar gestão', exige_aprovacao=True,
        )
        cls.company_capability = EmpresaCapacidade.objects.create(
            empresa=cls.company, capacidade=capability,
            status=EmpresaCapacidade.Status.PENDENTE,
        )
        cnae = CNAE.objects.create(codigo='6201-5/01', descricao='Desenvolvimento de programas')
        EmpresaCNAE.objects.create(
            empresa=cls.company, cnae=cnae, principal=True,
            origem=EmpresaCNAE.Origem.ADMINISTRATIVO,
        )
        cls.legacy_organization = Organizacao.objects.create(
            proprietario=cls.owner, categoria=cls.category,
            nome_fantasia='Organização legada auditada',
        )
        cls.legacy_unit = Unidade.objects.create(
            organizacao=cls.legacy_organization, categoria=cls.category,
            nome='Unidade legada auditada', principal=True,
        )
        cls.legacy_address = Endereco.objects.create(
            unidade=cls.legacy_unit, cidade=cls.city, bairro=cls.neighborhood,
            logradouro='Rua da Auditoria', numero='3',
        )

    def company_data(self, **overrides):
        data = {
            'usuario_proprietario': self.owner.pk,
            'tipo_cadastro': Empresa.TipoCadastro.INFORMAL,
            'origem_cadastro': Empresa.OrigemCadastro.ADMIN,
            'atuacao': Empresa.Atuacao.SERVICOS,
            'razao_social': '', 'nome_fantasia': 'Nova Empresa Gestão',
            'cpf_cnpj': '', 'inscricao_estadual': '', 'inscricao_municipal': '',
            'categoria_empresa': '', 'subcategoria_empresa': '',
            'modalidade_comercial': '', 'descricao_curta': '',
            'descricao_completa': '', 'telefone': '', 'whatsapp': '',
            'email': '', 'site': '', 'cep': '', 'endereco': '', 'numero': '',
            'complemento': '', 'bairro': '', 'estado': self.state.pk,
            'cidade': self.city.pk, 'atende_local': 'on',
            'horario_atendimento': '', 'status': Empresa.Status.RASCUNHO,
            'ativo': 'on',
        }
        data.update(overrides)
        return data

    def test_access_list_detail_filters_and_reverse(self):
        self.client.force_login(self.limited)
        self.assertEqual(self.client.get(reverse('gestao:empresas_lista')).status_code, 403)
        self.client.force_login(self.master)
        response = self.client.get(reverse('gestao:empresas_lista'), {
            'q': 'Auditada', 'status': Empresa.Status.ATIVA, 'ativo': '1',
            'tipo': Empresa.TipoCadastro.INFORMAL,
            'origem': self.company.origem_cadastro,
            'cidade': self.city.pk, 'propriedade': '1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.company.nome_fantasia)
        detail = self.client.get(reverse('gestao:empresa_detalhe', args=[self.company.uuid]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'Histórico de propriedade')
        self.assertContains(detail, 'Testar gestão')
        self.assertContains(detail, '6201-5/01')

    def test_create_valid_invalid_and_update(self):
        self.client.force_login(self.master)
        create_url = reverse('gestao:empresa_nova')
        invalid = self.client.post(create_url, self.company_data(nome_fantasia=''))
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, 'Este campo é obrigatório')
        response = self.client.post(create_url, self.company_data())
        created = Empresa.all_objects.get(nome_fantasia='Nova Empresa Gestão')
        self.assertRedirects(response, reverse('gestao:empresa_detalhe', args=[created.uuid]))
        self.assertEqual(created.criado_por, self.master)
        self.assertEqual(created.origem_cadastro, Empresa.OrigemCadastro.ADMIN)
        owner_link = EmpresaUsuario.objects.get(empresa=created, usuario=self.owner)
        self.assertTrue(owner_link.proprietario)
        self.assertTrue(owner_link.administrador)
        self.assertTrue(owner_link.pode_editar)

        update_url = reverse('gestao:empresa_editar', args=[created.uuid])
        response = self.client.post(update_url, self.company_data(
            nome_fantasia='Empresa Atualizada', usuario_proprietario=self.member.pk,
        ))
        self.assertRedirects(response, reverse('gestao:empresa_detalhe', args=[created.uuid]))
        created.refresh_from_db()
        self.assertEqual(created.nome_fantasia, 'Empresa Atualizada')
        self.assertEqual(created.usuario_proprietario, self.owner)

    def test_operator_with_domain_permission_can_access_companies(self):
        permission = Permissao.objects.create(
            modulo='empresas', grupo='Empresas', codigo='empresas.gerenciar',
            nome='Gerenciar empresas',
        )
        company_access = AcessoModulo.objects.create(
            usuario=self.limited, modulo='empresas', concedido_por=self.master,
            justificativa='Operação empresarial',
        )
        ConcessaoPermissao.objects.create(
            acesso=company_access, usuario=self.limited, permissao=permission,
            concedida_por=self.master, justificativa='Operação empresarial',
        )
        self.client.force_login(self.limited)
        self.assertEqual(self.client.get(reverse('gestao:empresas_lista')).status_code, 200)
        self.assertEqual(self.client.get(
            reverse('gestao:empresa_detalhe', args=[self.company.uuid]),
        ).status_code, 200)

    def test_inactivation_is_post_only_soft_and_reversible(self):
        self.client.force_login(self.master)
        url = reverse('gestao:empresa_inativar', args=[self.company.uuid])
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertRedirects(response, reverse('gestao:empresa_detalhe', args=[self.company.uuid]))
        self.company.refresh_from_db()
        self.assertFalse(self.company.ativo)
        self.assertIsNotNone(self.company.excluido_em)
        self.assertTrue(Empresa.all_objects.filter(pk=self.company.pk).exists())
        self.client.post(reverse('gestao:empresa_reativar', args=[self.company.uuid]))
        self.company.refresh_from_db()
        self.assertTrue(self.company.ativo)
        self.assertIsNone(self.company.excluido_em)

    def test_vinculo_create_validation_and_owner_protection(self):
        self.client.force_login(self.master)
        url = reverse('gestao:empresa_vinculo_novo', args=[self.company.uuid])
        invalid = self.client.post(url, {'email': 'missing@example.com', 'funcao': 'EDITOR'})
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, 'Nenhum usuário ativo')
        response = self.client.post(url, {
            'email': self.member.email, 'funcao': EmpresaUsuario.Funcao.EDITOR,
            'pode_editar': 'on', 'ativo': 'on',
        })
        self.assertRedirects(response, reverse('gestao:empresa_detalhe', args=[self.company.uuid]))
        link = EmpresaUsuario.objects.get(empresa=self.company, usuario=self.member)
        self.assertTrue(link.pode_editar)
        inactivate_url = reverse(
            'gestao:empresa_vinculo_inativar', args=[self.company.uuid, link.pk],
        )
        self.assertEqual(self.client.get(inactivate_url).status_code, 405)
        self.client.post(inactivate_url)
        link.refresh_from_db()
        self.assertFalse(link.ativo)
        reactivate_url = reverse(
            'gestao:empresa_vinculo_reativar', args=[self.company.uuid, link.pk],
        )
        self.assertEqual(self.client.get(reactivate_url).status_code, 405)
        self.client.post(reactivate_url)
        link.refresh_from_db()
        self.assertTrue(link.ativo)
        owner_url = reverse(
            'gestao:empresa_vinculo_inativar', args=[self.company.uuid, self.owner_link.pk],
        )
        self.assertEqual(self.client.post(owner_url).status_code, 403)
        self.owner_link.refresh_from_db()
        self.assertTrue(self.owner_link.ativo)

    def test_request_decision_validation_and_audit_fields(self):
        self.client.force_login(self.master)
        url = reverse('gestao:solicitacao_analisar', args=[self.request.pk])
        invalid = self.client.post(url, {
            'status': EmpresaSolicitacao.Status.REJEITADA, 'motivo_decisao': '',
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, 'Informe o motivo desta decisão')
        response = self.client.post(url, {
            'status': EmpresaSolicitacao.Status.REJEITADA,
            'motivo_decisao': 'Documento insuficiente.',
        })
        self.assertRedirects(response, reverse('gestao:solicitacoes_lista'))
        self.request.refresh_from_db()
        self.assertEqual(self.request.analisado_por, self.master)
        self.assertIsNotNone(self.request.analisado_em)

    def test_capability_rejection_requires_reason_and_approval_is_audited(self):
        self.client.force_login(self.master)
        url = reverse(
            'gestao:empresa_capacidade_editar',
            args=[self.company.uuid, self.company_capability.pk],
        )
        invalid = self.client.post(url, {
            'status': EmpresaCapacidade.Status.REJEITADA,
            'motivo_rejeicao': '', 'ativo': 'on',
        })
        self.assertEqual(invalid.status_code, 200)
        response = self.client.post(url, {
            'status': EmpresaCapacidade.Status.APROVADA,
            'motivo_rejeicao': '', 'ativo': 'on',
        })
        self.assertRedirects(response, reverse('gestao:empresa_detalhe', args=[self.company.uuid]))
        self.company_capability.refresh_from_db()
        self.assertEqual(self.company_capability.aprovado_por, self.master)
        self.assertIsNotNone(self.company_capability.aprovado_em)

    def test_pagination(self):
        Empresa.all_objects.bulk_create([
            Empresa(
                nome_fantasia=f'Empresa página {index}',
                slug=f'empresa-pagina-{index}',
                status=Empresa.Status.RASCUNHO,
            )
            for index in range(26)
        ])
        self.client.force_login(self.master)
        response = self.client.get(reverse('gestao:empresas_lista'))
        self.assertTrue(response.context['page_obj'].has_next())
        self.assertEqual(len(response.context['page_obj'].object_list), 25)

    def test_mutations_require_csrf_and_critical_pages_have_bounded_queries(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.master)
        self.assertEqual(csrf_client.post(reverse(
            'gestao:empresa_inativar', args=[self.company.uuid],
        )).status_code, 403)

        self.client.force_login(self.master)
        with CaptureQueriesContext(connection) as list_queries:
            response = self.client.get(reverse('gestao:empresas_lista'))
            self.assertEqual(response.status_code, 200)
            list(response.context['page_obj'].object_list)
        self.assertLessEqual(len(list_queries), 12)
        with CaptureQueriesContext(connection) as detail_queries:
            response = self.client.get(reverse(
                'gestao:empresa_detalhe', args=[self.company.uuid],
            ))
            self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(detail_queries), 18)

    def test_legacy_cruds_have_list_detail_create_update_and_soft_status(self):
        self.client.force_login(self.master)
        cases = (
            ('organizacoes', self.legacy_organization),
            ('unidades', self.legacy_unit),
            ('enderecos', self.legacy_address),
        )
        for slug, instance in cases:
            with self.subTest(slug=slug):
                self.assertEqual(self.client.get(reverse(f'gestao:{slug}_lista')).status_code, 200)
                detail_url = reverse(f'gestao:{slug}_detalhe', args=[instance.pk])
                self.assertEqual(self.client.get(detail_url).status_code, 200)
                status_url = reverse(f'gestao:{slug}_status', args=[instance.pk])
                self.assertEqual(self.client.get(status_url).status_code, 405)
                response = self.client.post(status_url)
                self.assertRedirects(response, detail_url)
                instance.refresh_from_db()
                self.assertFalse(instance.ativo)
                self.assertIsNotNone(instance.removido_em)
                self.client.post(status_url)
                instance.refresh_from_db()
                self.assertTrue(instance.ativo)
                self.assertIsNone(instance.removido_em)

        invalid = self.client.post(reverse('gestao:organizacoes_novo'), {
            'proprietario': self.owner.pk, 'categoria': self.category.pk,
            'nome_fantasia': '', 'ativo': 'on',
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, 'Este campo é obrigatório')
        created = self.client.post(reverse('gestao:organizacoes_novo'), {
            'proprietario': self.owner.pk, 'categoria': self.category.pk,
            'nome_fantasia': 'Organização criada na Gestão', 'ativo': 'on',
        })
        self.assertRedirects(created, reverse('gestao:organizacoes_lista'))
        organization = Organizacao.objects.get(nome_fantasia='Organização criada na Gestão')
        updated = self.client.post(reverse('gestao:organizacoes_editar', args=[organization.pk]), {
            'proprietario': self.owner.pk, 'categoria': self.category.pk,
            'nome_fantasia': 'Organização atualizada na Gestão', 'ativo': 'on',
        })
        self.assertRedirects(updated, reverse('gestao:organizacoes_lista'))
        organization.refresh_from_db()
        self.assertEqual(organization.nome_fantasia, 'Organização atualizada na Gestão')

    def test_legacy_cruds_block_user_without_domain_permission(self):
        self.client.force_login(self.limited)
        for slug, instance in (
            ('organizacoes', self.legacy_organization),
            ('unidades', self.legacy_unit),
            ('enderecos', self.legacy_address),
        ):
            with self.subTest(slug=slug):
                self.assertEqual(
                    self.client.get(reverse(f'gestao:{slug}_detalhe', args=[instance.pk])).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.post(reverse(f'gestao:{slug}_status', args=[instance.pk])).status_code,
                    403,
                )

    def test_company_catalogs_complete_crud_without_physical_delete(self):
        self.client.force_login(self.master)
        cases = (
            ('capacidades', Capacidade, {
                'codigo': 'CATALOGO_TESTE', 'nome': 'Capacidade de catálogo',
                'descricao': 'Auditada', 'exige_aprovacao': 'on', 'ativo': 'on',
            }),
            ('funcoes', EmpresaFuncao, {
                'codigo': 'FUNCAO_TESTE', 'nome': 'Função de catálogo',
                'descricao': 'Auditada', 'ativo': 'on',
            }),
        )
        for kind, model, data in cases:
            with self.subTest(kind=kind):
                list_url = reverse('gestao:empresa_catalogo_lista', args=[kind])
                self.assertEqual(self.client.get(list_url).status_code, 200)
                create_url = reverse('gestao:empresa_catalogo_novo', args=[kind])
                invalid = self.client.post(create_url, {**data, 'codigo': ''})
                self.assertEqual(invalid.status_code, 200)
                self.assertContains(invalid, 'Este campo é obrigatório')
                created_response = self.client.post(create_url, data)
                instance = model.objects.get(codigo=data['codigo'])
                detail_url = reverse(
                    'gestao:empresa_catalogo_detalhe', args=[kind, instance.pk],
                )
                self.assertRedirects(created_response, detail_url)
                self.assertContains(self.client.get(detail_url), data['nome'])
                edit_data = {**data, 'nome': f'{data["nome"]} atualizada'}
                edited = self.client.post(reverse(
                    'gestao:empresa_catalogo_editar', args=[kind, instance.pk],
                ), edit_data)
                self.assertRedirects(edited, detail_url)
                instance.refresh_from_db()
                self.assertEqual(instance.nome, edit_data['nome'])
                self.assertContains(self.client.get(list_url, {'q': data['codigo']}), edit_data['nome'])
                status_url = reverse(
                    'gestao:empresa_catalogo_status', args=[kind, instance.pk],
                )
                self.assertEqual(self.client.get(status_url).status_code, 405)
                self.assertRedirects(self.client.post(status_url), detail_url)
                instance.refresh_from_db()
                self.assertFalse(instance.ativo)
                self.assertTrue(model.objects.filter(pk=instance.pk).exists())
                self.client.post(status_url)
                instance.refresh_from_db()
                self.assertTrue(instance.ativo)

    def test_company_catalogs_require_master_and_csrf(self):
        capability = Capacidade.objects.get(codigo='TESTAR_GESTAO')
        urls = (
            reverse('gestao:empresa_catalogo_lista', args=['capacidades']),
            reverse('gestao:empresa_catalogo_novo', args=['capacidades']),
            reverse('gestao:empresa_catalogo_detalhe', args=['capacidades', capability.pk]),
            reverse('gestao:empresa_catalogo_editar', args=['capacidades', capability.pk]),
        )
        self.client.force_login(self.limited)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        status_url = reverse(
            'gestao:empresa_catalogo_status', args=['capacidades', capability.pk],
        )
        self.assertEqual(self.client.post(status_url).status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.master)
        self.assertEqual(csrf_client.post(status_url).status_code, 403)

    def test_company_catalog_pagination_and_unknown_catalog(self):
        EmpresaFuncao.objects.bulk_create([
            EmpresaFuncao(codigo=f'PAG_{index}', nome=f'Função página {index}')
            for index in range(26)
        ])
        self.client.force_login(self.master)
        response = self.client.get(reverse(
            'gestao:empresa_catalogo_lista', args=['funcoes'],
        ))
        self.assertTrue(response.context['page_obj'].has_next())
        self.assertEqual(len(response.context['page_obj'].object_list), 25)
        self.assertEqual(self.client.get(reverse(
            'gestao:empresa_catalogo_lista', args=['inexistente'],
        )).status_code, 404)
