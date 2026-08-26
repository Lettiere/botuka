from datetime import datetime, time, timedelta
from threading import Barrier, Lock, Thread

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import Client, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import (
    Agendamento,
    AgendaBloqueio,
    AgendaDisponibilidade,
    AgendaProfissional,
    AgendaProfissionalServico,
)
from apps.agenda.public_services import (
    cancelar_agendamento_cliente,
    criar_agendamento_publico,
    gerar_slots,
    nome_publico_profissional,
    servicos_agendaveis,
    vinculos_agendaveis,
)
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import Empresa, EmpresaCapacidade, EmpresaUsuario
from apps.services.models import (
    AreaProfissional, FormaCobranca, Profissao, ProfissaoTipoServico,
    Servico, Setor, TipoServico,
)

from . import test_operacao


class AgendaPublicaTests(test_operacao.AgendaOperacaoTests):
    def setUp(self):
        self.http = Client(HTTP_HOST='127.0.0.1')

    def _slots(self, vinculo=None, data=None, agora=None):
        vinculo = vinculo or self.vinculo_a
        data = data or self.inicio.date()
        return gerar_slots(vinculo, data, agora=agora)

    def _criar(self, inicio=None, cliente=None):
        return criar_agendamento_publico(
            vinculo_uuid=self.vinculo_a.uuid,
            cliente=cliente or self.cliente,
            inicio=inicio or self.inicio,
        )

    def test_empresa_com_agenda_e_cta_publico(self):
        response = self.http.get(reverse(
            'agenda_public:empresa', args=[self.empresa_a.slug]
        ))
        perfil = self.http.get(reverse('publico:empresa', args=[self.empresa_a.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.servico_a.titulo)
        self.assertContains(perfil, 'Agendar horário')

    def test_empresa_sem_agenda_nao_oferece_servico(self):
        EmpresaCapacidade.objects.filter(
            empresa=self.empresa_a,
            capacidade__codigo='ACEITAR_AGENDAMENTOS',
        ).update(ativo=False)
        response = self.http.get(reverse(
            'agenda_public:empresa', args=[self.empresa_a.slug]
        ))
        self.assertContains(response, 'temporariamente indisponível')
        self.assertFalse(servicos_agendaveis(self.empresa_a).exists())

    def test_servico_sem_vinculo_e_vinculo_inativo(self):
        outro = self._servico(self.owner_a, self.empresa_a, 'Sem vínculo público')
        response = self.http.get(reverse(
            'agenda_public:servico', args=[self.empresa_a.slug, outro.slug]
        ))
        self.assertContains(response, 'sem agenda disponível')
        AgendaProfissionalServico.objects.filter(pk=self.vinculo_a.pk).update(ativo=False)
        self.assertEqual(vinculos_agendaveis(servico=self.servico_a), [])

    def test_profissional_ou_membro_inativo_nao_aparece(self):
        AgendaProfissional.objects.filter(pk=self.prof_a.pk).update(ativo=False)
        self.assertEqual(vinculos_agendaveis(servico=self.servico_a), [])
        AgendaProfissional.objects.filter(pk=self.prof_a.pk).update(ativo=True)
        EmpresaUsuario.objects.filter(pk=self.eu_a.pk).update(ativo=False)
        self.assertEqual(vinculos_agendaveis(servico=self.servico_a), [])

    def test_profissional_unico_e_multiplos_profissionais(self):
        response = self.http.get(reverse(
            'agenda_public:servico', args=[self.empresa_a.slug, self.servico_a.slug]
        ))
        self.assertEqual(len(response.context['profissionais']), 1)
        outro_usuario = get_user_model().objects.create_user(
            'outro-publico', 'outro-publico@example.com', 'senha'
        )
        eu = EmpresaUsuario.objects.create(
            empresa=self.empresa_a, usuario=outro_usuario, ativo=True
        )
        profissional = AgendaProfissional.objects.create(empresa_usuario=eu)
        AgendaProfissionalServico.objects.create(
            profissional=profissional, servico=self.servico_a, duracao_minutos=30
        )
        response = self.http.get(reverse(
            'agenda_public:servico', args=[self.empresa_a.slug, self.servico_a.slug]
        ))
        self.assertEqual(len(response.context['profissionais']), 2)

    def test_uma_disponibilidade_e_fronteiras(self):
        slots = self._slots()
        self.assertEqual(slots[0].time(), time(8))
        self.assertEqual(slots[-1].time(), time(17))
        self.assertTrue(all(slot + timedelta(minutes=60) <= timezone.make_aware(
            datetime.combine(self.inicio.date(), time(18))
        ) for slot in slots))

    def test_multiplas_disponibilidades_nao_cruzam_intervalo(self):
        AgendaDisponibilidade.objects.filter(pk=self.disponibilidade_a.pk).update(
            hora_fim=time(12)
        )
        AgendaDisponibilidade.objects.create(
            profissional=self.prof_a, dia_semana=0,
            hora_inicio=time(13), hora_fim=time(15),
        )
        horas = [slot.time() for slot in self._slots()]
        self.assertIn(time(11), horas)
        self.assertIn(time(13), horas)
        self.assertNotIn(time(12), horas)

    def test_duracao_por_vinculo_e_slot_que_ultrapassa_fim(self):
        AgendaProfissionalServico.objects.filter(pk=self.vinculo_a.pk).update(
            duracao_minutos=90
        )
        self.vinculo_a.refresh_from_db()
        horas = [slot.time() for slot in self._slots()]
        self.assertEqual(horas[:3], [time(8), time(9, 30), time(11)])
        self.assertEqual(horas[-1], time(15, 30))

    def test_bloqueio_parcial_total_e_fronteira(self):
        AgendaBloqueio.objects.create(
            profissional=self.prof_a, tipo=AgendaBloqueio.Tipo.OUTRO,
            inicio=self.inicio, fim=self.inicio + timedelta(hours=1),
        )
        horas = [slot.time() for slot in self._slots()]
        self.assertNotIn(time(10), horas)
        self.assertIn(time(9), horas)
        self.assertIn(time(11), horas)
        AgendaBloqueio.objects.create(
            profissional=self.prof_a, tipo=AgendaBloqueio.Tipo.OUTRO,
            inicio=self.inicio.replace(hour=8), fim=self.inicio.replace(hour=18),
        )
        self.assertEqual(self._slots(), [])

    def test_status_ocupantes_e_cancelado_libera(self):
        item = self._agendamento(Agendamento.Status.PENDENTE)
        self.assertNotIn(self.inicio, self._slots())
        Agendamento.objects.filter(pk=item.pk).update(status=Agendamento.Status.CONFIRMADO)
        self.assertNotIn(self.inicio, self._slots())
        Agendamento.objects.filter(pk=item.pk).update(status=Agendamento.Status.CANCELADO)
        self.assertIn(self.inicio, self._slots())

    def test_concluido_e_faltou_seguem_regra_do_model(self):
        item = self._agendamento(Agendamento.Status.CONCLUIDO)
        self.assertIn(self.inicio, self._slots())
        Agendamento.objects.filter(pk=item.pk).update(status=Agendamento.Status.FALTOU)
        self.assertIn(self.inicio, self._slots())

    def test_data_passada_e_horario_passado_hoje(self):
        passado = timezone.localdate() - timedelta(days=7)
        self.assertEqual(self._slots(data=passado), [])
        agora = self.inicio.replace(hour=12, minute=30)
        horas = [slot.time() for slot in self._slots(agora=agora)]
        self.assertNotIn(time(12), horas)
        self.assertIn(time(13), horas)

    def test_timezone_sao_paulo_e_inicio_aware(self):
        slot = self._slots()[0]
        self.assertTrue(timezone.is_aware(slot))
        self.assertEqual(str(slot.tzinfo), 'America/Sao_Paulo')

    def test_usuario_anonimo_consulta_slots(self):
        response = self.http.get(reverse(
            'agenda_public:slots', args=[self.vinculo_a.uuid]
        ), {'data': self.inicio.date().isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['slots'])

    def test_anonimo_nao_confirma_e_login_preserva_next(self):
        url = reverse('agenda_public:confirmar', args=[self.vinculo_a.uuid])
        response = self.http.post(url, {'inicio': self.inicio.isoformat()})
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response.url)
        login_email = 'login-agenda@example.com'
        get_user_model().objects.create_user(
            login_email, login_email, 'senha-forte'
        )
        response = self.http.post(reverse('accounts:login'), {
            'email': login_email,
            'password': 'senha-forte',
            'next': '/meus-agendamentos/',
        })
        self.assertEqual(response.url, '/meus-agendamentos/')

    def test_cadastro_retorna_destino_local_e_rejeita_externo(self):
        dados = {
            'nome': 'Novo Cliente', 'email': 'novo-agenda@example.com',
            'password': 'senha-forte', 'password_confirm': 'senha-forte',
            'next': '/meus-agendamentos/',
        }
        response = self.http.post(reverse('accounts:cadastro'), dados)
        self.assertEqual(response.url, '/meus-agendamentos/')
        dados.update(email='outro-agenda@example.com', next='https://evil.example/')
        response = Client(HTTP_HOST='127.0.0.1').post(
            reverse('accounts:cadastro'), dados
        )
        self.assertNotEqual(response.url, 'https://evil.example/')

    def test_criacao_autenticada_controla_cliente_fim_status(self):
        item = self._criar()
        self.assertEqual(item.cliente, self.cliente)
        self.assertEqual(item.status, Agendamento.Status.PENDENTE)
        self.assertEqual(item.fim - item.inicio, timedelta(minutes=60))

    def test_post_http_ignora_campos_adulterados(self):
        self.http.force_login(self.cliente)
        response = self.http.post(reverse(
            'agenda_public:confirmar', args=[self.vinculo_a.uuid]
        ), {
            'inicio': self.inicio.isoformat(), 'cliente': self.owner_b.pk,
            'fim': (self.inicio + timedelta(days=1)).isoformat(),
            'status': Agendamento.Status.CONCLUIDO, 'duracao': 999,
        })
        self.assertEqual(response.status_code, 302)
        item = Agendamento.objects.get(cliente=self.cliente)
        self.assertEqual(item.status, Agendamento.Status.PENDENTE)
        self.assertEqual(item.fim - item.inicio, timedelta(minutes=60))

    def test_vinculo_servico_profissional_externos_rejeitados(self):
        response = self.http.get(reverse(
            'agenda_public:slots', args=[self.prof_b.uuid]
        ), {'data': self.inicio.date().isoformat()})
        self.assertEqual(response.status_code, 404)
        response = self.http.get(reverse(
            'agenda_public:servico', args=[self.empresa_a.slug, self.servico_b.slug]
        ))
        self.assertEqual(response.status_code, 404)

    def test_idor_detalhe_e_cancelamento(self):
        item = self._criar()
        self.http.force_login(self.owner_b)
        detalhe = self.http.get(reverse(
            'agenda_public:meu_agendamento', args=[item.uuid]
        ))
        cancelar = self.http.post(reverse(
            'agenda_public:cancelar', args=[item.uuid]
        ))
        self.assertEqual(detalhe.status_code, 404)
        item.refresh_from_db()
        self.assertEqual(item.status, Agendamento.Status.PENDENTE)
        self.assertEqual(cancelar.status_code, 404)

    def test_cancelamento_permitido_e_invalido(self):
        item = self._criar()
        cancelar_agendamento_cliente(
            agendamento_uuid=item.uuid, cliente=self.cliente
        )
        item.refresh_from_db()
        self.assertEqual(item.status, Agendamento.Status.CANCELADO)
        with self.assertRaises(ValidationError):
            cancelar_agendamento_cliente(
                agendamento_uuid=item.uuid, cliente=self.cliente
            )

    def test_revalidacao_e_double_booking(self):
        primeiro = self._criar()
        with self.assertRaises(ValidationError):
            self._criar()
        self.assertEqual(Agendamento.objects.filter(
            profissional_servico__profissional=self.prof_a,
            status__in=(Agendamento.Status.PENDENTE, Agendamento.Status.CONFIRMADO),
            inicio=self.inicio,
        ).count(), 1)
        self.assertEqual(primeiro.status, Agendamento.Status.PENDENTE)

    def test_capacidade_revogada_antes_da_confirmacao(self):
        EmpresaCapacidade.objects.filter(
            empresa=self.empresa_a,
            capacidade__codigo='ACEITAR_AGENDAMENTOS',
        ).update(ativo=False)
        with self.assertRaises(ValidationError):
            self._criar()
        self.assertFalse(Agendamento.objects.filter(cliente=self.cliente).exists())

    def test_area_cliente_lista_detalhe_e_uuid(self):
        item = self._criar()
        self.http.force_login(self.cliente)
        lista = self.http.get(reverse('agenda_public:meus_agendamentos'))
        detalhe = self.http.get(reverse(
            'agenda_public:meu_agendamento', args=[item.uuid]
        ))
        self.assertContains(lista, self.servico_a.titulo)
        self.assertEqual(detalhe.status_code, 200)

    def test_nome_publico_nao_expoe_email(self):
        self.membro_a.nome_exibicao = ''
        self.membro_a.first_name = ''
        self.membro_a.last_name = ''
        self.membro_a.save()
        nome = nome_publico_profissional(self.prof_a)
        self.assertEqual(nome, 'Profissional')
        self.assertNotIn('@', nome)


class AgendaConcorrenciaTests(TransactionTestCase):
    reset_sequences = False

    def _limpar_fixture(self):
        Agendamento.objects.all().delete()
        AgendaBloqueio.objects.all().delete()
        AgendaDisponibilidade.objects.all().delete()
        AgendaProfissionalServico.objects.all().delete()
        AgendaProfissional.objects.all().delete()
        Servico.all_objects.filter(titulo__contains='Serviço Agenda').delete()
        EmpresaCapacidade.objects.filter(
            empresa__nome_fantasia__contains='Empresa Agenda'
        ).delete()
        EmpresaUsuario.objects.filter(
            empresa__nome_fantasia__contains='Empresa Agenda'
        ).delete()
        Empresa.all_objects.filter(nome_fantasia__contains='Empresa Agenda').delete()
        ProfissaoTipoServico.objects.filter(
            profissao__nome='Profissão Agenda'
        ).delete()
        TipoServico.objects.filter(nome='Tipo Agenda').delete()
        Profissao.objects.filter(nome='Profissão Agenda').delete()
        AreaProfissional.objects.filter(nome='Área Agenda').delete()
        Setor.objects.filter(nome='Setor Agenda').delete()
        FormaCobranca.objects.filter(nome='Cobrança Agenda').delete()
        Cidade.all_objects.filter(nome='Cidade Agenda')._raw_delete('default')
        Estado.all_objects.filter(nome='Estado Agenda')._raw_delete('default')
        Pais.all_objects.filter(nome='Brasil Agenda')._raw_delete('default')
        get_user_model().objects.filter(
            username__in=('owner-a', 'owner-b', 'membro-a', 'membro-b', 'cliente-agenda')
        ).delete()

    def setUp(self):
        self._limpar_fixture()
        test_operacao.AgendaOperacaoTests.setUpTestData()
        self.vinculo = test_operacao.AgendaOperacaoTests.vinculo_a
        self.cliente = test_operacao.AgendaOperacaoTests.cliente
        self.inicio = test_operacao.AgendaOperacaoTests.inicio

    def _fixture_teardown(self):
        self._limpar_fixture()

    def test_duas_requisicoes_concorrentes_criam_apenas_uma_reserva(self):
        barreira = Barrier(2)
        trava = Lock()
        resultados = []

        def reservar():
            close_old_connections()
            barreira.wait()
            try:
                item = criar_agendamento_publico(
                    vinculo_uuid=self.vinculo.uuid,
                    cliente=get_user_model().objects.get(pk=self.cliente.pk),
                    inicio=self.inicio,
                )
            except ValidationError:
                resultado = 'rejeitado'
            else:
                resultado = f'criado:{item.pk}'
            finally:
                close_old_connections()
            with trava:
                resultados.append(resultado)

        threads = [Thread(target=reservar), Thread(target=reservar)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sum(item.startswith('criado:') for item in resultados), 1)
        self.assertEqual(resultados.count('rejeitado'), 1)
        self.assertEqual(Agendamento.objects.filter(
            profissional_servico__profissional=self.vinculo.profissional,
            status__in=(Agendamento.Status.PENDENTE, Agendamento.Status.CONFIRMADO),
            inicio=self.inicio,
        ).count(), 1)
