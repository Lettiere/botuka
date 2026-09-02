from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connection, transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.core.public_links import TipoLink, normalizar_link_publico
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import (
    Capacidade, Empresa, EmpresaCapacidade, EmpresaLink, EmpresaUsuario,
)
from apps.services.models import AreaProfissional, FormaCobranca, Profissao, ProfissaoTipoServico, Servico, ServicoLink, Setor, TipoServico
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
            atuacao=Empresa.Atuacao.SERVICOS,
        )
        capacidade, _ = Capacidade.objects.get_or_create(
            codigo='PRESTAR_SERVICOS', defaults={'nome': 'Prestar serviços'},
        )
        EmpresaCapacidade.objects.create(
            empresa=cls.empresa, capacidade=capacidade,
            status=EmpresaCapacidade.Status.APROVADA, ativo=True,
        )
        setor = Setor.objects.create(nome='Tecnologia')
        cls.area_profissional = AreaProfissional.objects.create(setor=setor, nome='Desenvolvimento')
        profissao = Profissao.objects.create(setor=setor, area=cls.area_profissional, nome='Desenvolvedor')
        tipo, _ = TipoServico.objects.get_or_create(nome='Consultoria')
        ProfissaoTipoServico.objects.get_or_create(profissao=profissao, tipo_servico=tipo)
        cobranca = FormaCobranca.objects.create(nome='Por hora')
        cls.servico = Servico.objects.create(
            usuario_responsavel=cls.usuario,
            prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA,
            setor=setor,
            area=cls.area_profissional,
            profissao=profissao,
            tipo_servico=tipo,
            forma_cobranca=cobranca,
            titulo='Consultoria em tecnologia',
            status=Servico.Status.PUBLICADO,
        )

    def dados_cadastro(self, **alteracoes):
        dados = {
            'prestador_tipo': Servico.PrestadorTipo.PESSOA_FISICA,
            'empresa': '', 'setor': self.servico.setor_id, 'area': self.area_profissional.pk,
            'profissao': self.servico.profissao_id,
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
                area=self.servico.area,
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
        resposta = self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(
                prestador_tipo=Servico.PrestadorTipo.EMPRESA,
                empresa=self.empresa.pk,
                acao='continuar',
            ),
        )
        self.assertEqual(resposta.status_code, 302)
        criado = Servico.objects.get(titulo='Novo serviço persistente')
        self.assertEqual(criado.empresa, self.empresa)
        self.assertEqual(criado.status, Servico.Status.RASCUNHO)
        self.assertEqual(
            resposta.url,
            reverse('painel:servico_editar', kwargs={'uuid': criado.uuid}),
        )

    def test_empresa_de_terceiro_bloqueada_no_cadastro(self):
        self.client.force_login(self.terceiro)
        resposta = self.client.post(reverse('painel:servico_criar'), self.dados_cadastro(prestador_tipo=Servico.PrestadorTipo.EMPRESA, empresa=self.empresa.pk))
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Servico.objects.filter(titulo='Novo serviço persistente').exists())

    def test_formulario_lista_apenas_empresa_administrada(self):
        outra_empresa = Empresa.objects.create(
            usuario_proprietario=self.terceiro,
            nome_fantasia='Empresa de terceiro',
            cidade=self.empresa.cidade,
            estado=self.empresa.estado,
            status=Empresa.Status.ATIVA,
            perfil_publico=True,
            atuacao=Empresa.Atuacao.SERVICOS,
        )
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('painel:servico_criar'))
        self.assertContains(resposta, self.empresa.nome_fantasia)
        self.assertNotContains(resposta, outra_empresa.nome_fantasia)

    def test_edicao_troca_empresa_por_autonomo_e_remove_empresa(self):
        self.servico.prestador_tipo = Servico.PrestadorTipo.EMPRESA
        self.servico.empresa = self.empresa
        self.servico.save()
        self.client.force_login(self.usuario)
        resposta = self.client.post(
            reverse('painel:servico_editar', kwargs={'uuid': self.servico.uuid}),
            self.dados_cadastro(titulo=self.servico.titulo, acao='salvar'),
        )
        self.assertEqual(resposta.status_code, 302)
        self.servico.refresh_from_db()
        self.assertEqual(self.servico.prestador_tipo, Servico.PrestadorTipo.PESSOA_FISICA)
        self.assertIsNone(self.servico.empresa_id)
        self.assertEqual(self.servico.usuario_responsavel, self.usuario)

    def test_area_de_outro_setor_rejeitada(self):
        outro_setor = Setor.objects.create(nome='Saúde')
        outra_area = AreaProfissional.objects.create(setor=outro_setor, nome='Clínica')
        self.client.force_login(self.usuario)
        resposta = self.client.post(
            reverse('painel:servico_editar', kwargs={'uuid': self.servico.uuid}),
            self.dados_cadastro(
                titulo=self.servico.titulo,
                setor=self.servico.setor_id,
                area=outra_area.pk,
                acao='salvar',
            ),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'A área profissional não pertence ao setor selecionado.')

    def test_ajax_respeita_hierarquia_e_rejeita_id_invalido(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(
            reverse('painel:servicos_ajax_areas'),
            {'setor_id': self.servico.setor_id},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['results'][0]['id'], self.area_profissional.pk)
        invalida = self.client.get(reverse('painel:servicos_ajax_areas'), {'setor_id': 'invalido'})
        self.assertEqual(invalida.status_code, 200)
        self.assertEqual(invalida.json(), {'results': []})

    def test_formulario_edicao_preserva_classificacao(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(
            reverse('painel:servico_editar', kwargs={'uuid': self.servico.uuid}),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, self.area_profissional.nome)
        self.assertContains(resposta, self.servico.profissao.nome)

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

    def test_sem_atendimento_rejeitado_na_publicacao(self):
        self.client.force_login(self.usuario)
        dados = self.dados_cadastro(acao='publicar')
        dados.pop('atendimento_presencial')
        resposta = self.client.post(reverse('painel:servico_criar'), dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Servico.objects.filter(titulo='Novo serviço persistente').exists())

    def test_rascunho_incompleto_pode_ser_salvo(self):
        self.client.force_login(self.usuario)
        dados = self.dados_cadastro(
            area='',
            profissao='',
            tipo_servico='',
            forma_cobranca='',
            descricao_completa='',
            experiencia='',
            preco_inicial='',
            preco_sob_consulta='on',
            acao='rascunho',
        )
        resposta = self.client.post(reverse('painel:servico_criar'), dados)
        self.assertEqual(resposta.status_code, 302)
        criado = Servico.objects.get(titulo='Novo serviço persistente')
        self.assertEqual(criado.status, Servico.Status.RASCUNHO)
        self.assertIsNotNone(criado.setor_id)
        self.assertIsNone(criado.area_id)
        self.assertIsNone(criado.profissao_id)
        self.assertIsNone(criado.forma_cobranca_id)
        self.assertTrue(criado.preco_sob_consulta)
        self.assertTrue(criado.slug)

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

    def criar_empresa_sem_capacidade(self, atuacao, *, proprietario=None, nome='Empresa sem capacidade'):
        modalidade = (
            Empresa.ModalidadeComercial.VAREJO
            if atuacao in {
                Empresa.Atuacao.COMERCIO,
                Empresa.Atuacao.COMERCIO_E_SERVICOS,
            }
            else ''
        )
        return Empresa.objects.create(
            usuario_proprietario=proprietario or self.usuario,
            nome_fantasia=nome,
            cidade=self.empresa.cidade,
            estado=self.empresa.estado,
            status=Empresa.Status.ATIVA,
            atuacao=atuacao,
            modalidade_comercial=modalidade,
        )

    def test_servicos_sem_capacidade_cria_rascunho_contextual_e_generico(self):
        empresa = self.criar_empresa_sem_capacidade(
            Empresa.Atuacao.SERVICOS, nome='Serviços sem capacidade',
        )
        self.client.force_login(self.usuario)

        contextual = self.client.post(
            f"{reverse('painel:servico_criar')}?empresa={empresa.pk}",
            self.dados_cadastro(
                titulo='Rascunho contextual',
                prestador_tipo=Servico.PrestadorTipo.EMPRESA,
                empresa=empresa.pk,
            ),
        )
        generico = self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(
                titulo='Rascunho genérico',
                prestador_tipo=Servico.PrestadorTipo.EMPRESA,
                empresa=empresa.pk,
            ),
        )

        self.assertEqual(contextual.status_code, 302)
        self.assertEqual(generico.status_code, 302)
        self.assertEqual(
            set(Servico.objects.filter(empresa=empresa).values_list('status', flat=True)),
            {Servico.Status.RASCUNHO},
        )

    def test_comercio_e_servicos_sem_capacidade_cria_rascunho(self):
        empresa = self.criar_empresa_sem_capacidade(
            Empresa.Atuacao.COMERCIO_E_SERVICOS,
            nome='Comércio e serviços sem capacidade',
        )
        self.client.force_login(self.usuario)
        response = self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(
                titulo='Rascunho comércio e serviços',
                prestador_tipo=Servico.PrestadorTipo.EMPRESA,
                empresa=empresa.pk,
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Servico.objects.filter(
            empresa=empresa, status=Servico.Status.RASCUNHO,
        ).exists())

    def test_comercio_nao_cria_servico_contextual_nem_generico(self):
        empresa = self.criar_empresa_sem_capacidade(
            Empresa.Atuacao.COMERCIO, nome='Comércio incompatível',
        )
        self.client.force_login(self.usuario)
        contextual = self.client.get(
            reverse('painel:servico_criar'), {'empresa': empresa.pk},
        )
        generico = self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(
                titulo='Serviço comercial indevido',
                prestador_tipo=Servico.PrestadorTipo.EMPRESA,
                empresa=empresa.pk,
            ),
        )
        self.assertEqual(contextual.status_code, 302)
        self.assertEqual(generico.status_code, 200)
        self.assertFalse(Servico.objects.filter(
            titulo='Serviço comercial indevido',
        ).exists())

    def test_capacidade_pendente_permite_rascunho_mas_bloqueia_publicacao(self):
        vinculo = self.empresa.capacidades_empresa.get(
            capacidade__codigo='PRESTAR_SERVICOS',
        )
        vinculo.status = EmpresaCapacidade.Status.PENDENTE
        vinculo.save(update_fields=['status', 'atualizado_em'])
        self.client.force_login(self.usuario)
        rascunho = self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(
                titulo='Rascunho com capacidade pendente',
                prestador_tipo=Servico.PrestadorTipo.EMPRESA,
                empresa=self.empresa.pk,
            ),
        )
        criado = Servico.objects.get(titulo='Rascunho com capacidade pendente')
        publicacao = self.client.post(
            reverse('painel:servico_alterar_status', kwargs={'uuid': criado.uuid}),
            {'status': Servico.Status.PUBLICADO},
            follow=True,
        )
        self.assertEqual(rascunho.status_code, 302)
        self.assertEqual(publicacao.status_code, 200)
        self.assertContains(
            publicacao,
            'Sua empresa ainda não está autorizada a publicar serviços. '
            'A capacidade de prestar serviços está aguardando aprovação.',
        )
        criado.refresh_from_db()
        self.assertEqual(criado.status, Servico.Status.RASCUNHO)
        self.assertIsNone(criado.publicado_em)
        self.assertFalse(Servico.objects.publicamente_visiveis().filter(pk=criado.pk).exists())

    def test_capacidade_aprovada_permite_publicacao_empresarial(self):
        servico = Servico.objects.create(
            usuario_responsavel=self.usuario,
            prestador_tipo=Servico.PrestadorTipo.EMPRESA,
            empresa=self.empresa,
            setor=self.servico.setor,
            area=self.servico.area,
            profissao=self.servico.profissao,
            tipo_servico=self.servico.tipo_servico,
            forma_cobranca=self.servico.forma_cobranca,
            titulo='Serviço empresarial apto para publicação',
            atendimento_presencial=True,
            status=Servico.Status.RASCUNHO,
        )
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('painel:servico_alterar_status', kwargs={'uuid': servico.uuid}),
            {'status': Servico.Status.PUBLICADO},
        )

        self.assertEqual(response.status_code, 302)
        servico.refresh_from_db()
        self.assertEqual(servico.status, Servico.Status.PUBLICADO)
        self.assertIsNotNone(servico.publicado_em)
        self.assertTrue(Servico.objects.publicamente_visiveis().filter(pk=servico.pk).exists())

    def test_usuario_nao_autorizado_continua_bloqueado_na_publicacao(self):
        servico = Servico.objects.create(
            usuario_responsavel=self.usuario,
            prestador_tipo=Servico.PrestadorTipo.EMPRESA,
            empresa=self.empresa,
            setor=self.servico.setor,
            area=self.servico.area,
            profissao=self.servico.profissao,
            tipo_servico=self.servico.tipo_servico,
            forma_cobranca=self.servico.forma_cobranca,
            titulo='Serviço empresarial protegido',
            atendimento_presencial=True,
            status=Servico.Status.RASCUNHO,
        )
        EmpresaUsuario.objects.create(
            empresa=self.empresa,
            usuario=self.terceiro,
            pode_editar=True,
            pode_publicar_servico=False,
            ativo=True,
        )
        self.client.force_login(self.terceiro)
        request = RequestFactory().post(
            reverse('painel:servico_alterar_status', kwargs={'uuid': servico.uuid}),
            {'status': Servico.Status.PUBLICADO},
        )
        request.user = self.terceiro
        request.session = {}
        request._messages = FallbackStorage(request)

        from apps.painel.views import servico_alterar_status
        with (
            patch('apps.painel.views._servico_autorizado', return_value=servico),
            self.assertRaises(PermissionDenied),
        ):
            servico_alterar_status.__wrapped__(request, servico.uuid)
        servico.refresh_from_db()
        self.assertEqual(servico.status, Servico.Status.RASCUNHO)
        self.assertIsNone(servico.publicado_em)

    def test_post_contextual_adulterando_empresa_e_bloqueado(self):
        outra = self.criar_empresa_sem_capacidade(
            Empresa.Atuacao.SERVICOS,
            proprietario=self.terceiro,
            nome='Empresa adulterada',
        )
        self.client.force_login(self.usuario)
        response = self.client.post(
            f"{reverse('painel:servico_criar')}?empresa={self.empresa.pk}",
            self.dados_cadastro(
                titulo='Serviço adulterado',
                prestador_tipo=Servico.PrestadorTipo.EMPRESA,
                empresa=outra.pk,
            ),
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Servico.objects.filter(titulo='Serviço adulterado').exists())

    def test_empresa_sem_atuacao_nao_cria_servico_empresarial(self):
        empresa = self.criar_empresa_sem_capacidade(None, nome='Empresa sem atuação')
        self.client.force_login(self.usuario)
        response = self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(
                titulo='Serviço sem atuação',
                prestador_tipo=Servico.PrestadorTipo.EMPRESA,
                empresa=empresa.pk,
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Servico.objects.filter(titulo='Serviço sem atuação').exists())
    def test_servico_legado_de_empresa_incompativel_continua_editavel(self):
        empresa_legada = self.criar_empresa_sem_capacidade(
            Empresa.Atuacao.COMERCIO, nome='Empresa comercial legada',
        )
        servico_legado = Servico.objects.create(
            usuario_responsavel=self.usuario,
            prestador_tipo=Servico.PrestadorTipo.EMPRESA,
            empresa=empresa_legada,
            setor=self.servico.setor,
            area=self.servico.area,
            profissao=self.servico.profissao,
            tipo_servico=self.servico.tipo_servico,
            forma_cobranca=self.servico.forma_cobranca,
            titulo='Serviço empresarial legado',
            descricao_curta='Descrição legada',
            descricao_completa='Descrição completa legada',
            preco_inicial=Decimal('100.00'),
            atendimento_presencial=True,
            status=Servico.Status.RASCUNHO,
        )
        self.client.force_login(self.usuario)
        url = reverse('painel:servico_editar', kwargs={'uuid': servico_legado.uuid})
        edicao = self.client.get(url)
        self.assertEqual(edicao.status_code, 200)
        self.assertContains(edicao, empresa_legada.nome_fantasia)

        response = self.client.post(
            url,
            self.dados_cadastro(
                titulo='Serviço empresarial legado editado',
                prestador_tipo=Servico.PrestadorTipo.EMPRESA,
                empresa=empresa_legada.pk,
                acao='salvar',
            ),
        )
        self.assertEqual(response.status_code, 302)
        servico_legado.refresh_from_db()
        self.assertEqual(servico_legado.titulo, 'Serviço empresarial legado editado')
        self.assertEqual(servico_legado.empresa, empresa_legada)
    def test_cadastro_rapido_exibe_somente_campos_essenciais(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse('painel:servico_criar'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['form'].fields),
            [
                'prestador_tipo', 'empresa', 'titulo', 'setor',
                'descricao_curta', 'preco_inicial', 'preco_sob_consulta',
                'atendimento_presencial', 'atendimento_remoto',
            ],
        )
        self.assertNotContains(response, 'Descrição completa')
        self.assertNotContains(response, 'Experiência e qualificações')
        self.assertContains(response, 'Continuar configuração')

    def test_preco_informado_e_sob_consulta_funcionam_separadamente(self):
        self.client.force_login(self.usuario)
        informado = self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(titulo='Serviço com preço', preco_inicial='75.50'),
        )
        consulta = self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(
                titulo='Serviço sob consulta', preco_inicial='',
                preco_sob_consulta='on',
            ),
        )
        self.assertEqual(informado.status_code, 302)
        self.assertEqual(consulta.status_code, 302)
        self.assertEqual(
            Servico.objects.get(titulo='Serviço com preço').preco_inicial,
            Decimal('75.50'),
        )
        self.assertTrue(
            Servico.objects.get(titulo='Serviço sob consulta').preco_sob_consulta,
        )

    def test_preco_negativo_e_preco_contraditorio_sao_rejeitados(self):
        self.client.force_login(self.usuario)
        negativo = self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(titulo='Preço negativo', preco_inicial='-1'),
        )
        contraditorio = self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(
                titulo='Preço contraditório', preco_inicial='10',
                preco_sob_consulta='on',
            ),
        )
        self.assertEqual(negativo.status_code, 200)
        self.assertEqual(contraditorio.status_code, 200)
        self.assertFalse(Servico.objects.filter(
            titulo__in=('Preço negativo', 'Preço contraditório'),
        ).exists())

    def test_modalidades_presencial_remoto_e_ambos_funcionam(self):
        self.client.force_login(self.usuario)
        casos = (
            ('Presencial rápido', {'atendimento_presencial': 'on'}),
            ('Remoto rápido', {'atendimento_remoto': 'on'}),
            ('Atendimento híbrido', {
                'atendimento_presencial': 'on', 'atendimento_remoto': 'on',
            }),
        )
        for titulo, modalidade in casos:
            dados = self.dados_cadastro(titulo=titulo)
            dados.pop('atendimento_presencial', None)
            dados.update(modalidade)
            with self.subTest(titulo=titulo):
                self.assertEqual(
                    self.client.post(reverse('painel:servico_criar'), dados).status_code,
                    302,
                )
                criado = Servico.objects.get(titulo=titulo)
                self.assertEqual(
                    (criado.atendimento_presencial, criado.atendimento_remoto),
                    (
                        'atendimento_presencial' in modalidade,
                        'atendimento_remoto' in modalidade,
                    ),
                )
                criado.delete()
    def test_sem_modalidade_e_rejeitado_no_cadastro_rapido(self):
        self.client.force_login(self.usuario)
        dados = self.dados_cadastro(titulo='Sem atendimento')
        dados.pop('atendimento_presencial', None)
        response = self.client.post(reverse('painel:servico_criar'), dados)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Selecione atendimento presencial, online ou ambos.')
        self.assertFalse(Servico.objects.filter(titulo='Sem atendimento').exists())

    def test_continuar_configuracao_mantem_rascunho_e_abre_edicao_completa(self):
        self.client.force_login(self.usuario)
        response = self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(titulo='Continuar serviço', acao='continuar'),
        )
        criado = Servico.objects.get(titulo='Continuar serviço')
        self.assertEqual(criado.status, Servico.Status.RASCUNHO)
        self.assertEqual(
            response.url,
            reverse('painel:servico_editar', kwargs={'uuid': criado.uuid}),
        )
        edicao = self.client.get(response.url)
        self.assertContains(edicao, 'Descrição completa')
        self.assertContains(edicao, 'Experiência e qualificações')

    def test_rascunho_minimo_nao_e_publico_nem_agendavel(self):
        from apps.agenda.public_services import servicos_agendaveis
        self.client.force_login(self.usuario)
        self.client.post(
            reverse('painel:servico_criar'),
            self.dados_cadastro(
                titulo='Rascunho mínimo privado', preco_inicial='',
                preco_sob_consulta='on',
                prestador_tipo=Servico.PrestadorTipo.EMPRESA,
                empresa=self.empresa.pk,
            ),
        )
        criado = Servico.objects.get(titulo='Rascunho mínimo privado')
        self.assertEqual(criado.status, Servico.Status.RASCUNHO)
        self.assertFalse(servicos_agendaveis(self.empresa).filter(pk=criado.pk).exists())

    def test_publicacao_incompleta_retorna_validacao_sem_erro_500(self):
        incompleto = Servico.objects.create(
            usuario_responsavel=self.usuario,
            prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA,
            setor=self.servico.setor,
            titulo='Rascunho incompleto para publicação',
            status=Servico.Status.RASCUNHO,
        )
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('painel:servico_alterar_status', kwargs={'uuid': incompleto.uuid}),
            {'status': Servico.Status.PUBLICADO},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Não foi possível publicar o serviço.')
        self.assertContains(response, 'Informe a área profissional')
        self.assertContains(response, 'Informe a profissão')
        incompleto.refresh_from_db()
        self.assertEqual(incompleto.status, Servico.Status.RASCUNHO)
        self.assertIsNone(incompleto.publicado_em)

    def test_taxonomia_fiscal_e_tributaria_e_idempotente(self):
        migracao = import_module(
            'apps.services.migrations.0011_taxonomia_fiscal_tributaria',
        )
        schema_editor = SimpleNamespace(connection=connection)

        migracao.criar_taxonomia_fiscal(django_apps, schema_editor)
        migracao.criar_taxonomia_fiscal(django_apps, schema_editor)

        setor = Setor.objects.get(nome__in=migracao.SETORES_CONTABEIS)
        area = AreaProfissional.objects.get(
            setor=setor, nome__iexact='Fiscal e Tributária', ativo=True,
        )
        analista = Profissao.objects.get(
            setor=setor, nome__iexact='Analista fiscal', ativo=True,
        )
        consultor = Profissao.objects.get(
            setor=setor, nome__iexact='Consultor tributário', ativo=True,
        )
        tipo = TipoServico.objects.get(nome__iexact='Consultoria', ativo=True)

        self.assertEqual(analista.area, area)
        self.assertEqual(consultor.setor, setor)
        self.assertTrue(ProfissaoTipoServico.objects.filter(
            profissao=analista, tipo_servico=tipo, ativo=True,
        ).exists())
        self.assertTrue(ProfissaoTipoServico.objects.filter(
            profissao=consultor, tipo_servico=tipo, ativo=True,
        ).exists())
        self.assertEqual(AreaProfissional.objects.filter(
            setor=setor, nome__iexact='Fiscal e Tributária',
        ).count(), 1)

    def test_profissao_rejeita_area_de_outro_setor(self):
        outro_setor = Setor.objects.create(nome='Setor contábil incompatível')
        outra_area = AreaProfissional.objects.create(
            setor=outro_setor, nome='Área incompatível',
        )
        profissao = Profissao(
            setor=self.servico.setor,
            area=outra_area,
            nome='Profissão incompatível',
        )

        with self.assertRaisesMessage(
            ValidationError,
            'A área profissional deve pertencer ao setor da profissão.',
        ):
            profissao.full_clean()

    def test_publicacao_completa_pela_view_continua_funcionando(self):
        completo = Servico.objects.create(
            usuario_responsavel=self.usuario,
            prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA,
            setor=self.servico.setor,
            area=self.servico.area,
            profissao=self.servico.profissao,
            tipo_servico=self.servico.tipo_servico,
            forma_cobranca=self.servico.forma_cobranca,
            titulo='Serviço completo para publicação',
            atendimento_presencial=True,
            status=Servico.Status.RASCUNHO,
        )
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('painel:servico_alterar_status', kwargs={'uuid': completo.uuid}),
            {'status': Servico.Status.PUBLICADO},
        )

        self.assertEqual(response.status_code, 302)
        completo.refresh_from_db()
        self.assertEqual(completo.status, Servico.Status.PUBLICADO)
        self.assertIsNotNone(completo.publicado_em)
