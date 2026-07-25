from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Assinatura, ContratacaoEmpresaAdicional, Empresa, Plano
from apps.organizations.plans import obter_limite_empresas, total_empresas_ativas, usuario_pode_criar_empresa
from .models import (Candidatura, Curriculo, CurriculoPrivacidade, Experiencia,
                     Formacao, Curso, Habilidade, Idioma, Projeto, Vaga)
from .services import calcular_progresso, curriculo_publico
from apps.accounts.master_services import garantir_usuario_master
from apps.organizations.permissions import empresas_disponiveis_para_usuario


class BaseRecruitmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.dono = U.objects.create_user('dono', 'dono@example.com', 'senha')
        cls.outro = U.objects.create_user('outro', 'outro@example.com', 'senha')
        pais = Pais.objects.create(nome='Brasil', codigo_iso_2='BR', codigo_iso_3='BRA')
        estado = Estado.objects.create(pais=pais, nome='São Paulo', sigla='SP')
        cidade = Cidade.objects.create(estado=estado, nome='Botucatu')
        cls.empresa = Empresa.objects.create(usuario_proprietario=cls.dono, nome_fantasia='Empresa A', cpf_cnpj='11222333000181', cidade=cidade, estado=estado, status=Empresa.Status.ATIVA)
        cls.empresa_outro = Empresa.objects.create(usuario_proprietario=cls.outro, nome_fantasia='Empresa B', cpf_cnpj='11444777000161', cidade=cidade, estado=estado, status=Empresa.Status.ATIVA)

    def vaga(self, **kwargs):
        dados = dict(empresa=self.empresa, usuario_responsavel=self.dono, titulo='Desenvolvedor', descricao='Descrição', tipo_contrato='CLT', modalidade='Remoto', cidade='Botucatu', estado='SP')
        dados.update(kwargs)
        return Vaga.objects.create(**dados)


class PlanoEmpresaTests(BaseRecruitmentTests):
    def test_gratuito_bloqueia_segunda_empresa(self):
        self.assertEqual(obter_limite_empresas(self.dono), 1)
        self.assertFalse(usuario_pode_criar_empresa(self.dono).permitido)

    def test_gratuito_permite_primeira_empresa(self):
        novo = get_user_model().objects.create_user('novo', password='senha')
        self.assertTrue(usuario_pode_criar_empresa(novo).permitido)

    def test_pago_respeita_limite(self):
        plano = Plano.objects.get(codigo=Plano.Codigo.BRONZE)
        assinatura = Assinatura.objects.create(usuario=self.dono, plano=plano)
        ContratacaoEmpresaAdicional.objects.create(
            assinatura=assinatura, quantidade=1, valor_unitario=Decimal('50.00'),
            status=ContratacaoEmpresaAdicional.Status.ATIVA,
        )
        self.assertTrue(usuario_pode_criar_empresa(self.dono).permitido)

    def test_nenhum_plano_inicial_e_ilimitado(self):
        self.assertFalse(Plano.objects.filter(ilimitado_servicos=True).exists())
        self.assertFalse(Plano.objects.filter(ilimitado_empresas=True).exists())

    def test_expirada_volta_gratuito(self):
        from django.utils import timezone
        plano = Plano.objects.get(codigo=Plano.Codigo.PREMIUM)
        Assinatura.objects.create(usuario=self.dono, plano=plano, fim=timezone.now() - timedelta(days=1))
        self.assertEqual(obter_limite_empresas(self.dono), 1)

    def test_gratuito_pode_contratar_empresas_adicionais(self):
        plano = Plano.objects.get(codigo=Plano.Codigo.GRATUITO)
        assinatura = Assinatura.objects.create(usuario=self.dono, plano=plano)
        ContratacaoEmpresaAdicional.objects.create(
            assinatura=assinatura, quantidade=2, valor_unitario=Decimal('50.00'),
            status=ContratacaoEmpresaAdicional.Status.ATIVA,
        )
        self.assertEqual(obter_limite_empresas(self.dono), 3)
        self.assertTrue(usuario_pode_criar_empresa(self.dono).permitido)

    def test_excluida_nao_conta_e_vinculo_nao_duplica(self):
        self.empresa.delete()
        self.assertEqual(total_empresas_ativas(self.dono), 0)


