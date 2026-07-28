from unittest.mock import patch
import uuid

from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.organizations.models import Empresa
from apps.recruitment.models import Vaga
from apps.services.models import Servico

from .services.contacts import (
    formatar_telefone, normalizar_telefone, telefone_eh_celular,
    telefone_para_whatsapp,
)
from .services.public_sharing import (
    gerar_qrcode_png, gerar_qrcode_svg, obter_dados_compartilhamento,
    obter_url_publica,
)


@override_settings(PUBLIC_BASE_URL='https://botuka.com.br', DEBUG=False)
class PublicSharingTests(SimpleTestCase):
    def company(self, **kwargs):
        defaults = dict(
            uuid=uuid.uuid4(), slug='empresa-publica', nome_fantasia='Empresa Pública',
            status=Empresa.Status.ATIVA, perfil_publico=True, ativo=True,
            excluido_em=None,
        )
        defaults.update(kwargs)
        return Empresa(**defaults)

    def service(self, **kwargs):
        defaults = dict(
            uuid=uuid.uuid4(), slug='servico-publico', titulo='Serviço Público',
            status=Servico.Status.PUBLICADO, publicado_em=__import__('django.utils.timezone', fromlist=['now']).now(),
            ativo=True, excluido_em=None,
        )
        defaults.update(kwargs)
        return Servico(**defaults)

    def job(self):
        return Vaga(
            uuid=uuid.uuid4(), slug='vaga-publica', titulo='Vaga Pública',
            status=Vaga.Status.PUBLICADA,
            publicado_em=__import__('django.utils.timezone', fromlist=['now']).now(),
            ativo=True, excluido_em=None, cidade='Botucatu',
        )

    def test_urls_canonicas_e_host_fixo(self):
        self.assertEqual(obter_url_publica(self.company()), 'https://botuka.com.br/empresas/empresa-publica/')
        request = RequestFactory().get('/', HTTP_HOST='evil.example')
        self.assertNotIn('evil.example', obter_url_publica(self.service(), request))

    def test_privado_suspenso_ou_excluido_e_bloqueado(self):
        for obj in (
            self.company(perfil_publico=False),
            self.company(status=Empresa.Status.SUSPENSA),
            self.company(excluido_em=__import__('django.utils.timezone', fromlist=['now']).now()),
        ):
            with self.assertRaises(Exception):
                obter_url_publica(obj)

    def test_png_svg_e_conteudo_recebem_somente_url(self):
        company = self.company()
        with patch('apps.core.services.public_sharing.qrcode.QRCode.add_data') as add_data:
            gerar_qrcode_png(company)
            add_data.assert_called_once_with('https://botuka.com.br/empresas/empresa-publica/')
        self.assertIn(b'<svg', gerar_qrcode_svg(company))

    def test_textos_de_vaga_e_servico(self):
        self.assertIn('Confira esta oportunidade', obter_dados_compartilhamento(self.job())['texto'])
        self.assertIn('Conheça o serviço', obter_dados_compartilhamento(self.service())['texto'])


class ContactServiceTests(SimpleTestCase):
    def test_celular_brasileiro(self):
        self.assertEqual(normalizar_telefone('(14) 99876-5432'), '5514998765432')
        self.assertEqual(formatar_telefone('5514998765432'), '(14) 99876-5432')
        self.assertTrue(telefone_eh_celular('5514998765432'))
        self.assertEqual(telefone_para_whatsapp('5514998765432'), 'https://wa.me/5514998765432')

    def test_fixo_vazio_invalido_e_internacional(self):
        self.assertFalse(telefone_eh_celular('1438123456'))
        self.assertEqual(telefone_para_whatsapp('1438123456'), '')
        self.assertEqual(normalizar_telefone(''), '')
        self.assertEqual(normalizar_telefone('123'), '')
        self.assertEqual(normalizar_telefone('+1 202 555 0198'), '12025550198')
