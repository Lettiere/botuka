from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from .forms import ProdutoForm
from .models import (
    AtributoProduto, AuditoriaProduto, CategoriaProduto, FamiliaProduto, Produto, TipoProduto,
    ValorAtributoProduto,
)
from .services import validar_transicao_status, whatsapp_produto


class ProductCreationAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            'product-audit-master', 'product-audit@example.com', 'safe-password',
        )
        cls.common = get_user_model().objects.create_user(
            'product-audit-common', 'product-common@example.com', 'safe-password',
        )
        cls.common.telefone = '(14) 99999-9999'
        cls.common.save(update_fields=['telefone'])
        cls.category = CategoriaProduto.objects.create(nome='Auditável', slug='auditavel')
        cls.other_category = CategoriaProduto.objects.create(nome='Outra auditoria', slug='outra-auditoria')
        cls.family = FamiliaProduto.objects.create(
            categoria=cls.category, nome='Família auditável', slug='familia-auditavel',
        )
        cls.product_type = TipoProduto.objects.create(
            familia=cls.family, nome='Tipo auditável', slug='tipo-auditavel',
        )
        cls.attribute = AtributoProduto.objects.create(
            categoria_taxonomia=cls.category, nome='Voltagem', chave='voltagem',
            tipo=AtributoProduto.Tipo.ESCOLHA, opcoes=['110V', '220V'], obrigatorio=True,
        )
        cls.foreign_attribute = AtributoProduto.objects.create(
            categoria_taxonomia=cls.other_category, nome='Incompatível', chave='incompativel',
        )

    def payload(self, **changes):
        data = {
            'nome': 'Produto criado integralmente',
            'titular_tipo': Produto.TitularTipo.PESSOA_FISICA,
            'empresa_proprietaria': '',
            'descricao_curta': 'Descrição curta suficiente.',
            'descricao_completa': '<p>Descrição <script>alert(1)</script> segura.</p>',
            'categoria_taxonomia': self.category.pk,
            'familia': self.family.pk,
            'tipo_produto': self.product_type.pk,
            'segmento': '',
            'condicao': Produto.Condicao.NOVO,
            'preco': '19,90', 'preco_promocional': '9.90',
            'moeda': 'BRL', 'preco_sob_consulta': '',
            'unidade_venda': 'unidade', 'quantidade_minima': '1',
            'estoque_informativo': '2',
            'disponibilidade': Produto.Disponibilidade.DISPONIVEL,
            'publico': 'on',
            f'atributo_{self.attribute.pk}': '220V',
            'videos-TOTAL_FORMS': '0', 'videos-INITIAL_FORMS': '0',
            'videos-MIN_NUM_FORMS': '0', 'videos-MAX_NUM_FORMS': '8',
        }
        data.update(changes)
        return data

    def test_route_auth_assets_and_responsive_wizard_contract(self):
        url = reverse('painel:produto_criar')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/conta/login/', response['Location'])
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'painel/css/produtos_form.css')
        self.assertContains(response, 'painel/js/produtos_form.js')
        self.assertContains(response, 'data-attributes-url')
        self.assertContains(response, 'data-dynamic-attributes')
        self.assertContains(response, 'defer')

    def test_valid_creation_persists_attribute_and_sanitizes_atomically(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('painel:produto_criar'), self.payload())
        self.assertEqual(response.status_code, 302)
        product = Produto.objects.get(nome='Produto criado integralmente')
        self.assertEqual(product.preco, Decimal('19.90'))
        self.assertNotIn('<script', product.descricao_completa)
        self.assertEqual(
            ValorAtributoProduto.objects.get(produto=product, atributo=self.attribute).valor,
            '220V',
        )
        self.assertEqual(product.status, Produto.Status.RASCUNHO)
        self.assertTrue(product.codigo_interno)

    def test_foreign_attribute_and_fake_image_leave_no_partial_product(self):
        self.client.force_login(self.user)
        data = self.payload(**{f'atributo_{self.foreign_attribute.pk}': 'ataque'})
        response = self.client.post(reverse('painel:produto_criar'), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'atributos incompatíveis')
        self.assertFalse(Produto.objects.filter(nome=data['nome']).exists())

        fake = SimpleUploadedFile('falsa.png', b'not an image', content_type='image/png')
        data = self.payload(nome='Produto com imagem falsa', galeria_upload=fake)
        response = self.client.post(reverse('painel:produto_criar'), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Produto.objects.filter(nome='Produto com imagem falsa').exists())

    def test_price_and_stock_coherence_are_backend_validated(self):
        form = ProdutoForm(data=self.payload(preco='-1'), user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('preco', form.errors)
        form = ProdutoForm(data=self.payload(
            disponibilidade=Produto.Disponibilidade.ESGOTADO,
            estoque_informativo='3',
        ), user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('estoque_informativo', form.errors)

    def test_workflow_rejects_status_jump_and_requires_rejection_reason(self):
        product = Produto(
            nome='Workflow seguro', categoria='Auditável', descricao_curta='Descrição',
            descricao_completa='Descrição', preco=Decimal('10'),
            titular_tipo=Produto.TitularTipo.PESSOA_FISICA,
            criador_registro=self.user, proprietario=self.user, responsavel=self.user,
        )
        with self.assertRaisesMessage(ValidationError, 'Não é permitido'):
            validar_transicao_status(product, Produto.Status.PUBLICADO)
        product.status = Produto.Status.EM_ANALISE
        with self.assertRaisesMessage(ValidationError, 'motivo da rejeição'):
            validar_transicao_status(product, Produto.Status.REJEITADO)

    def test_status_endpoint_records_approval_and_rejection_audit(self):
        product = Produto.objects.create(
            nome='Workflow persistido', categoria='Auditável', descricao_curta='Descrição',
            descricao_completa='Descrição', preco=Decimal('10'),
            titular_tipo=Produto.TitularTipo.PESSOA_FISICA,
            criador_registro=self.user, proprietario=self.user, responsavel=self.user,
        )
        self.client.force_login(self.user)
        url = reverse('painel:produto_status', args=[product.uuid])
        self.client.post(url, {'status': Produto.Status.PUBLICADO})
        product.refresh_from_db()
        self.assertEqual(product.status, Produto.Status.RASCUNHO)
        self.client.post(url, {'status': Produto.Status.EM_ANALISE})
        self.client.post(url, {'status': Produto.Status.APROVADO})
        product.refresh_from_db()
        self.assertEqual(product.aprovado_por, self.user)
        self.assertIsNotNone(product.aprovado_em)
        self.client.post(url, {
            'status': Produto.Status.REJEITADO,
            'motivo_rejeicao': 'Documentação insuficiente.',
        })
        product.refresh_from_db()
        self.assertEqual(product.status, Produto.Status.REJEITADO)
        self.assertEqual(product.motivo_rejeicao, 'Documentação insuficiente.')
        self.assertEqual(AuditoriaProduto.objects.filter(produto=product, acao='STATUS').count(), 3)

    def test_personal_product_does_not_expose_private_phone_without_permission(self):
        product = Produto(
            nome='Contato privado', titular_tipo=Produto.TitularTipo.PESSOA_FISICA,
            responsavel=self.common,
        )
        self.assertEqual(whatsapp_produto(product), {'numero': '', 'url': ''})

    def test_csrf_is_required_for_creation(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(
            client.post(reverse('painel:produto_criar'), self.payload()).status_code,
            403,
        )