class VagaTests(BaseRecruitmentTests):
    def dados(self, empresa=None, **kwargs):
        dados = {'empresa': (empresa or self.empresa).pk, 'titulo': 'Analista', 'descricao': 'Descrição', 'tipo_contrato': 'CLT', 'modalidade': 'Presencial', 'quantidade': 1, 'cidade': 'Botucatu', 'estado': 'SP', 'status': Vaga.Status.RASCUNHO}
        dados.update(kwargs); return dados

    def test_empresa_autorizada_cria_e_terceira_bloqueia(self):
        self.client.force_login(self.dono)
        self.assertEqual(self.client.post(reverse('painel:vaga_criar'), self.dados()).status_code, 302)
        self.assertEqual(self.client.post(reverse('painel:vaga_criar'), self.dados(self.empresa_outro)).status_code, 200)

    def test_salario_e_datas_invalidos(self):
        with self.assertRaises(ValidationError):
            self.vaga(salario_minimo=200, salario_maximo=100)

    def test_datas_invalidas(self):
        with self.assertRaises(ValidationError): self.vaga(inicio=date.today(), encerramento=date.today()-timedelta(days=1))

    def test_publicidade_por_status(self):
        rascunho = self.vaga()
        self.assertEqual(self.client.get(reverse('recruitment_public:vaga', args=[rascunho.slug])).status_code, 404)
        rascunho.status = Vaga.Status.PUBLICADA; rascunho.save()
        self.assertEqual(self.client.get(reverse('recruitment_public:vaga', args=[rascunho.slug])).status_code, 200)

    def test_isolamento(self):
        vaga = self.vaga(); self.client.force_login(self.outro)
        self.assertEqual(self.client.get(reverse('painel:vaga_detalhe', args=[vaga.uuid])).status_code, 404)


class CurriculoCandidaturaTests(BaseRecruitmentTests):
    def setUp(self): self.curriculo = Curriculo.objects.create(usuario=self.dono, titulo_profissional='Dev')

    def test_um_curriculo_por_usuario(self):
        with self.assertRaises(IntegrityError), transaction.atomic(): Curriculo.objects.create(usuario=self.dono)

    def test_terceiro_nao_edita(self):
        self.client.force_login(self.outro); self.client.get(reverse('painel:curriculo'))
        self.assertFalse(Curriculo.objects.filter(usuario=self.outro).exists())

    def test_itens_curriculo(self):
        Experiencia.objects.create(curriculo=self.curriculo, titulo='Empresa', cargo='Dev')
        Formacao.objects.create(curriculo=self.curriculo, titulo='Curso superior')
        Curso.objects.create(curriculo=self.curriculo, titulo='Django')
        Habilidade.objects.create(curriculo=self.curriculo, nome='Python')
        Idioma.objects.create(curriculo=self.curriculo, nome='Português', nivel='Nativo')
        self.assertEqual(Experiencia.objects.filter(curriculo=self.curriculo).count(), 1)

    def test_curriculo_nao_possui_rota_publica(self):
        self.assertEqual(self.client.get(reverse('recruitment_public:curriculo', args=[self.curriculo.uuid])).status_code, 404)

    def test_candidatura_valida_duplicada_e_nao_publicada(self):
        vaga = self.vaga(status=Vaga.Status.PUBLICADA)
        Candidatura.objects.create(vaga=vaga, usuario=self.dono, curriculo=self.curriculo)
        with self.assertRaises(ValidationError): Candidatura.objects.create(vaga=self.vaga(), usuario=self.dono, curriculo=self.curriculo)
        with self.assertRaises(ValidationError): Candidatura.objects.create(vaga=vaga, usuario=self.dono, curriculo=self.curriculo)

    def test_curriculo_de_terceiro_bloqueado(self):
        vaga=self.vaga(status=Vaga.Status.PUBLICADA); outro=Curriculo.objects.create(usuario=self.outro)
        with self.assertRaises(ValidationError): Candidatura.objects.create(vaga=vaga, usuario=self.dono, curriculo=outro)

    def test_candidatura_sem_curriculo_publicado_abre_assistente(self):
        vaga = self.vaga(status=Vaga.Status.PUBLICADA)
        self.client.force_login(self.outro)
        response = self.client.get(reverse('recruitment_public:candidatar', args=[vaga.slug]))
        self.assertRedirects(response, reverse('painel:curriculo_novo'))
        self.assertEqual(self.client.session['candidatura_pendente_slug'], vaga.slug)

    def test_candidatura_com_curriculo_incompleto_retorna_a_etapa(self):
        vaga = self.vaga(status=Vaga.Status.PUBLICADA)
        self.curriculo.etapa_atual = 4
        self.curriculo.save(update_fields=['etapa_atual'])
        self.client.force_login(self.dono)
        response = self.client.get(reverse('recruitment_public:candidatar', args=[vaga.slug]))
        self.assertRedirects(response, reverse('painel:curriculo_formacoes'))

    def test_master_ve_empresas_vagas_curriculos_e_candidaturas(self):
        master, _ = garantir_usuario_master(email='master-recruitment@example.com', senha='SenhaSegura#2026')
        vaga = self.vaga(status=Vaga.Status.PUBLICADA)
        Candidatura.objects.create(vaga=vaga, usuario=self.dono, curriculo=self.curriculo)
        self.assertIn(self.empresa, empresas_disponiveis_para_usuario(master))
        self.assertNotIn(self.empresa_outro, empresas_disponiveis_para_usuario(self.dono))
        self.client.force_login(master)
        self.assertContains(self.client.get(reverse('painel:vagas_lista')), vaga.titulo)
        self.assertContains(self.client.get(reverse('admin:recruitment_curriculo_changelist')), self.curriculo.usuario.username)
        self.assertContains(self.client.get(reverse('admin:recruitment_candidatura_changelist')), vaga.titulo)


