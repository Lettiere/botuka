from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.authorization import criar_verificador_permissoes
from apps.core.models import Perfil, PerfilPermissao, Permissao
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Capacidade, Empresa, EmpresaCapacidade
from apps.painel.navigation import painel_navigation

from .forms import ProdutoForm
from .models import Produto
from .permissions import pode_editar
from .services import calcular_limite, validar_contexto


class ProductsAdministrativeIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.master = User.objects.create_superuser('products_master', 'master@example.com', 'safe-password')
        cls.user = User.objects.create_user('products_user', password='safe-password')
        cls.other = User.objects.create_user('products_other', password='safe-password')
        cls.profile = Perfil.objects.create(nome='VENDEDOR PRODUTOS')
        cls.user.perfil = cls.profile
        cls.user.save(update_fields=['perfil'])
        cls.permissions = {
            item.codigo: item for item in Permissao.objects.filter(modulo='products')
        }
        for code in ('products.acessar', 'products.visualizar', 'products.criar_proprio'):
            PerfilPermissao.objects.create(perfil=cls.profile, permissao=cls.permissions[code])
        country = Pais.objects.create(nome='Brasil Produtos Integração', codigo_iso_2='PI', codigo_iso_3='PIT')
        state = Estado.objects.create(pais=country, nome='Estado Produtos', sigla='PX')
        city = Cidade.objects.create(estado=state, nome='Cidade Produtos')
        cls.company = Empresa.objects.create(
            usuario_proprietario=cls.user, nome_fantasia='Loja Integrada',
            cidade=city, estado=state, status=Empresa.Status.ATIVA,
            perfil_publico=True, verificada=True,
        )
        cls.other_company = Empresa.objects.create(
            usuario_proprietario=cls.other, nome_fantasia='Loja Alheia',
            cidade=city, estado=state, status=Empresa.Status.ATIVA,
        )

    def product(self, **overrides):
        values = {
            'nome': 'Produto integrado', 'categoria': 'Comércio',
            'descricao_curta': 'Produto de teste integrado.',
            'descricao_completa': '<p>Descrição</p>', 'preco': Decimal('20.00'),
            'titular_tipo': Produto.TitularTipo.PESSOA_FISICA,
            'criador_registro': self.user, 'proprietario': self.user,
            'responsavel': self.user,
        }
        values.update(overrides)
        return Produto.objects.create(**values)

    def test_products_permissions_are_dynamic_and_grouped_in_management(self):
        self.client.force_login(self.master)
        response = self.client.get(reverse('gestao:perfil_permissoes', args=[self.profile.pk]))
        self.assertContains(response, 'Produtos')
        self.assertContains(response, 'products.acessar')
        self.assertContains(response, 'products.gerenciar_atributos')

    def test_permission_change_is_effective_on_next_check_without_logout(self):
        self.assertFalse(criar_verificador_permissoes(self.user)('products.editar_empresa'))
        PerfilPermissao.objects.create(
            perfil=self.profile, permissao=self.permissions['products.editar_empresa'],
        )
        self.assertTrue(criar_verificador_permissoes(self.user)('products.editar_empresa'))

    def test_menu_and_dashboard_follow_real_permission(self):
        request = RequestFactory().get('/painel/')
        request.user = self.user
        labels = [
            item['label'] for group in painel_navigation(request)['painel_module_groups']
            for item in group['items']
        ]
        self.assertIn('Produtos', labels)
        self.client.force_login(self.user)
        response = self.client.get(reverse('painel:dashboard'))
        self.assertContains(response, 'Produtos')

    def test_user_without_access_is_blocked_by_backend(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('painel:produtos_lista')).status_code, 403)

    def test_company_selector_is_scoped_and_fixed_context_cannot_be_tampered(self):
        form = ProdutoForm(user=self.user)
        self.assertIn(self.company, form.fields['empresa_proprietaria'].queryset)
        self.assertNotIn(self.other_company, form.fields['empresa_proprietaria'].queryset)
        fixed = ProdutoForm(user=self.user, fixed_company=self.company)
        self.assertTrue(fixed.fields['empresa_proprietaria'].disabled)
        self.assertTrue(fixed.fields['titular_tipo'].disabled)

    def test_personal_and_company_limits_are_separate(self):
        self.product()
        personal = calcular_limite(self.user, Produto.TitularTipo.PESSOA_FISICA)
        company = calcular_limite(self.user, Produto.TitularTipo.EMPRESA, self.company)
        self.assertEqual(personal.utilizado, 1)
        self.assertEqual(company.utilizado, 0)
        self.assertEqual(personal.efetivo, 4)
        self.assertEqual(company.efetivo, 10)

    def test_company_product_requires_enterprise_edit_permission(self):
        product = self.product(
            titular_tipo=Produto.TitularTipo.EMPRESA,
            empresa_proprietaria=self.company,
        )
        self.assertFalse(pode_editar(self.user, product))
        PerfilPermissao.objects.create(
            perfil=self.profile, permissao=self.permissions['products.editar_empresa'],
        )
        self.assertTrue(pode_editar(self.user, product))

    def test_unrelated_or_inactive_company_is_rejected(self):
        with self.assertRaises(PermissionDenied):
            validar_contexto(self.user, Produto.TitularTipo.EMPRESA, self.other_company)
        self.company.status = Empresa.Status.SUSPENSA
        self.company.save(update_fields=['status'])
        with self.assertRaises(Exception):
            validar_contexto(self.user, Produto.TitularTipo.EMPRESA, self.company)

    def test_only_public_company_products_appear_on_public_profile(self):
        capability, _ = Capacidade.objects.get_or_create(
            codigo='VENDER_PRODUTOS', defaults={'nome': 'Vender produtos'},
        )
        EmpresaCapacidade.objects.create(
            empresa=self.company, capacidade=capability,
            status=EmpresaCapacidade.Status.APROVADA, ativo=True,
        )
        published = self.product(
            nome='Produto público empresa', titular_tipo=Produto.TitularTipo.EMPRESA,
            empresa_proprietaria=self.company, status=Produto.Status.PUBLICADO,
        )
        self.product(
            nome='Rascunho empresa', titular_tipo=Produto.TitularTipo.EMPRESA,
            empresa_proprietaria=self.company,
        )
        response = self.client.get(reverse('publico:empresa', args=[self.company.slug]))
        self.assertContains(response, published.nome)
        self.assertNotContains(response, 'Rascunho empresa')
        self.assertNotContains(response, 'CPF')
