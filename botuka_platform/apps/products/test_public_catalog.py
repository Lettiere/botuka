from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Perfil, PerfilPermissao, Permissao

from .models import CategoriaProduto, FamiliaProduto, Produto, SegmentoProduto, TipoProduto
from .public_catalog import produtos_para_home, produtos_publicos


class PublicProductCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username='catalog-seller', password='safe-password', telefone='(14) 99999-9999',
        )
        profile = Perfil.objects.create(nome='VENDEDOR CATÁLOGO')
        cls.user.perfil = profile
        cls.user.save(update_fields=['perfil'])
        for code in ('products.acessar', 'products.oferecer_whatsapp'):
            PerfilPermissao.objects.create(
                perfil=profile, permissao=Permissao.objects.get(codigo=code),
            )
        cls.category = CategoriaProduto.objects.create(nome='Catálogo', slug='catalogo-publico')
        cls.family = FamiliaProduto.objects.create(categoria=cls.category, nome='Família catálogo', slug='familia-catalogo')
        cls.type = TipoProduto.objects.create(familia=cls.family, nome='Tipo catálogo', slug='tipo-catalogo')

    def product(self, **overrides):
        values = {
            'nome': 'Produto público', 'categoria': self.category.nome,
            'categoria_taxonomia': self.category, 'familia': self.family, 'tipo_produto': self.type,
            'descricao_curta': 'Produto disponível na loja.', 'descricao_completa': '<p>Descrição</p>',
            'preco': Decimal('20.00'), 'titular_tipo': Produto.TitularTipo.PESSOA_FISICA,
            'criador_registro': self.user, 'proprietario': self.user, 'responsavel': self.user,
            'status': Produto.Status.PUBLICADO, 'publicado_em': timezone.now(), 'publico': True,
        }
        values.update(overrides)
        return Produto.objects.create(**values)

    def test_store_only_lists_eligible_products(self):
        published = self.product()
        draft = self.product(nome='Produto rascunho', status=Produto.Status.RASCUNHO, publicado_em=None)
        response = self.client.get(reverse('products:loja'))
        self.assertContains(response, published.nome)
        self.assertNotContains(response, draft.nome)
        self.assertEqual(list(produtos_publicos().values_list('pk', flat=True)), [published.pk])

    def test_store_filters_by_real_taxonomy(self):
        published = self.product()
        response = self.client.get(reverse('products:loja'), {'categoria': self.category.uuid})
        self.assertContains(response, published.nome)
        response = self.client.get(reverse('products:loja'), {'categoria': '00000000-0000-0000-0000-000000000001'})
        self.assertNotContains(response, published.nome)

    def test_home_uses_only_highlighted_products_and_limits_eight(self):
        for index in range(9):
            self.product(nome=f'Destaque {index}', destaque=True)
        self.product(nome='Publicado sem destaque', destaque=False)
        results = produtos_para_home()
        self.assertEqual(len(results), 8)
        self.assertTrue(all(item.destaque for item in results))

    def test_public_detail_has_taxonomy_and_valid_whatsapp(self):
        published = self.product()
        response = self.client.get(published.get_absolute_url())
        self.assertContains(response, self.category.nome)
        self.assertContains(response, 'https://wa.me/5514999999999?text=')
        self.assertContains(response, 'noopener noreferrer')

    def test_taxonomy_loader_is_idempotent(self):
        call_command('carregar_taxonomia_produtos', verbosity=0)
        counts = (
            CategoriaProduto.objects.count(), FamiliaProduto.objects.count(),
            TipoProduto.objects.count(), SegmentoProduto.objects.count(),
        )
        call_command('carregar_taxonomia_produtos', verbosity=0)
        self.assertEqual(counts, (
            CategoriaProduto.objects.count(), FamiliaProduto.objects.count(),
            TipoProduto.objects.count(), SegmentoProduto.objects.count(),
        ))