class CurriculumWizardTests(BaseRecruitmentTests):
    def setUp(self):
        self.curriculo = Curriculo.objects.create(usuario=self.dono)
        CurriculoPrivacidade.objects.create(curriculo=self.curriculo)
        self.client.force_login(self.dono)

    def test_get_does_not_create_curriculum(self):
        novo = get_user_model().objects.create_user('wizard_new', password='senha')
        self.client.force_login(novo)
        self.assertEqual(self.client.get(reverse('painel:curriculo')).status_code, 200)
        self.assertEqual(self.client.get(reverse('painel:curriculo_novo')).status_code, 200)
        self.assertFalse(Curriculo.objects.filter(usuario=novo).exists())

    def test_post_creates_curriculum(self):
        novo = get_user_model().objects.create_user('wizard_post', password='senha')
        self.client.force_login(novo)
        response = self.client.post(reverse('painel:curriculo_novo'), {
            'cidade': 'Botucatu', 'estado': 'SP',
            'email_publico': 'wizard@example.com',
        })
        self.assertRedirects(response, reverse('painel:curriculo_etapa', args=[2]))
        self.assertTrue(Curriculo.objects.filter(usuario=novo).exists())

    def test_steps_save_independently_and_preserve_data(self):
        self.client.post(reverse('painel:curriculo_etapa', args=[1]), {
            'cidade': 'Botucatu', 'estado': 'SP', 'email_publico': 'publico@example.com',
            'acao': 'continuar',
        })
        self.client.post(reverse('painel:curriculo_etapa', args=[2]), {
            'titulo_profissional': 'Desenvolvedor', 'area_profissional': 'Tecnologia',
            'resumo': 'Resumo salvo',
            'acao': 'rascunho',
        })
        self.curriculo.refresh_from_db()
        self.assertEqual(self.curriculo.titulo_profissional, 'Desenvolvedor')
        self.assertEqual(self.curriculo.cidade, 'Botucatu')

    def test_progress_is_calculated_by_service(self):
        self.curriculo.titulo_profissional = 'Dev'; self.curriculo.area_profissional = 'TI'; self.curriculo.resumo = 'Resumo'; self.curriculo.save()
        progress = calcular_progresso(self.curriculo)
        self.assertGreaterEqual(progress.percentual, 20)
        self.assertNotIn(3, progress.etapas_concluidas)

    def test_experience_crud_and_idor(self):
        self.client.post(reverse('painel:curriculo_experiencia_nova'), {'titulo': 'Empresa A', 'cargo': 'Dev', 'descricao': 'Atividades'})
        experience = Experiencia.objects.get(curriculo=self.curriculo)
        self.client.post(reverse('painel:curriculo_experiencia_editar', args=[experience.uuid]), {'titulo': 'Empresa A', 'cargo': 'Senior', 'descricao': 'Atividades'})
        experience.refresh_from_db(); self.assertEqual(experience.cargo, 'Senior')
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(reverse('painel:curriculo_experiencia_editar', args=[experience.uuid])).status_code, 404)
        self.client.force_login(self.dono)
        self.client.post(reverse('painel:curriculo_experiencia_remover', args=[experience.uuid]))
        self.assertFalse(Experiencia.objects.filter(pk=experience.pk).exists())

    def test_auxiliary_records_and_case_insensitive_uniqueness(self):
        Formacao.objects.create(curriculo=self.curriculo, titulo='Graduação')
        Curso.objects.create(curriculo=self.curriculo, titulo='Django')
        Projeto.objects.create(curriculo=self.curriculo, titulo='Projeto')
        Habilidade.objects.create(curriculo=self.curriculo, nome='Python')
        Idioma.objects.create(curriculo=self.curriculo, nome='Português', nivel='Nativo')
        with self.assertRaises(IntegrityError), transaction.atomic(): Habilidade.objects.create(curriculo=self.curriculo, nome='python')
        with self.assertRaises(IntegrityError), transaction.atomic(): Idioma.objects.create(curriculo=self.curriculo, nome='português', nivel='Básico')

    def test_public_visibility_and_sanitized_dto(self):
        self.dono.cpf = '12345678901'; self.dono.email = 'privado@example.com'; self.dono.save()
        self.curriculo.titulo_profissional = 'Dev'; self.curriculo.area_profissional = 'TI'; self.curriculo.resumo = 'Resumo'
        self.curriculo.status = Curriculo.Status.CONCLUIDO; self.curriculo.visibilidade = Curriculo.Visibilidade.CANDIDATURAS; self.curriculo.save()
        self.assertIsNone(curriculo_publico(self.curriculo))
        self.curriculo.visibilidade = Curriculo.Visibilidade.PUBLICO; self.curriculo.save()
        serialized = str(curriculo_publico(self.curriculo).serializar())
        self.assertNotIn('12345678901', serialized); self.assertNotIn('privado@example.com', serialized)
        self.assertEqual(self.client.get(reverse('recruitment_public:curriculo', args=[self.curriculo.uuid])).status_code, 200)

    def test_application_snapshot_is_immutable_and_consented(self):
        vacancy = self.vaga(status=Vaga.Status.PUBLICADA)
        self.curriculo.titulo_profissional = 'Versão enviada'; self.curriculo.save()
        application = Candidatura.objects.create(vaga=vacancy, usuario=self.dono, curriculo=self.curriculo)
        application.refresh_from_db()
        snapshot = application.curriculo_snapshot
        self.assertIsNotNone(application.consentimento_compartilhamento_em)
        self.curriculo.titulo_profissional = 'Versão posterior'; self.curriculo.save()
        application.status = Candidatura.Status.EM_ANALISE; application.save(); application.refresh_from_db()
        self.assertEqual(application.curriculo_snapshot, snapshot)
        self.assertEqual(snapshot['titulo_profissional'], 'Versão enviada')

    def test_required_routes_and_back_buttons(self):
        for route, args in (('painel:curriculo', ()), ('painel:curriculo_etapa', (1,)), ('painel:curriculo_visualizar', ())):
            response = self.client.get(reverse(route, args=args))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Voltar')

    def test_all_item_lists_render_their_own_fields(self):
        Experiencia.objects.create(curriculo=self.curriculo, titulo='Empresa A', cargo='Pessoa desenvolvedora')
        Formacao.objects.create(curriculo=self.curriculo, titulo='Sistemas', instituicao='Faculdade A', nivel='Superior')
        Curso.objects.create(curriculo=self.curriculo, titulo='Django', instituicao='Escola A', carga_horaria=20)
        Habilidade.objects.create(curriculo=self.curriculo, nome='Python', nivel='Avançado', categoria='Tecnologia')
        Idioma.objects.create(curriculo=self.curriculo, nome='Inglês', nivel='Intermediário')
        Projeto.objects.create(curriculo=self.curriculo, titulo='Portal', descricao='Projeto de portfólio')
        expected = (
            ('painel:curriculo_experiencias', 'Pessoa desenvolvedora'),
            ('painel:curriculo_formacoes', 'Faculdade A'),
            ('painel:curriculo_cursos', '20 horas'),
            ('painel:curriculo_habilidades', 'Tecnologia'),
            ('painel:curriculo_idiomas', 'Intermediário'),
            ('painel:curriculo_projetos', 'Projeto de portfólio'),
        )
        for route, text in expected:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, text)

    def test_save_and_continue_uses_the_next_stage_for_every_item_type(self):
        cases = (
            ('painel:curriculo_experiencia_nova', {'titulo': 'Empresa', 'cargo': 'Dev'}, 'painel:curriculo_formacoes', ()),
            ('painel:curriculo_formacao_nova', {'titulo': 'Graduação'}, 'painel:curriculo_cursos', ()),
            ('painel:curriculo_curso_novo', {'tipo': Curso.Tipo.CURSO, 'titulo': 'Django'}, 'painel:curriculo_habilidades', ()),
            ('painel:curriculo_habilidade_nova', {'nome': 'Python'}, 'painel:curriculo_idiomas', ()),
            ('painel:curriculo_idioma_novo', {'nome': 'Inglês', 'nivel': 'Básico'}, 'painel:curriculo_projetos', ()),
            ('painel:curriculo_projeto_novo', {'titulo': 'Portal'}, 'painel:curriculo_etapa', (9,)),
        )
        for route, data, next_route, args in cases:
            with self.subTest(route=route):
                response = self.client.post(reverse(route), {**data, 'acao': 'continuar'})
                self.assertRedirects(response, reverse(next_route, args=args))

    def test_save_returns_to_list_and_cancel_is_available(self):
        response = self.client.post(reverse('painel:curriculo_habilidade_nova'), {
            'nome': 'Comunicação', 'acao': 'salvar',
        })
        self.assertRedirects(response, reverse('painel:curriculo_habilidades'))
        response = self.client.get(reverse('painel:curriculo_habilidade_nova'))
        self.assertContains(response, 'Cancelar')
        self.assertContains(response, 'Salvar e continuar')

    def test_current_experience_rejects_an_end_date(self):
        response = self.client.post(reverse('painel:curriculo_experiencia_nova'), {
            'titulo': 'Empresa', 'cargo': 'Dev', 'atual': 'on',
            'fim': date.today().isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Uma experiência atual não pode ter data final.')
        self.assertFalse(Experiencia.objects.filter(curriculo=self.curriculo).exists())

    def test_privacy_get_does_not_persist_configuration(self):
        CurriculoPrivacidade.all_objects.filter(curriculo=self.curriculo).delete()
        self.assertEqual(self.client.get(reverse('painel:curriculo_etapa', args=[10])).status_code, 200)
        self.assertFalse(CurriculoPrivacidade.objects.filter(curriculo=self.curriculo).exists())

    def test_invalid_steps_and_foreign_uuids_are_safe(self):
        self.assertEqual(self.client.get(reverse('painel:curriculo_etapa', args=[11])).status_code, 404)
        foreign_curriculum = Curriculo.objects.create(usuario=self.outro)
        foreign_item = Projeto.objects.create(curriculo=foreign_curriculum, titulo='Privado')
        self.assertEqual(
            self.client.get(reverse('painel:curriculo_projeto_editar', args=[foreign_item.uuid])).status_code,
            404,
        )

    def test_all_ten_steps_show_context_description_and_current_indicator(self):
        routes = (
            ('painel:curriculo_etapa', (1,), 'Dados pessoais'),
            ('painel:curriculo_etapa', (2,), 'Objetivo profissional'),
            ('painel:curriculo_experiencias', (), 'Experiências'),
            ('painel:curriculo_formacoes', (), 'Formação acadêmica'),
            ('painel:curriculo_cursos', (), 'Cursos e certificações'),
            ('painel:curriculo_habilidades', (), 'Habilidades'),
            ('painel:curriculo_idiomas', (), 'Idiomas'),
            ('painel:curriculo_projetos', (), 'Projetos'),
            ('painel:curriculo_etapa', (9,), 'Informações adicionais'),
            ('painel:curriculo_etapa', (10,), 'Privacidade e publicação'),
        )
        descriptions = set()
        for number, (route, args, title) in enumerate(routes, start=1):
            with self.subTest(step=number):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Painel')
                self.assertContains(response, 'Currículo')
                self.assertContains(response, title)
                self.assertContains(response, f'Etapa {number} de 10')
                self.assertContains(response, 'aria-current="step"', html=False)
                self.assertTrue(response.context['descricao'])
                descriptions.add(response.context['descricao'])
        self.assertEqual(len(descriptions), 10)

    def test_stage_footers_keep_consistent_actions(self):
        simple = self.client.get(reverse('painel:curriculo_etapa', args=[2]))
        item_form = self.client.get(reverse('painel:curriculo_experiencia_nova'))
        for response in (simple, item_form):
            with self.subTest(path=response.request['PATH_INFO']):
                self.assertContains(response, 'Voltar')
                self.assertContains(response, 'Cancelar')
                self.assertContains(response, '>Salvar<', html=False)
                self.assertContains(response, 'Salvar e continuar')
