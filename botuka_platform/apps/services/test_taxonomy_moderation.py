from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.search.registry import _servico as servicos_da_busca_global
from apps.core.seo.sitemaps import ServicoSitemap
from apps.core.services.home.adapters.services import obter_servicos_destaque

from apps.services.models import (
    AreaProfissional,
    FormaCobranca,
    Profissao,
    ProfissaoTipoServico,
    Servico,
    Setor,
    TipoServico,
)
from apps.services.taxonomy_moderation import normalizar_nome_catalogo


class TaxonomiaModeracaoTests(TestCase):
    def setUp(self):
        usuario = get_user_model()
        self.autor = usuario.objects.create_user(username='autor-taxonomia')
        self.outro = usuario.objects.create_user(username='outro-taxonomia')
        self.moderador = usuario.objects.create_user(
            username='moderador-taxonomia', is_staff=True,
        )
        self.aprovado = Setor.objects.create(nome='Catálogo aprovado')
        self.pendente = Setor.objects.create(
            nome='  ÁREA   de  Saúde ', origem=Setor.Origem.USUARIO,
            status_catalogo=Setor.StatusCatalogo.PENDENTE, criado_por=self.autor,
        )

    def test_normalizacao_preserva_nome_original(self):
        self.assertEqual(self.pendente.nome, '  ÁREA   de  Saúde ')
        self.assertEqual(self.pendente.nome_normalizado, 'area de saude')
        self.assertEqual(normalizar_nome_catalogo('  AÇÃO   Fiscal '), 'acao fiscal')

    def test_aprovado_e_global_e_pendente_e_do_criador(self):
        visiveis = Setor.objects.visiveis_para(self.autor)
        self.assertTrue(visiveis.filter(pk=self.aprovado.pk).exists())
        self.assertTrue(visiveis.filter(pk=self.pendente.pk).exists())
        self.assertFalse(Setor.objects.visiveis_para(self.outro).filter(pk=self.pendente.pk).exists())
        self.assertFalse(Setor.objects.visiveis_para().filter(pk=self.pendente.pk).exists())

    def test_moderador_visualiza_pendente(self):
        self.assertTrue(
            Setor.objects.visiveis_para(self.moderador).filter(pk=self.pendente.pk).exists()
        )

    def test_rejeitado_e_mesclado_nao_sao_visiveis(self):
        for status in (Setor.StatusCatalogo.REJEITADO, Setor.StatusCatalogo.MESCLADO):
            item = Setor.objects.create(nome=f'Setor {status}', status_catalogo=status)
            self.assertFalse(
                Setor.objects.visiveis_para(self.moderador).filter(pk=item.pk).exists()
            )


