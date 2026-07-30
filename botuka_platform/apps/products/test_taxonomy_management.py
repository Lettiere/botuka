from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import (
    CategoriaProduto, FamiliaProduto, SegmentoProduto,
    TipoProduto, TipoProdutoSegmento,
)


class TaxonomyManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username='taxonomy-admin', email='taxonomy@example.com', password='test-pass-123',
        )
        cls.category = CategoriaProduto.objects.create(nome='Teste', slug='teste')
        cls.family = FamiliaProduto.objects.create(categoria=cls.category, nome='Família teste', slug='familia-teste')
        cls.type = TipoProduto.objects.create(familia=cls.family, nome='Tipo teste', slug='tipo-teste')
        cls.segment = SegmentoProduto.objects.create(nome='Público teste', slug='publico-teste')

    def setUp(self):
        self.client.force_login(self.user)

    def test_management_pages_load(self):
        urls = [
            reverse('gestao:taxonomia_produtos_dashboard'),
            reverse('gestao:taxonomia_categorias_lista'),
            reverse('gestao:taxonomia_familias_lista'),
            reverse('gestao:taxonomia_tipos_lista'),
            reverse('gestao:taxonomia_segmentos_lista'),
            reverse('gestao:taxonomia_categorias_detalhe', kwargs={'uuid': self.category.uuid}),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_dependent_apis_only_return_compatible_records(self):
        response = self.client.get(reverse('gestao:api_produtos_familias'), {'categoria': self.category.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['nome'], self.family.nome)
        response = self.client.get(reverse('gestao:api_produtos_tipos'), {'familia': self.family.pk})
        self.assertEqual(response.json()['results'][0]['nome'], self.type.nome)
        self.type.permite_segmento = True
        self.type.save()
        TipoProdutoSegmento.objects.create(tipo_produto=self.type, segmento=self.segment)
        response = self.client.get(reverse('gestao:api_produtos_segmentos'), {'tipo': self.type.pk})
        self.assertTrue(response.json()['permite_segmento'])
        self.assertEqual(response.json()['results'][0]['nome'], self.segment.nome)

    def test_type_cannot_require_disallowed_segment(self):
        self.type.permite_segmento = False
        self.type.exige_segmento = True
        with self.assertRaises(ValidationError):
            self.type.save()

    def test_status_change_uses_post(self):
        url = reverse('gestao:taxonomia_categorias_status', kwargs={'uuid': self.category.uuid})
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.category.refresh_from_db()
        self.assertFalse(self.category.ativo)

    def test_invalid_api_identifier_returns_clear_error(self):
        response = self.client.get(reverse('gestao:api_produtos_familias'), {'categoria': 'invalida'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Categoria inválida.')
