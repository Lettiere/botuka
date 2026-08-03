from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import ProdutoVideoFormSet, youtube_id
from .models import Produto, ProdutoVideo
from .services import gerar_codigo_interno, normalizar_whatsapp, whatsapp_produto


class ProductFormWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username='product-form-admin', email='form@example.com', password='safe-password',
        )
        cls.user.first_name = 'Pessoa'
        cls.user.cpf = '52998224725'
        cls.user.telefone = '(14) 99999-9999'
        cls.user.save()

    def product(self, **overrides):
        values = {
            'nome': 'Produto fluxo', 'categoria': 'Legado',
            'descricao_curta': 'Descrição curta', 'descricao_completa': '<p>Descrição</p>',
            'preco': Decimal('10.00'), 'titular_tipo': Produto.TitularTipo.PESSOA_FISICA,
            'criador_registro': self.user, 'proprietario': self.user, 'responsavel': self.user,
        }
        values.update(overrides)
        return Produto.objects.create(**values)

    def test_form_has_exactly_seven_steps_and_dynamic_video_formset(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('painel:produto_criar'))
        self.assertEqual(response.status_code, 200)
        for title in (
            'Identificação', 'Taxonomia', 'Características e atributos',
            'Preços e estoque', 'Publicação e revisão',
            'Imagens e vídeos', 'Conferência do produto',
        ):
            self.assertContains(response, title)
        self.assertContains(response, 'Conferência do produto')
        self.assertContains(response, 'id_videos-TOTAL_FORMS')
        self.assertNotContains(response, 'name="videos_youtube"')

    def test_internal_code_is_unique_and_does_not_change_on_edit(self):
        first = self.product()
        first.codigo_interno = gerar_codigo_interno(first)
        first.save()
        original = first.codigo_interno
        first.nome = 'Nome editado'
        first.save()
        self.assertEqual(first.codigo_interno, original)
        second = self.product()
        second.codigo_interno = gerar_codigo_interno(second)
        second.save()
        self.assertNotEqual(first.codigo_interno, second.codigo_interno)
        self.assertTrue(first.codigo_interno.startswith('BOT-PESSOA-4725-'))

    def test_company_code_exposes_only_document_suffix(self):
        company = SimpleNamespace(pk=22, nome_fantasia='Aleicah Comércio', cpf_cnpj='12345678000199')
        product = SimpleNamespace(
            pk=23, codigo_interno='', empresa_proprietaria=company,
            proprietario=self.user,
        )
        code = gerar_codigo_interno(product)
        self.assertIn('ALEICAHCOMER', code)
        self.assertIn('-0199-', code)
        self.assertNotIn('12345678000199', code)

    def test_whatsapp_normalization_and_public_url(self):
        self.assertEqual(normalizar_whatsapp('(14) 99999-9999'), '5514999999999')
        self.assertEqual(normalizar_whatsapp('55 14 99999-9999'), '5514999999999')
        product = self.product(whatsapp='')
        result = whatsapp_produto(product)
        self.assertEqual(result['numero'], '5514999999999')
        self.assertTrue(result['url'].startswith('https://wa.me/5514999999999?text='))
        self.assertIn('%E2%80%9CProduto%20fluxo%E2%80%9D', result['url'])

    def test_youtube_live_is_supported(self):
        self.assertEqual(youtube_id('https://youtube.com/live/abc_DEF-123'), 'abc_DEF-123')

    def test_video_formset_saves_caption_order_and_rejects_duplicate(self):
        product = self.product()
        data = {
            'videos-TOTAL_FORMS': '2', 'videos-INITIAL_FORMS': '0',
            'videos-MIN_NUM_FORMS': '0', 'videos-MAX_NUM_FORMS': '8',
            'videos-0-url': 'https://youtu.be/abc123', 'videos-0-titulo': 'Apresentação', 'videos-0-ordem': '2',
            'videos-1-url': 'https://youtube.com/watch?v=abc123', 'videos-1-titulo': '', 'videos-1-ordem': '1',
        }
        formset = ProdutoVideoFormSet(data, instance=product, prefix='videos')
        self.assertFalse(formset.is_valid())
        self.assertIn('Não repita', str(formset.non_form_errors()))
        data['videos-1-url'] = 'https://youtube.com/shorts/xyz789'
        formset = ProdutoVideoFormSet(data, instance=product, prefix='videos')
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertEqual(ProdutoVideo.objects.filter(produto=product).count(), 2)
        self.assertEqual(product.videos.get(youtube_id='abc123').titulo, 'Apresentação')
