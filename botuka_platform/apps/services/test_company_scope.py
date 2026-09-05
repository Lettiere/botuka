from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.agenda.public_services import servicos_agendaveis
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import (
    Capacidade, Empresa, EmpresaCapacidade, UsuarioLimitePersonalizado,
)
from apps.services.models import Servico, Setor


class PainelServicosEmpresaSelecionadaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuario_model = get_user_model()
        cls.usuario = usuario_model.objects.create_user(
            'dono-duas-empresas', 'dono@example.com', 'senha-forte',
        )
        cls.terceiro = usuario_model.objects.create_user(
            'terceiro-empresa', 'terceiro@example.com', 'senha-forte',
        )
        cls.master = usuario_model.objects.create_superuser(
            'master-escopo-empresa', 'master-escopo@example.com', 'senha-forte',
        )
        UsuarioLimitePersonalizado.objects.create(
            usuario=cls.usuario,
            empresas_ilimitadas=True,
            servicos_ilimitados=True,
            motivo='Fixture de testes de escopo empresarial',
            concedido_por=cls.master,
        )
        pais = Pais.objects.create(
            nome='Brasil', codigo_iso_2='BR', codigo_iso_3='BRA',
        )
        estado = Estado.objects.create(pais=pais, nome='São Paulo', sigla='SP')
        cidade = Cidade.objects.create(estado=estado, nome='Botucatu')
        cls.empresa_a = cls._empresa(cls.usuario, 'Empresa A', cidade, estado)
        cls.empresa_b = cls._empresa(cls.usuario, 'Empresa B', cidade, estado)
        cls.empresa_sem_acesso = cls._empresa(
            cls.terceiro, 'Empresa sem acesso', cidade, estado,
        )
        capacidade, _ = Capacidade.objects.get_or_create(
            codigo='PRESTAR_SERVICOS', defaults={'nome': 'Prestar serviços'},
        )
        for empresa in (cls.empresa_a, cls.empresa_b, cls.empresa_sem_acesso):
            EmpresaCapacidade.objects.update_or_create(
                empresa=empresa,
                capacidade=capacidade,
                defaults={
                    'status': EmpresaCapacidade.Status.APROVADA,
                    'ativo': True,
                },
            )
        cls.setor = Setor.objects.create(nome='Serviços gerais')
        cls.a1 = cls._servico(cls.empresa_a, 'Serviço A1')
        cls.a2 = cls._servico(cls.empresa_a, 'Serviço A2')
        cls.b1 = cls._servico(cls.empresa_b, 'Serviço B1')

    @classmethod
    def _empresa(cls, proprietario, nome, cidade, estado):
        return Empresa.objects.create(
            usuario_proprietario=proprietario,
            nome_fantasia=nome,
            cidade=cidade,
            estado=estado,
            status=Empresa.Status.ATIVA,
            perfil_publico=True,
            atuacao=Empresa.Atuacao.SERVICOS,
        )

    @classmethod
    def _servico(cls, empresa, titulo):
        return Servico.objects.create(
            usuario_responsavel=cls.usuario,
            prestador_tipo=Servico.PrestadorTipo.EMPRESA,
            empresa=empresa,
            setor=cls.setor,
            titulo=titulo,
            atendimento_presencial=True,
            status=Servico.Status.RASCUNHO,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def selecionar(self, empresa):
        return self.client.get(
            reverse('painel:servicos_lista'), {'empresa': empresa.pk},
        )

    def test_listagem_e_troca_ficam_estritamente_na_empresa(self):
        resposta_a = self.selecionar(self.empresa_a)
        self.assertQuerySetEqual(
            resposta_a.context['servicos'], [self.a1, self.a2], ordered=False,
        )
        resposta_b = self.selecionar(self.empresa_b)
        self.assertQuerySetEqual(
            resposta_b.context['servicos'], [self.b1], ordered=False,
        )
        self.assertEqual(resposta_b.context['empresa_contexto'], self.empresa_b)

    def test_detalhe_edicao_exclusao_e_publicacao_cruzados_retornam_404(self):
        self.selecionar(self.empresa_a)
        rotas = (
            ('servico_detalhe', 'get'),
            ('servico_editar', 'get'),
            ('servico_excluir', 'get'),
            ('servico_excluir', 'post'),
            ('servico_alterar_status', 'post'),
            ('servico_qrcode', 'get'),
            ('servico_preview', 'get'),
        )
        for nome, metodo in rotas:
            with self.subTest(nome=nome, metodo=metodo):
                resposta = getattr(self.client, metodo)(
                    reverse(f'painel:{nome}', kwargs={'uuid': self.b1.uuid}),
                    {'status': Servico.Status.PUBLICADO},
                )
                self.assertEqual(resposta.status_code, 404)
        self.b1.refresh_from_db()
        self.assertEqual(self.b1.status, Servico.Status.RASCUNHO)
        self.assertTrue(Servico.objects.filter(pk=self.b1.pk).exists())

    def test_criacao_usa_empresa_ativa_e_bloqueia_post_adulterado(self):
        self.selecionar(self.empresa_a)
        dados = {
            'prestador_tipo': Servico.PrestadorTipo.EMPRESA,
            'empresa': self.empresa_a.pk,
            'titulo': 'Novo serviço da A',
            'setor': self.setor.pk,
            'descricao_curta': 'Descrição do novo serviço',
            'preco_inicial': '50.00',
            'atendimento_presencial': 'on',
            'acao': 'rascunho',
        }
        resposta = self.client.post(reverse('painel:servico_criar'), dados)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            Servico.objects.get(titulo='Novo serviço da A').empresa,
            self.empresa_a,
        )

        dados.update(empresa=self.empresa_b.pk, titulo='Serviço adulterado')
        resposta = self.client.post(reverse('painel:servico_criar'), dados)
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(Servico.objects.filter(titulo='Serviço adulterado').exists())

    def test_empresa_sem_acesso_nao_pode_ser_selecionada(self):
        resposta = self.client.get(
            reverse('painel:servicos_lista'),
            {'empresa': self.empresa_sem_acesso.pk},
        )
        self.assertEqual(resposta.status_code, 403)

    def test_agenda_e_publicacao_publica_preservam_escopo_proprio(self):
        agenda_antes = list(servicos_agendaveis(self.empresa_a))
        publicos_antes = list(
            Servico.objects.publicamente_visiveis().values_list('pk', flat=True)
        )

        self.selecionar(self.empresa_b)

        self.assertEqual(list(servicos_agendaveis(self.empresa_a)), agenda_antes)
        self.assertEqual(
            list(Servico.objects.publicamente_visiveis().values_list('pk', flat=True)),
            publicos_antes,
        )
