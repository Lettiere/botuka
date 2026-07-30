from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from apps.core.seo.page_builders import product_seo

from .models import CategoriaProduto, SetorProduto, Produto
from .negotiation import iniciar_conversa, seller_verification_service
from .services import calcular_limite
from .forms import youtube_id


class ProdutoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='produto_teste', email='produto@example.com', password='safe-test-password',
        )

    def product(self, **overrides):
        values = {
            'nome': 'Produto local', 'categoria': 'Artesanato',
            'descricao_curta': 'Produto artesanal feito em Botucatu.',
            'descricao_completa': '<p>Descrição <strong>segura</strong>.</p>',
            'preco': Decimal('25.00'), 'titular_tipo': Produto.TitularTipo.PESSOA_FISICA,
            'criador_registro': self.user, 'proprietario': self.user, 'responsavel': self.user,
        }
        values.update(overrides)
        return Produto.objects.create(**values)

    def test_limite_padrao_pessoa_fisica_e_quatro(self):
        result = calcular_limite(self.user, Produto.TitularTipo.PESSOA_FISICA)
        self.assertEqual(result.efetivo, 4)
        self.assertEqual(result.utilizado, 0)

    def test_html_perigoso_e_sanitizado(self):
        item = self.product(descricao_completa='<p>Ok</p><script>alert(1)</script>')
        self.assertNotIn('<script', item.descricao_completa)

    def test_publico_exige_status_publicado(self):
        item = self.product()
        self.assertEqual(self.client.get(item.get_absolute_url()).status_code, 404)
        item.status = Produto.Status.PUBLICADO
        item.publicado_em = item.criado_em
        item.save()
        self.assertEqual(self.client.get(item.get_absolute_url()).status_code, 200)

    def test_seo_product_e_breadcrumb_validos(self):
        item = self.product(status=Produto.Status.PUBLICADO)
        request = RequestFactory().get(item.get_absolute_url(), secure=True, HTTP_HOST='botuka.com.br')
        seo = product_seo(request, item)
        self.assertEqual(seo['canonical_url'], f'https://botuka.com.br{item.get_absolute_url()}')
        schemas = seo['schema']['@graph']
        self.assertTrue(any(schema.get('@type') == 'Product' for schema in schemas))
        self.assertTrue(any(schema.get('@type') == 'BreadcrumbList' for schema in schemas))

    def test_slug_e_unico(self):
        first = self.product()
        second = self.product()
        self.assertNotEqual(first.slug, second.slug)

    def test_links_youtube_aceitos_e_outros_hosts_rejeitados(self):
        self.assertEqual(youtube_id('https://youtu.be/abc_DEF-123'), 'abc_DEF-123')
        self.assertEqual(
            youtube_id('https://www.youtube.com/watch?v=abc_DEF-123'),
            'abc_DEF-123',
        )
        with self.assertRaises(ValidationError):
            youtube_id('https://example.com/video')

    def test_taxonomia_incompativel_e_rejeitada_no_backend(self):
        tecnologia = SetorProduto.objects.create(nome='Tecnologia teste', slug='tecnologia-teste')
        casa = SetorProduto.objects.create(nome='Casa teste', slug='casa-teste')
        celulares = CategoriaProduto.objects.create(setor=tecnologia, nome='Celulares teste', slug='celulares-teste')
        with self.assertRaises(ValidationError):
            self.product(setor=casa, categoria_taxonomia=celulares)

    def test_conversa_pf_valida_participantes_e_registra_verificacao(self):
        buyer = get_user_model().objects.create_user(username='comprador_teste', password='safe-test-password')
        product = self.product(status=Produto.Status.PUBLICADO)
        conversation = iniciar_conversa(product=product, buyer=buyer, initial_message='Tenho interesse.')
        self.assertEqual(conversation.comprador, buyer)
        self.assertEqual(conversation.mensagens.count(), 1)
        self.assertTrue(product.verificacoes_vendedor.filter(permitido=True, codigo='OK').exists())

    def test_vendedor_nao_pode_conversar_consigo(self):
        product = self.product(status=Produto.Status.PUBLICADO)
        result = seller_verification_service.can_start_conversation(
            seller=self.user, product=product, buyer=self.user,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, 'SELF_CONVERSATION')
