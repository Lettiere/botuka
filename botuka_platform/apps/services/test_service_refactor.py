import base64

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.master_services import garantir_usuario_master
from apps.core.services.contacts import telefone_para_whatsapp
from apps.core.services.public_sharing import obter_url_publica
from apps.core.services.rich_text import sanitizar_html_rico
from apps.services.models import (
    AreaProfissional, FormaCobranca, Profissao, ProfissaoTipoServico,
    Servico, ServicoImagem, Setor, TipoServico,
)


class ServiceHelpersTests(SimpleTestCase):
    def test_html_rico_preserva_formatacao_e_remove_perigo(self):
        result = sanitizar_html_rico(
            '<h2>Título</h2><p onclick="x()"><strong>Seguro</strong></p><script>alert(1)</script>'
        )
        self.assertEqual(result, '<h2>Título</h2><p><strong>Seguro</strong></p>')

    def test_whatsapp_normaliza_e_adiciona_mensagem(self):
        url = telefone_para_whatsapp(
            '(14) 99876-5432',
            'Olá! Encontrei o serviço Jardinagem na plataforma BOTUKA.',
        )
        self.assertTrue(url.startswith('https://wa.me/5514998765432?text='))
        self.assertNotIn(' ', url)


@override_settings(PUBLIC_BASE_URL='https://botuka.com.br')
class ServicePanelRefactorTests(TestCase):
    png = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
    )

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('service-owner', password='senha')
        cls.setor = Setor.objects.create(nome='Casa')
        cls.area = AreaProfissional.objects.create(setor=cls.setor, nome='Manutenção residencial')
        cls.profissao = Profissao.objects.create(setor=cls.setor, area=cls.area, nome='Prestador')
        cls.tipo = TipoServico.objects.create(nome='Manutenção')
        ProfissaoTipoServico.objects.create(profissao=cls.profissao, tipo_servico=cls.tipo)
        cls.cobranca = FormaCobranca.objects.create(nome='Por serviço')
        cls.servico = Servico.objects.create(
            usuario_responsavel=cls.owner,
            prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA,
            setor=cls.setor,
            area=cls.area,
            profissao=cls.profissao,
            tipo_servico=cls.tipo,
            forma_cobranca=cls.cobranca,
            titulo='Manutenção residencial',
            descricao_completa='<p>Descrição inicial</p>',
            atendimento_presencial=True,
            status=Servico.Status.PUBLICADO,
            publicado_em=timezone.now(),
        )

    def payload(self, **changes):
        data = {
            'prestador_tipo': Servico.PrestadorTipo.PESSOA_FISICA,
            'empresa': '', 'setor': self.setor.pk, 'area': self.area.pk,
            'profissao': self.profissao.pk, 'tipo_servico': self.tipo.pk,
            'forma_cobranca': self.cobranca.pk, 'titulo': self.servico.titulo,
            'descricao_curta': 'Atendimento residencial',
            'descricao_completa': '<h2>Serviço</h2><p><strong>Completo</strong><script>x()</script></p>',
            'experiencia': '<p>Dez anos.</p>', 'preco_inicial': '100.00',
            'preco_final': '200.00', 'unidade_preco': 'serviço',
            'atendimento_presencial': 'on', 'prazo_medio': '2 dias',
            'telefone_publico': '', 'whatsapp_publico': '(14) 99876-5432',
            'email_publico': '', 'acao': 'salvar',
        }
        data.update(changes)
        return data

    def test_listagem_e_editor_compartilhado(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('painel:servicos_lista')), 'Manutenção residencial')
        cadastro = self.client.get(reverse('painel:servico_criar'))
        self.assertNotContains(cadastro, 'data-richtext-editor')
        self.assertContains(cadastro, 'Continuar configuração')
        self.assertContains(
            self.client.get(reverse('painel:servico_editar', args=[self.servico.uuid])),
            'data-richtext-editor',
        )

    def test_edicao_sanitiza_e_master_nao_assume_propriedade(self):
        master, _ = garantir_usuario_master(email='master-service-refactor@example.com', senha='Senha#2026')
        self.client.force_login(master)
        response = self.client.post(
            reverse('painel:servico_editar', args=[self.servico.uuid]),
            self.payload(),
        )
        self.assertEqual(response.status_code, 302)
        self.servico.refresh_from_db()
        self.assertEqual(self.servico.usuario_responsavel, self.owner)
        self.assertIn('<strong>Completo</strong>', self.servico.descricao_completa)
        self.assertNotIn('<script', self.servico.descricao_completa)

    def test_substitui_e_remove_imagem_logicamente(self):
        antiga = ServicoImagem.objects.create(
            servico=self.servico,
            imagem=SimpleUploadedFile('antiga.png', self.png, content_type='image/png'),
            principal=True,
        )
        self.client.force_login(self.owner)
        payload = self.payload(remover_imagem=str(antiga.uuid))
        payload['imagem_capa'] = SimpleUploadedFile('nova.png', self.png, content_type='image/png')
        response = self.client.post(
            reverse('painel:servico_editar', args=[self.servico.uuid]),
            payload,
        )
        self.assertEqual(response.status_code, 302)
        antiga.refresh_from_db()
        self.assertFalse(antiga.ativo)
        self.assertIsNotNone(antiga.excluido_em)
        self.assertTrue(ServicoImagem.objects.filter(servico=self.servico, principal=True, ativo=True).exists())

    def test_publico_whatsapp_url_e_url_canonica(self):
        self.servico.whatsapp_publico = '(14) 99876-5432'
        self.servico.save()
        response = self.client.get(self.servico.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'https://wa.me/5514998765432?text=')
        self.assertNotContains(response, '127.0.0.1')
        self.assertEqual(
            obter_url_publica(self.servico),
            f'https://botuka.com.br/servicos/{self.servico.slug}/',
        )
