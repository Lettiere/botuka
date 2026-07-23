from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.core.public_links import TipoLink, normalizar_link_publico
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Empresa, EmpresaLink
from apps.services.models import FormaCobranca, Profissao, Servico, ServicoLink, Setor, TipoServico
from apps.accounts.master_services import garantir_usuario_master
from apps.services.permissions import servicos_disponiveis_para_usuario


class LinksQrCodeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.usuario = Usuario.objects.create_user('proprietario', 'proprietario@example.com', 'senha-forte')
        cls.terceiro = Usuario.objects.create_user('terceiro', 'terceiro@example.com', 'senha-forte')
        pais = Pais.objects.create(nome='Brasil', codigo_iso_2='BR', codigo_iso_3='BRA')
        estado = Estado.objects.create(pais=pais, nome='São Paulo', sigla='SP')
        cidade = Cidade.objects.create(estado=estado, nome='Botucatu')
        cls.empresa = Empresa.objects.create(
            usuario_proprietario=cls.usuario,
            nome_fantasia='Empresa Teste',
            cidade=cidade,
            estado=estado,
            status=Empresa.Status.ATIVA,
            perfil_publico=True,
        )
        setor = Setor.objects.create(nome='Tecnologia')
        profissao = Profissao.objects.create(setor=setor, nome='Desenvolvedor')
        tipo = TipoServico.objects.create(nome='Consultoria')
        cobranca = FormaCobranca.objects.create(nome='Por hora')
        cls.servico = Servico.objects.create(
            usuario_responsavel=cls.usuario,
            prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA,
            setor=setor,
            profissao=profissao,
            tipo_servico=tipo,
            forma_cobranca=cobranca,
            titulo='Consultoria em tecnologia',
            status=Servico.Status.PUBLICADO,
        )

    def dados_cadastro(self, **alteracoes):
        dados = {
            'prestador_tipo': Servico.PrestadorTipo.PESSOA_FISICA,
            'empresa': '', 'setor': self.servico.setor_id, 'profissao': self.servico.profissao_id,
            'tipo_servico': self.servico.tipo_servico_id, 'forma_cobranca': self.servico.forma_cobranca_id,
            'titulo': 'Novo serviço persistente', 'descricao_curta': 'Descrição curta',
            'descricao_completa': 'Descrição completa', 'experiencia': '', 'preco_inicial': '100.00',
            'preco_final': '200.00', 'unidade_preco': 'serviço', 'atendimento_presencial': 'on',
            'prazo_medio': '', 'telefone_publico': '', 'whatsapp_publico': '', 'email_publico': '',
            'acao': 'rascunho',
        }
        dados.update(alteracoes)
        return dados

    def test_cadastro_persistente_pf(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('painel:servico_criar'), self.dados_cadastro())
        self.assertEqual(resposta.status_code, 302)
        criado = Servico.objects.get(titulo='Novo serviço persistente')
        self.assertEqual(criado.usuario_responsavel, self.usuario)
        self.assertIsNone(criado.empresa_id)
        self.assertEqual(criado.status, Servico.Status.RASCUNHO)

    def test_gratuito_bloqueia_quarto_servico_no_backend(self):
        for indice in range(2):
            Servico.objects.create(
                usuario_responsavel=self.usuario,
                prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA,
                setor=self.servico.setor,
                profissao=self.servico.profissao,
                tipo_servico=self.servico.tipo_servico,
                forma_cobranca=self.servico.forma_cobranca,
                titulo=f'Serviço adicional {indice}',
            )
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('painel:servico_criar'), self.dados_cadastro())
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'limite de serviços')
        self.assertFalse(Servico.objects.filter(titulo='Novo serviço persistente').exists())

    def test_cadastro_persistente_pj(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('painel:servico_criar'), self.dados_cadastro(prestador_tipo=Servico.PrestadorTipo.EMPRESA, empresa=self.empresa.pk, acao='publicar'))
        self.assertEqual(resposta.status_code, 302)
        criado = Servico.objects.get(titulo='Novo serviço persistente')
        self.assertEqual(criado.empresa, self.empresa)
        self.assertEqual(criado.status, Servico.Status.PENDENTE)

    def test_empresa_de_terceiro_bloqueada_no_cadastro(self):
        self.client.force_login(self.terceiro)
        resposta = self.client.post(reverse('painel:servico_criar'), self.dados_cadastro(prestador_tipo=Servico.PrestadorTipo.EMPRESA, empresa=self.empresa.pk))
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Servico.objects.filter(titulo='Novo serviço persistente').exists())

    def test_master_ve_todos_servicos_e_comum_mantem_escopo(self):
        master, _ = garantir_usuario_master(email='master-services@example.com', senha='SenhaSegura#2026')
        self.assertIn(self.servico, servicos_disponiveis_para_usuario(master))
        self.assertNotIn(self.servico, servicos_disponiveis_para_usuario(self.terceiro))

    def test_pj_sem_empresa_rejeitado(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('painel:servico_criar'), self.dados_cadastro(prestador_tipo=Servico.PrestadorTipo.EMPRESA, empresa=''))
        self.assertEqual(resposta.status_code, 200)

    def test_pf_com_empresa_enviada_e_rejeitada(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(empresa=self.empresa.pk),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Servico.objects.filter(titulo='Novo serviço persistente').exists())

    def test_sem_atendimento_rejeitado(self):
        self.client.force_login(self.usuario)
        dados = self.dados_cadastro()
        dados.pop('atendimento_presencial')
        resposta = self.client.post(reverse('painel:servico_criar'), dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Servico.objects.filter(titulo='Novo serviço persistente').exists())

    def test_criacao_link_valido_servico(self):
        link = ServicoLink.objects.create(servico=self.servico, tipo_link=TipoLink.SITE, url='https://example.com/servico')
        self.assertEqual(link.url, 'https://example.com/servico')

    def test_criacao_link_valido_empresa(self):
        link = EmpresaLink.objects.create(empresa=self.empresa, tipo_link=TipoLink.SITE, url='https://example.com/empresa')
        self.assertEqual(link.url, 'https://example.com/empresa')

    def test_javascript_rejeitado(self):
        with self.assertRaises(ValidationError):
            normalizar_link_publico(TipoLink.OUTRO, 'javascript:alert(1)')

    def test_data_rejeitado(self):
        with self.assertRaises(ValidationError):
            normalizar_link_publico(TipoLink.OUTRO, 'data:text/html,teste')

    def test_html_script_e_iframe_rejeitados(self):
        for valor in ('<b>https://example.com</b>', '<script>alert(1)</script>', '<iframe src="https://example.com"></iframe>'):
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                normalizar_link_publico(TipoLink.OUTRO, valor)

    def test_dominio_falso_rede_social_rejeitado(self):
        with self.assertRaises(ValidationError):
            normalizar_link_publico(TipoLink.INSTAGRAM, 'https://instagram.com.exemplo.com/perfil')

    def test_instagram_oficial_aceito(self):
        url, identificador = normalizar_link_publico(TipoLink.INSTAGRAM, 'https://www.instagram.com/botuka/?utm_source=teste')
        self.assertEqual(url, 'https://www.instagram.com/botuka/')
        self.assertEqual(identificador, '')

    def test_facebook_oficial_aceito(self):
        url, _ = normalizar_link_publico(TipoLink.FACEBOOK, 'https://facebook.com/botuka')
        self.assertEqual(url, 'https://facebook.com/botuka')

    def test_youtube_oficial_aceito(self):
        url, _ = normalizar_link_publico(TipoLink.YOUTUBE, 'https://www.youtube.com/@botuka')
        self.assertEqual(url, 'https://www.youtube.com/@botuka')

    def test_youtube_extrai_id_video(self):
        link = ServicoLink.objects.create(servico=self.servico, tipo_link=TipoLink.YOUTUBE, url='https://youtu.be/dQw4w9WgXcQ?si=abc')
        self.assertEqual(link.identificador_externo, 'dQw4w9WgXcQ')
        self.assertEqual(link.url_embed, 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ')

    def test_canal_e_playlist_sem_embed(self):
        for url in ('https://youtube.com/@botuka', 'https://youtube.com/playlist?list=PL123'):
            with self.subTest(url=url):
                _, identificador = normalizar_link_publico(TipoLink.YOUTUBE, url)
                self.assertEqual(identificador, '')

    def test_link_ativo_duplicado_rejeitado(self):
        ServicoLink.objects.create(servico=self.servico, tipo_link=TipoLink.SITE, url='https://example.com/duplicado')
        with self.assertRaises(ValidationError):
            ServicoLink.objects.create(servico=self.servico, tipo_link=TipoLink.SITE, url='https://example.com/duplicado')

    def test_constraint_rejeita_duplicado_sem_passar_por_save(self):
        ServicoLink.objects.create(servico=self.servico, tipo_link=TipoLink.SITE, url='https://example.com/constraint')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ServicoLink.objects.bulk_create([ServicoLink(servico=self.servico, tipo_link=TipoLink.SITE, url='https://example.com/constraint')])

    def test_link_inativo_pode_coexistir(self):
        ServicoLink.objects.create(servico=self.servico, tipo_link=TipoLink.SITE, url='https://example.com/inativo')
        link = ServicoLink.objects.create(servico=self.servico, tipo_link=TipoLink.SITE, url='https://example.com/inativo', ativo=False)
        self.assertFalse(link.ativo)

    def test_ordem_negativa_rejeitada(self):
        with self.assertRaises(ValidationError):
            ServicoLink.objects.create(servico=self.servico, tipo_link=TipoLink.SITE, url='https://example.com/ordem', ordem=-1)

    def test_qr_tokens_sao_unicos(self):
        self.assertNotEqual(self.servico.qr_token, self.empresa.qr_token)

    def test_regeneracao_altera_token(self):
        anterior = self.servico.qr_token
        self.servico.regenerar_qr_token()
        self.assertNotEqual(anterior, self.servico.qr_token)

    def test_token_antigo_deixa_de_localizar_objeto(self):
        anterior = self.servico.qr_token
        self.servico.regenerar_qr_token()
        self.assertFalse(Servico.objects.filter(qr_token=anterior).exists())

    def test_qr_servico_publicado_redireciona(self):
        resposta = self.client.get(reverse('publico:qrcode_servico', args=[self.servico.qr_token]))
        self.assertRedirects(resposta, reverse('publico:servico', args=[self.servico.slug]), fetch_redirect_response=False)

    def test_qr_servico_nao_publicado_retorna_404(self):
        self.servico.status = Servico.Status.RASCUNHO
        self.servico.save()
        resposta = self.client.get(reverse('publico:qrcode_servico', args=[self.servico.qr_token]))
        self.assertEqual(resposta.status_code, 404)

    def test_qr_empresa_publica_ativa_redireciona(self):
        resposta = self.client.get(reverse('publico:qrcode_empresa', args=[self.empresa.qr_token]))
        self.assertRedirects(resposta, reverse('publico:empresa', args=[self.empresa.slug]), fetch_redirect_response=False)

    def test_qr_empresa_inativa_ou_privada_retorna_404(self):
        for campo, valor in (('ativo', False), ('perfil_publico', False)):
            Empresa.all_objects.filter(pk=self.empresa.pk).update(ativo=True, perfil_publico=True)
            Empresa.all_objects.filter(pk=self.empresa.pk).update(**{campo: valor})
            with self.subTest(campo=campo):
                resposta = self.client.get(reverse('publico:qrcode_empresa', args=[self.empresa.qr_token]))
                self.assertEqual(resposta.status_code, 404)

    def test_terceiro_nao_gerencia_links_servico(self):
        self.client.force_login(self.terceiro)
        resposta = self.client.get(reverse('painel:servico_links', args=[self.servico.uuid]))
        self.assertIn(resposta.status_code, (403, 404))

    def test_terceiro_nao_gerencia_links_empresa(self):
        self.client.force_login(self.terceiro)
        resposta = self.client.get(reverse('painel:empresa_links', args=[self.empresa.uuid]))
        self.assertIn(resposta.status_code, (403, 404))

    def test_qr_ignora_destino_arbitrario(self):
        resposta = self.client.get(reverse('publico:qrcode_servico', args=[self.servico.qr_token]), {'url': 'https://evil.example'})
        self.assertEqual(resposta.url, reverse('publico:servico', args=[self.servico.slug]))

    def test_limite_de_links(self):
        for indice in range(15):
            ServicoLink.objects.create(servico=self.servico, tipo_link=TipoLink.SITE, url=f'https://example.com/link-{indice}')
        with self.assertRaises(ValidationError):
            ServicoLink.objects.create(servico=self.servico, tipo_link=TipoLink.SITE, url='https://example.com/excedente')

    def test_limite_de_videos(self):
        ids = ('dQw4w9WgXcQ', 'aaaaaaaaaaa', 'bbbbbbbbbbb', 'ccccccccccc', 'ddddddddddd', 'eeeeeeeeeee')
        for identificador in ids:
            ServicoLink.objects.create(servico=self.servico, tipo_link=TipoLink.YOUTUBE, url=f'https://youtu.be/{identificador}')
        with self.assertRaises(ValidationError):
            ServicoLink.objects.create(servico=self.servico, tipo_link=TipoLink.YOUTUBE, url='https://youtu.be/fffffffffff')
