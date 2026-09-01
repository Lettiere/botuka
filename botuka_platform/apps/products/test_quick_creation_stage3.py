from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.core.models import Perfil, PerfilPermissao, Permissao
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Capacidade, Empresa, EmpresaCapacidade

from .forms import ProdutoForm, ProdutoRapidoForm
from .models import CategoriaProduto, Produto
from .public_catalog import produtos_publicos


class ProdutoCadastroRapidoStage3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user('produto-stage3', password='safe-password')
        cls.other = User.objects.create_user('produto-stage3-other', password='safe-password')
        profile = Perfil.objects.create(nome='PRODUTOS STAGE 3')
        cls.user.perfil = profile
        cls.user.save(update_fields=['perfil'])
        for code in (
            'products.acessar', 'products.visualizar', 'products.criar_proprio',
            'products.criar_empresa', 'products.editar_proprios', 'products.editar_empresa',
            'products.publicar',
        ):
            PerfilPermissao.objects.create(
                perfil=profile, permissao=Permissao.objects.get(codigo=code),
            )
        country = Pais.objects.create(nome='Brasil Stage 3', codigo_iso_2='S3', codigo_iso_3='ST3')
        state = Estado.objects.create(pais=country, nome='Estado Stage 3', sigla='S3')
        city = Cidade.objects.create(estado=state, nome='Cidade Stage 3')
        base = {
            'cidade': city, 'estado': state, 'status': Empresa.Status.ATIVA,
            'ativo': True, 'perfil_publico': True,
        }
        cls.comercio = Empresa.objects.create(
            usuario_proprietario=cls.user, nome_fantasia='Comércio Stage 3',
            razao_social='Comércio Stage 3 Ltda', cpf_cnpj='11222333000181',
            email='comercio-stage3@example.com', cep='18600000',
            endereco='Rua Stage 3', numero='10', bairro='Centro',
            atuacao=Empresa.Atuacao.COMERCIO,
            modalidade_comercial=Empresa.ModalidadeComercial.VAREJO, **base,
        )
        cls.mista = Empresa.objects.create(
            usuario_proprietario=cls.user, nome_fantasia='Mista Stage 3',
            atuacao=Empresa.Atuacao.COMERCIO_E_SERVICOS,
            modalidade_comercial=Empresa.ModalidadeComercial.VAREJO, **base,
        )
        cls.servicos = Empresa.objects.create(
            usuario_proprietario=cls.user, nome_fantasia='Serviços Stage 3',
            atuacao=Empresa.Atuacao.SERVICOS, **base,
        )
        cls.foreign = Empresa.objects.create(
            usuario_proprietario=cls.other, nome_fantasia='Empresa alheia Stage 3',
            atuacao=Empresa.Atuacao.COMERCIO,
            modalidade_comercial=Empresa.ModalidadeComercial.VAREJO, **base,
        )
        cls.category = CategoriaProduto.objects.create(nome='Categoria Stage 3', slug='categoria-stage-3')

    def setUp(self):
        self.client.force_login(self.user)

    def payload(self, company=None, **changes):
        data = {
            'titular_tipo': Produto.TitularTipo.EMPRESA if company else Produto.TitularTipo.PESSOA_FISICA,
            'empresa_proprietaria': company.pk if company else '',
            'nome': 'Produto mínimo Stage 3',
            'categoria_taxonomia': self.category.pk,
            'descricao_curta': 'Descrição real informada pelo usuário.',
            'preco': '29.90',
            'preco_sob_consulta': '',
            'estoque_informativo': '',
            'acao': 'rascunho',
        }
        data.update(changes)
        return data

    def test_quick_form_has_nine_fields_and_complete_form_remains_available(self):
        self.assertEqual(len(ProdutoRapidoForm(user=self.user).visible_fields()), 9)
        self.assertGreater(len(ProdutoForm(user=self.user).visible_fields()), 9)
        response = self.client.get(reverse('painel:produto_criar'))
        self.assertContains(response, 'Salvar rascunho')
        self.assertNotContains(response, 'SEO')
        self.assertNotContains(response, 'Vídeos do YouTube')

    def test_comercio_and_mista_create_draft_without_capability(self):
        for company in (self.comercio, self.mista):
            response = self.client.post(
                reverse('painel:empresa_produto_criar', args=[company.uuid]),
                self.payload(company, nome=f'Rascunho {company.nome_fantasia}'),
            )
            self.assertEqual(response.status_code, 302)
            product = Produto.objects.get(nome=f'Rascunho {company.nome_fantasia}')
            self.assertEqual(product.status, Produto.Status.RASCUNHO)
            self.assertEqual(product.empresa_proprietaria, company)
            self.assertEqual(product.descricao_completa, product.descricao_curta)

    def test_servicos_is_blocked_contextually_and_in_generic_post(self):
        response = self.client.get(reverse('painel:empresa_produto_criar', args=[self.servicos.uuid]))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse('painel:produto_criar'), self.payload(self.servicos))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Produto.objects.filter(nome='Produto mínimo Stage 3').exists())

    def test_personal_product_remains_supported_and_draft_is_not_public(self):
        response = self.client.post(reverse('painel:produto_criar'), self.payload())
        self.assertEqual(response.status_code, 302)
        product = Produto.objects.get(nome='Produto mínimo Stage 3')
        self.assertEqual(product.titular_tipo, Produto.TitularTipo.PESSOA_FISICA)
        self.assertEqual(product.status, Produto.Status.RASCUNHO)
        self.assertFalse(produtos_publicos().filter(pk=product.pk).exists())
        self.assertEqual(self.client.get(product.get_absolute_url()).status_code, 404)

    def test_save_and_continue_have_distinct_safe_redirects(self):
        response = self.client.post(reverse('painel:produto_criar'), self.payload(nome='Salvar Stage 3'))
        saved = Produto.objects.get(nome='Salvar Stage 3')
        self.assertRedirects(response, reverse('painel:produto_detalhe', args=[saved.uuid]))
        response = self.client.post(
            reverse('painel:produto_criar'), self.payload(nome='Continuar Stage 3', acao='continuar'),
        )
        continued = Produto.objects.get(nome='Continuar Stage 3')
        self.assertRedirects(response, reverse('painel:produto_editar', args=[continued.uuid]))
        edit = self.client.get(reverse('painel:produto_editar', args=[continued.uuid]))
        self.assertContains(edit, 'Características e atributos')
        self.assertEqual(continued.status, Produto.Status.RASCUNHO)

    def test_price_consultation_negative_and_contradiction(self):
        response = self.client.post(
            reverse('painel:produto_criar'),
            self.payload(nome='Sob consulta Stage 3', preco='', preco_sob_consulta='on'),
        )
        self.assertEqual(response.status_code, 302)
        product = Produto.objects.get(nome='Sob consulta Stage 3')
        self.assertIsNone(product.preco)
        self.assertTrue(product.preco_sob_consulta)
        for data in (
            self.payload(nome='Negativo Stage 3', preco='-1'),
            self.payload(nome='Contraditório Stage 3', preco='10', preco_sob_consulta='on'),
        ):
            response = self.client.post(reverse('painel:produto_criar'), data)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(Produto.objects.filter(nome=data['nome']).exists())

    def test_invalid_taxonomy_is_rejected(self):
        response = self.client.post(
            reverse('painel:produto_criar'), self.payload(categoria_taxonomia='999999999'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Produto.objects.filter(nome='Produto mínimo Stage 3').exists())

    def test_optional_stock_and_existing_image_pipeline(self):
        buffer = BytesIO()
        Image.new('RGB', (32, 32), color='blue').save(buffer, format='PNG')
        png = SimpleUploadedFile('produto.png', buffer.getvalue(), content_type='image/png')
        data = self.payload(nome='Imagem Stage 3', estoque_informativo='7')
        data['imagem_principal_upload'] = png
        response = self.client.post(reverse('painel:produto_criar'), data)
        self.assertEqual(response.status_code, 302)
        product = Produto.objects.get(nome='Imagem Stage 3')
        self.assertEqual(product.estoque_informativo, 7)
        self.assertEqual(product.imagens.filter(principal=True).count(), 1)

    def test_context_company_cannot_be_changed_by_post(self):
        response = self.client.post(
            reverse('painel:empresa_produto_criar', args=[self.comercio.uuid]),
            self.payload(self.mista, nome='Contexto protegido Stage 3'),
        )
        self.assertEqual(response.status_code, 302)
        product = Produto.objects.get(nome='Contexto protegido Stage 3')
        self.assertEqual(product.empresa_proprietaria, self.comercio)

    def test_foreign_company_is_blocked_by_url_and_post(self):
        self.assertEqual(
            self.client.get(reverse('painel:empresa_produto_criar', args=[self.foreign.uuid])).status_code,
            404,
        )
        response = self.client.post(reverse('painel:produto_criar'), self.payload(self.foreign))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Produto.objects.filter(nome='Produto mínimo Stage 3').exists())

    def test_publication_requires_approved_capability(self):
        product = Produto.objects.create(
            nome='Publicação Stage 3', categoria=self.category.nome,
            categoria_taxonomia=self.category, descricao_curta='Descrição',
            descricao_completa='Descrição completa', preco=Decimal('10'),
            titular_tipo=Produto.TitularTipo.EMPRESA,
            empresa_proprietaria=self.comercio, criador_registro=self.user,
            proprietario=self.user, responsavel=self.user,
            status=Produto.Status.APROVADO,
        )
        url = reverse('painel:produto_status', args=[product.uuid])
        self.client.post(url, {'status': Produto.Status.PUBLICADO})
        product.refresh_from_db()
        self.assertEqual(product.status, Produto.Status.APROVADO)
        self.assertFalse(self.comercio.pode_publicar_produto)
        self.assertTrue(self.comercio.pode_criar_rascunho_produto)

        capability, _ = Capacidade.objects.get_or_create(
            codigo='VENDER_PRODUTOS', defaults={'nome': 'Vender produtos'},
        )
        EmpresaCapacidade.objects.create(
            empresa=self.comercio, capacidade=capability,
            status=EmpresaCapacidade.Status.APROVADA, ativo=True,
        )
        self.client.post(url, {'status': Produto.Status.PUBLICADO})
        product.refresh_from_db()
        self.assertEqual(product.status, Produto.Status.PUBLICADO)
        self.assertTrue(self.comercio.pode_publicar_produto)

    def test_plan_limit_remains_enforced(self):
        for index in range(10):
            Produto.objects.create(
                nome=f'Limite Stage 3 {index}', categoria=self.category.nome,
                categoria_taxonomia=self.category, descricao_curta='Descrição',
                descricao_completa='Descrição', preco=Decimal('10'),
                titular_tipo=Produto.TitularTipo.EMPRESA,
                empresa_proprietaria=self.comercio, criador_registro=self.user,
                proprietario=self.user, responsavel=self.user,
            )
        response = self.client.post(reverse('painel:produto_criar'), self.payload(self.comercio))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Produto.objects.filter(nome='Produto mínimo Stage 3').exists())