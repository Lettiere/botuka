from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import AcessoModulo, ConcessaoPermissao
from apps.core.models import Permissao
from apps.organizations.models import CNAE, Empresa, EmpresaCNAE, SubcategoriaCNAE
from apps.taxonomy.models import Categoria, Subcategoria


class BusinessTaxonomyManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.master = User.objects.create_superuser('taxonomy-master', password='x')
        cls.operator = User.objects.create_user('taxonomy-operator', password='x')
        cls.outsider = User.objects.create_user('taxonomy-outsider', password='x')
        for code in ('gestao.acessar', 'categorias.gerenciar'):
            access = AcessoModulo.objects.create(
                usuario=cls.operator, modulo=code.split('.', 1)[0],
                concedido_por=cls.master, justificativa='Teste',
            )
            permission, _ = Permissao.objects.get_or_create(
                codigo=code, defaults={
                    'modulo': code.split('.', 1)[0], 'nome': code,
                    'descricao': 'Teste',
                },
            )
            ConcessaoPermissao.objects.create(
                acesso=access, usuario=cls.operator, permissao=permission,
                concedida_por=cls.master, justificativa='Teste',
            )
        cls.category = Categoria.objects.create(nome='Comércio empresarial')
        cls.subcategory = Subcategoria.objects.create(
            categoria=cls.category, nome='Mercado empresarial',
        )
        cls.cnae = CNAE.objects.create(codigo='4711302', descricao='Comércio varejista')

    def test_cnae_crud_search_filter_status_and_csrf(self):
        self.client.force_login(self.operator)
        list_url = reverse('gestao:taxonomia_empresarial_lista', args=['cnaes'])
        self.assertContains(self.client.get(list_url, {'q': '4711', 'ativo': '1'}), 'Comércio varejista')
        create_url = reverse('gestao:taxonomia_empresarial_novo', args=['cnaes'])
        self.assertEqual(self.client.post(create_url, {'codigo': '', 'descricao': ''}).status_code, 200)
        response = self.client.post(create_url, {
            'codigo': '6201501', 'descricao': 'Desenvolvimento de programas', 'ativo': 'on',
        })
        created = CNAE.objects.get(codigo='6201501')
        detail_url = reverse('gestao:taxonomia_empresarial_detalhe', args=['cnaes', created.pk])
        self.assertRedirects(response, detail_url)
        response = self.client.post(reverse(
            'gestao:taxonomia_empresarial_editar', args=['cnaes', created.pk],
        ), {'codigo': created.codigo, 'descricao': 'Software sob encomenda', 'ativo': 'on'})
        self.assertRedirects(response, detail_url)
        status_url = reverse('gestao:taxonomia_empresarial_status', args=['cnaes', created.pk])
        self.assertEqual(self.client.get(status_url).status_code, 405)
        self.client.post(status_url)
        created.refresh_from_db()
        self.assertFalse(created.ativo)
        self.assertTrue(CNAE.objects.filter(pk=created.pk).exists())
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.operator)
        self.assertEqual(csrf.post(status_url).status_code, 403)

    def test_mapping_and_company_classification_validation(self):
        self.client.force_login(self.operator)
        mapping_url = reverse('gestao:taxonomia_empresarial_novo', args=['mapeamentos'])
        response = self.client.post(mapping_url, {
            'subcategoria': self.subcategory.pk, 'cnae': self.cnae.pk,
            'relevancia': 90, 'principal': 'on', 'revisado': 'on', 'ativo': 'on',
        })
        mapping = SubcategoriaCNAE.objects.get(subcategoria=self.subcategory, cnae=self.cnae)
        self.assertRedirects(response, reverse(
            'gestao:taxonomia_empresarial_detalhe', args=['mapeamentos', mapping.pk],
        ))
        company = Empresa.objects.create(nome_fantasia='Empresa CNAE')
        EmpresaCNAE.objects.create(empresa=company, cnae=self.cnae, principal=True)
        second = CNAE.objects.create(codigo='6202300', descricao='Consultoria')
        duplicate = self.client.post(reverse(
            'gestao:taxonomia_empresarial_novo', args=['empresas-cnaes'],
        ), {'empresa': company.pk, 'cnae': second.pk, 'principal': 'on',
            'origem': EmpresaCNAE.Origem.ADMINISTRATIVO, 'ativo': 'on'})
        self.assertEqual(duplicate.status_code, 200)
        self.assertContains(duplicate, 'já possui um CNAE principal')

        duplicate_mapping = self.client.post(mapping_url, {
            'subcategoria': self.subcategory.pk, 'cnae': self.cnae.pk,
            'relevancia': 50, 'ativo': 'on',
        })
        self.assertEqual(duplicate_mapping.status_code, 200)
        self.assertContains(duplicate_mapping, 'já existe')

    def test_company_main_cnae_reactivation_conflict_is_blocked(self):
        company = Empresa.objects.create(nome_fantasia='Empresa conflito CNAE')
        inactive_main = EmpresaCNAE.objects.create(
            empresa=company, cnae=self.cnae, principal=True, ativo=False,
        )
        other = CNAE.objects.create(codigo='7490104', descricao='Intermediação')
        EmpresaCNAE.objects.create(empresa=company, cnae=other, principal=True, ativo=True)
        self.client.force_login(self.operator)
        response = self.client.post(reverse(
            'gestao:taxonomia_empresarial_status',
            args=['empresas-cnaes', inactive_main.pk],
        ))
        self.assertRedirects(response, reverse(
            'gestao:taxonomia_empresarial_detalhe',
            args=['empresas-cnaes', inactive_main.pk],
        ))
        inactive_main.refresh_from_db()
        self.assertFalse(inactive_main.ativo)
        self.assertContains(
            self.client.get(reverse('gestao:taxonomia_empresarial_detalhe', args=['empresas-cnaes', inactive_main.pk])),
            'Inativo',
        )

    def test_category_and_subcategory_detail_soft_status(self):
        self.client.force_login(self.operator)
        for slug, instance in (('categorias', self.category), ('subcategorias', self.subcategory)):
            detail = reverse(f'gestao:{slug}_detalhe', args=[instance.pk])
            status = reverse(f'gestao:{slug}_status', args=[instance.pk])
            self.assertEqual(self.client.get(detail).status_code, 200)
            self.assertEqual(self.client.get(status).status_code, 405)
            self.assertRedirects(self.client.post(status), detail)
            instance.refresh_from_db()
            self.assertFalse(instance.ativo)
            self.assertIsNotNone(instance.removido_em)

    def test_category_subcategory_crud_filters_and_parent_integrity(self):
        self.client.force_login(self.operator)
        category_list = self.client.get(reverse('gestao:categorias_lista'), {
            'q': 'Comércio', 'ativo': '1',
        })
        self.assertContains(category_list, self.category.nome)
        subcategory_list = self.client.get(reverse('gestao:subcategorias_lista'), {
            'categoria': self.category.pk, 'q': 'Mercado',
        })
        self.assertContains(subcategory_list, self.subcategory.nome)

        response = self.client.post(reverse('gestao:categorias_novo'), {
            'nome': 'Serviços especializados', 'slug': '', 'descricao': '',
            'icone': '', 'ordem': 5, 'ativo': 'on',
        })
        created_category = Categoria.objects.get(nome='Serviços especializados')
        self.assertRedirects(response, reverse('gestao:categorias_detalhe', args=[created_category.pk]))
        response = self.client.post(reverse('gestao:subcategorias_novo'), {
            'categoria': created_category.pk, 'nome': 'Consultoria empresarial',
            'slug': '', 'descricao': '', 'ordem': 1, 'ativo': 'on',
        })
        created_subcategory = Subcategoria.objects.get(nome='Consultoria empresarial')
        self.assertRedirects(response, reverse('gestao:subcategorias_detalhe', args=[created_subcategory.pk]))

        self.client.post(reverse('gestao:categorias_status', args=[created_category.pk]))
        invalid_parent = self.client.post(reverse('gestao:subcategorias_novo'), {
            'categoria': created_category.pk, 'nome': 'Vínculo inválido',
            'slug': '', 'descricao': '', 'ordem': 2, 'ativo': 'on',
        })
        self.assertEqual(invalid_parent.status_code, 200)
        self.assertContains(invalid_parent, 'Faça uma escolha válida')

    def test_cnae_duplicate_filters_details_and_query_limits(self):
        self.client.force_login(self.operator)
        duplicate = self.client.post(reverse(
            'gestao:taxonomia_empresarial_novo', args=['cnaes'],
        ), {'codigo': self.cnae.codigo, 'descricao': 'Duplicado', 'ativo': 'on'})
        self.assertEqual(duplicate.status_code, 200)
        self.assertContains(duplicate, 'já existe')

        mapping = SubcategoriaCNAE.objects.create(
            subcategoria=self.subcategory, cnae=self.cnae, relevancia=80,
            principal=True, revisado=True,
        )
        response = self.client.get(reverse(
            'gestao:taxonomia_empresarial_lista', args=['mapeamentos'],
        ), {'categoria': self.category.pk, 'subcategoria': self.subcategory.pk,
            'principal': '1', 'revisado': '1'})
        self.assertContains(response, mapping.cnae.codigo)

        self.client.force_login(self.master)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse(
                'gestao:taxonomia_empresarial_lista', args=['mapeamentos'],
            ))
            self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 18)

    def test_access_and_unknown_kind(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse(
            'gestao:taxonomia_empresarial_lista', args=['cnaes'],
        )).status_code, 403)
        self.client.force_login(self.master)
        self.assertEqual(self.client.get(reverse(
            'gestao:taxonomia_empresarial_lista', args=['unknown'],
        )).status_code, 404)

    def test_pagination(self):
        CNAE.objects.bulk_create([
            CNAE(codigo=f'99{index:05d}', descricao=f'Atividade {index}') for index in range(26)
        ])
        self.client.force_login(self.operator)
        response = self.client.get(reverse('gestao:taxonomia_empresarial_lista', args=['cnaes']))
        self.assertTrue(response.context['page_obj'].has_next())
        self.assertEqual(len(response.context['page_obj'].object_list), 25)