class PublicacaoTaxonomiaModeradaTests(TestCase):
    def setUp(self):
        usuario = get_user_model()
        self.autor = usuario.objects.create_user(username='autor-publicacao-taxonomia')
        self.outro = usuario.objects.create_user(username='outro-publicacao-taxonomia')
        self.forma = FormaCobranca.objects.create(nome='Por serviço')

    def criar_taxonomia(self, *, status='APROVADO', criado_por=None, sufixo='aprovada'):
        atributos = {'status_catalogo': status, 'criado_por': criado_por}
        setor = Setor.objects.create(nome=f'Setor {sufixo}', **atributos)
        area = AreaProfissional.objects.create(
            setor=setor, nome=f'Área {sufixo}', **atributos,
        )
        profissao = Profissao.objects.create(
            setor=setor, area=area, nome=f'Profissão {sufixo}', **atributos,
        )
        tipo = TipoServico.objects.create(nome=f'Tipo {sufixo}')
        vinculo = ProfissaoTipoServico.objects.create(
            profissao=profissao, tipo_servico=tipo,
        )
        return setor, area, profissao, tipo, vinculo

    def publicar(self, taxonomia, *, usuario=None):
        setor, area, profissao, tipo, _ = taxonomia
        return Servico.objects.create(
            usuario_responsavel=usuario or self.autor,
            prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA,
            setor=setor,
            area=area,
            profissao=profissao,
            tipo_servico=tipo,
            forma_cobranca=self.forma,
            titulo=f'Serviço {setor.nome}',
            status=Servico.Status.PUBLICADO,
        )

    def test_servico_com_taxonomia_aprovada_publica(self):
        servico = self.publicar(self.criar_taxonomia())
        self.assertEqual(servico.status, Servico.Status.PUBLICADO)

    def test_pendentes_criados_pelo_responsavel_publicam(self):
        taxonomia = self.criar_taxonomia(
            status=Setor.StatusCatalogo.PENDENTE,
            criado_por=self.autor,
            sufixo='pendente própria',
        )
        servico = self.publicar(taxonomia)
        self.assertEqual(servico.status, Servico.Status.PUBLICADO)

    def test_pendente_de_outro_usuario_bloqueia_publicacao(self):
        taxonomia = self.criar_taxonomia(
            status=Setor.StatusCatalogo.PENDENTE,
            criado_por=self.outro,
            sufixo='pendente alheia',
        )
        with self.assertRaises(ValidationError):
            self.publicar(taxonomia)

    def test_rejeitado_bloqueia_publicacao(self):
        taxonomia = self.criar_taxonomia(
            status=Setor.StatusCatalogo.REJEITADO, sufixo='rejeitada',
        )
        with self.assertRaises(ValidationError):
            self.publicar(taxonomia)

    def test_mesclado_bloqueia_publicacao(self):
        taxonomia = self.criar_taxonomia(
            status=Setor.StatusCatalogo.MESCLADO, sufixo='mesclada',
        )
        with self.assertRaises(ValidationError):
            self.publicar(taxonomia)

    def test_vinculo_pendente_do_responsavel_permite_publicacao(self):
        taxonomia = self.criar_taxonomia(sufixo='vínculo próprio')
        vinculo = taxonomia[-1]
        vinculo.status_catalogo = ProfissaoTipoServico.StatusCatalogo.PENDENTE
        vinculo.criado_por = self.autor
        vinculo.save(update_fields=['status_catalogo', 'criado_por'])
        servico = self.publicar(taxonomia)
        self.assertEqual(servico.status, Servico.Status.PUBLICADO)

    def test_vinculo_pendente_de_outro_usuario_bloqueia_publicacao(self):
        taxonomia = self.criar_taxonomia(sufixo='vínculo alheio')
        vinculo = taxonomia[-1]
        vinculo.status_catalogo = ProfissaoTipoServico.StatusCatalogo.PENDENTE
        vinculo.criado_por = self.outro
        vinculo.save(update_fields=['status_catalogo', 'criado_por'])
        with self.assertRaises(ValidationError):
            self.publicar(taxonomia)

    def test_catalogo_publico_exclui_pendente(self):
        pendente = Setor.objects.create(
            nome='Setor não público',
            origem=Setor.Origem.USUARIO,
            status_catalogo=Setor.StatusCatalogo.PENDENTE,
            criado_por=self.autor,
        )
        self.assertFalse(Setor.objects.visiveis_para().filter(pk=pendente.pk).exists())

    def test_servico_aprovado_aparece_nas_superficies_publicas(self):
        servico = self.publicar(self.criar_taxonomia(sufixo='pública'))
        response = self.client.get(reverse('publico:servicos'))
        self.assertContains(response, servico.titulo)
        self.assertTrue(servicos_da_busca_global().filter(pk=servico.pk).exists())
        self.assertIn(servico, obter_servicos_destaque())
        self.assertTrue(ServicoSitemap().items().filter(pk=servico.pk).exists())

    def test_cada_item_pendente_retira_servico_da_exposicao_publica(self):
        for indice, posicao in enumerate((0, 1, 2, 3)):
            with self.subTest(posicao=posicao):
                taxonomia = self.criar_taxonomia(sufixo=f'pendência pública {indice}')
                servico = self.publicar(taxonomia)
                item = taxonomia[posicao]
                item.status_catalogo = item.StatusCatalogo.PENDENTE
                item.criado_por = self.autor
                item.save(update_fields=['status_catalogo', 'criado_por'])
                self.assertFalse(
                    Servico.objects.publicamente_visiveis().filter(pk=servico.pk).exists()
                )

    def test_vinculo_pendente_retira_servico_da_exposicao_publica(self):
        taxonomia = self.criar_taxonomia(sufixo='vínculo público pendente')
        servico = self.publicar(taxonomia)
        vinculo = taxonomia[-1]
        vinculo.status_catalogo = ProfissaoTipoServico.StatusCatalogo.PENDENTE
        vinculo.criado_por = self.autor
        vinculo.save(update_fields=['status_catalogo', 'criado_por'])
        self.assertFalse(
            Servico.objects.publicamente_visiveis().filter(pk=servico.pk).exists()
        )

    def test_rejeitado_e_mesclado_nunca_aparecem_publicamente(self):
        for status in (Setor.StatusCatalogo.REJEITADO, Setor.StatusCatalogo.MESCLADO):
            with self.subTest(status=status):
                taxonomia = self.criar_taxonomia(sufixo=f'público {status.lower()}')
                servico = self.publicar(taxonomia)
                Setor.objects.filter(pk=taxonomia[0].pk).update(status_catalogo=status)
                self.assertFalse(
                    Servico.objects.publicamente_visiveis().filter(pk=servico.pk).exists()
                )

    def test_servico_legado_sem_area_continua_publicamente_visivel(self):
        setor = Setor.objects.create(nome='Setor legado público')
        profissao = Profissao.objects.create(
            setor=setor, area=None, nome='Profissão legada pública',
        )
        servico = Servico.objects.create(
            usuario_responsavel=self.autor,
            prestador_tipo=Servico.PrestadorTipo.PESSOA_FISICA,
            setor=setor,
            area=None,
            profissao=profissao,
            forma_cobranca=self.forma,
            titulo='Serviço legado público sem área',
            status=Servico.Status.RASCUNHO,
        )
        Servico.objects.filter(pk=servico.pk).update(
            status=Servico.Status.PUBLICADO, publicado_em=timezone.now(),
        )
        self.assertTrue(
            Servico.objects.publicamente_visiveis().filter(pk=servico.pk).exists()
        )

    def test_busca_home_e_sitemap_nao_vazam_taxonomia_pendente(self):
        taxonomia = self.criar_taxonomia(sufixo='oculta nas superfícies')
        servico = self.publicar(taxonomia)
        Profissao.objects.filter(pk=taxonomia[2].pk).update(
            status_catalogo=Profissao.StatusCatalogo.PENDENTE,
            criado_por=self.autor,
        )
        self.assertFalse(servicos_da_busca_global().filter(pk=servico.pk).exists())
        self.assertNotIn(servico, obter_servicos_destaque())
        self.assertFalse(ServicoSitemap().items().filter(pk=servico.pk).exists())
