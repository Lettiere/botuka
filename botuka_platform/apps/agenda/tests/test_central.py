from datetime import datetime, time, timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import (
    Agendamento,
    AgendaEmpresa,
    AgendaBloqueio,
    AgendaDisponibilidade,
    AgendaDisponibilidadeData,
    AgendaFuncionamentoEmpresa,
    AgendaProfissional,
    AgendaProfissionalServico,
    AgendamentoHistorico,
)
from apps.locations.models import Cidade, Estado, Pais
from apps.organizations.models import (
    Capacidade,
    Empresa,
    EmpresaCapacidade,
    EmpresaUsuario,
)
from apps.services.models import (
    AreaProfissional,
    FormaCobranca,
    Profissao,
    Servico,
    Setor,
)


class CentralAgendaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.gestor = Usuario.objects.create_user('central-gestor', password='senha-forte')
        cls.outro = Usuario.objects.create_user('central-outro', password='senha-forte')
        cls.membro = Usuario.objects.create_user('central-membro', password='senha-forte')
        cls.cliente = Usuario.objects.create_user(
            'central-cliente', email='central-cliente@example.com', password='senha-forte',
        )
        pais = Pais.objects.create(nome='Brasil Central', codigo_iso_2='BC', codigo_iso_3='BCT')
        estado = Estado.objects.create(pais=pais, nome='Estado Central', sigla='CT')
        cidade = Cidade.objects.create(estado=estado, nome='Cidade Central')
        cls.empresa = Empresa.objects.create(
            usuario_proprietario=cls.gestor,
            nome_fantasia='Empresa Central',
            atuacao=Empresa.Atuacao.SERVICOS,
            status=Empresa.Status.ATIVA,
            perfil_publico=True,
            cidade=cidade,
            estado=estado,
        )
        cls.empresa_alheia = Empresa.objects.create(
            usuario_proprietario=cls.outro,
            nome_fantasia='Empresa Alheia',
            atuacao=Empresa.Atuacao.SERVICOS,
            status=Empresa.Status.ATIVA,
            perfil_publico=True,
            cidade=cidade,
            estado=estado,
        )
        for empresa in (cls.empresa, cls.empresa_alheia):
            for codigo in ('PRESTAR_SERVICOS', 'ACEITAR_AGENDAMENTOS'):
                capacidade, _ = Capacidade.objects.get_or_create(
                    codigo=codigo, defaults={'nome': codigo},
                )
                EmpresaCapacidade.objects.update_or_create(
                    empresa=empresa,
                    capacidade=capacidade,
                    defaults={'status': EmpresaCapacidade.Status.APROVADA, 'ativo': True},
                )
        membro_empresa = EmpresaUsuario.objects.create(
            empresa=cls.empresa, usuario=cls.membro, ativo=True,
        )
        cls.profissional = AgendaProfissional.objects.create(
            empresa_usuario=membro_empresa,
        )
        setor = Setor.objects.create(nome='Setor Central')
        area = AreaProfissional.objects.create(setor=setor, nome='Área Central')
        profissao = Profissao.objects.create(
            setor=setor, area=area, nome='Profissão Central',
        )
        cobranca = FormaCobranca.objects.create(nome='Cobrança Central')
        cls.servico = Servico.objects.create(
            usuario_responsavel=cls.gestor,
            empresa=cls.empresa,
            prestador_tipo=Servico.PrestadorTipo.EMPRESA,
            setor=setor,
            area=area,
            profissao=profissao,
            forma_cobranca=cobranca,
            titulo='Serviço Central',
            status=Servico.Status.PUBLICADO,
        )
        cls.vinculo = AgendaProfissionalServico.objects.create(
            profissional=cls.profissional,
            servico=cls.servico,
            duracao_minutos=60,
        )
        data = timezone.localdate() + timedelta(days=2)
        AgendaDisponibilidade.objects.create(
            profissional=cls.profissional,
            dia_semana=data.weekday(),
            hora_inicio=time(8),
            hora_fim=time(18),
        )
        inicio = timezone.make_aware(datetime.combine(data, time(10)))
        cls.agendamento = Agendamento.objects.create(
            profissional_servico=cls.vinculo,
            cliente=cls.cliente,
            inicio=inicio,
            fim=inicio + timedelta(hours=1),
        )

    def setUp(self):
        self.client.force_login(self.gestor)
        self.url = reverse('painel:empresa_agenda', kwargs={'uuid': self.empresa.uuid})

    def test_gestor_autorizado_acessa_central(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Configure sua agenda')
        self.assertContains(response, 'Quem atende')
        self.assertNotContains(response, 'ACEITAR_AGENDAMENTOS')
        self.assertNotContains(response, 'PRESTAR_SERVICOS')

    def test_usuario_de_outra_empresa_nao_acessa(self):
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_empresa_inexistente_retorna_404(self):
        url = reverse('painel:empresa_agenda', kwargs={'uuid': uuid4()})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_central_calcula_profissionais(self):
        central = self.client.get(self.url).context['central']
        self.assertEqual(central['profissionais_total'], 1)
        self.assertEqual(central['profissionais_ativos'], 1)

    def test_central_calcula_servicos_e_vinculos(self):
        central = self.client.get(self.url).context['central']
        self.assertEqual(central['servicos_publicados'], 1)
        self.assertEqual(central['servicos_vinculados'], 1)
        self.assertEqual(central['vinculos_ativos'], 1)

    def test_central_calcula_proximos_agendamentos(self):
        central = self.client.get(self.url).context['central']
        self.assertEqual(central['proximos_total'], 1)
        self.assertEqual(list(central['proximos']), [self.agendamento])

    def test_checklist_identifica_configuracao_incompleta(self):
        AgendaDisponibilidade.objects.filter(profissional=self.profissional).update(ativo=False)
        central = self.client.get(self.url).context['central']
        item = next(item for item in central['checklist'] if item['rotulo'].startswith('Horário'))
        self.assertFalse(item['ok'])
        self.assertEqual(central['estado'], 'PENDENTE DE CONFIGURAÇÃO')

    def test_card_empresa_aponta_para_gerenciar_agenda(self):
        response = self.client.get(reverse(
            'painel:empresa_detalhe', kwargs={'uuid': self.empresa.uuid},
        ))
        self.assertContains(response, 'Gerenciar Agenda')
        self.assertContains(response, self.url)
        self.assertContains(response, 'Serviços vinculados')

    def test_capacidades_pendentes_nao_provocam_erro(self):
        self.empresa.capacidades_empresa.update(
            status=EmpresaCapacidade.Status.PENDENTE,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['central']['estado'], 'PENDENTE DE AUTORIZAÇÃO')

    def test_central_nao_vaza_dados_de_outra_empresa(self):
        outro_membro = EmpresaUsuario.objects.create(
            empresa=self.empresa_alheia, usuario=self.outro, ativo=True,
        )
        AgendaProfissional.objects.create(empresa_usuario=outro_membro)
        response = self.client.get(self.url)
        self.assertNotContains(response, 'Empresa Alheia')
        self.assertEqual(response.context['central']['profissionais_total'], 1)

    def test_links_operacionais_existentes_continuam_validos(self):
        central = self.client.get(self.url).context['central']
        for chave in ('calendario', 'bloqueios', 'agendamentos'):
            response = self.client.get(central['urls'][chave])
            self.assertEqual(response.status_code, 200, chave)

    def test_pagina_funciona_sem_profissionais(self):
        Agendamento.objects.filter(pk=self.agendamento.pk).delete()
        AgendaProfissional.objects.filter(pk=self.profissional.pk).delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['central']['profissionais_total'], 0)

    def test_pagina_funciona_sem_servicos(self):
        Agendamento.objects.filter(pk=self.agendamento.pk).delete()
        AgendaProfissionalServico.objects.filter(pk=self.vinculo.pk).delete()
        Servico.all_objects.filter(pk=self.servico.pk).delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['central']['servicos_publicados'], 0)

    def test_pagina_funciona_sem_agendamentos(self):
        Agendamento.objects.filter(pk=self.agendamento.pk).delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['central']['proximos_total'], 0)

    def test_horarios_separa_semanais_e_excecoes(self):
        AgendaDisponibilidadeData.objects.create(
            profissional=self.profissional,
            data=timezone.localdate() + timedelta(days=5),
            hora_inicio=time(13), hora_fim=time(17),
        )
        response = self.client.get(reverse(
            'painel:agenda_horarios', kwargs={'uuid': self.empresa.uuid},
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Horários de cada semana')
        self.assertContains(response, 'Horário diferente neste dia')
        self.assertEqual(response.context['semanais'].count(), 1)
        self.assertEqual(response.context['excecoes'].count(), 1)

    def test_copia_horarios_de_segunda_para_dias_escolhidos(self):
        AgendaDisponibilidade.objects.filter(profissional=self.profissional).delete()
        AgendaDisponibilidade.objects.create(
            profissional=self.profissional,
            dia_semana=AgendaDisponibilidade.DiaSemana.SEGUNDA,
            hora_inicio=time(8), hora_fim=time(12),
        )
        response = self.client.post(reverse(
            'painel:agenda_horarios', kwargs={'uuid': self.empresa.uuid},
        ), {
            'acao': 'copiar_segunda',
            'profissional': self.profissional.pk,
            'dias': [AgendaDisponibilidade.DiaSemana.TERCA,
                     AgendaDisponibilidade.DiaSemana.QUARTA],
        })
        self.assertEqual(response.status_code, 302)
        copiados = AgendaDisponibilidade.objects.filter(
            profissional=self.profissional,
            dia_semana__in=(1, 2), hora_inicio=time(8), hora_fim=time(12),
        )
        self.assertEqual(copiados.count(), 2)

    def test_cria_edita_e_desativa_horario_semanal(self):
        criar = reverse('painel:agenda_horario_semanal_criar', kwargs={
            'uuid': self.empresa.uuid,
        })
        response = self.client.post(criar, {
            'profissional': self.profissional.pk,
            'dia_semana': 6,
            'hora_inicio': '09:00',
            'hora_fim': '12:00',
        })
        self.assertRedirects(response, reverse(
            'painel:agenda_horarios', kwargs={'uuid': self.empresa.uuid},
        ))
        item = AgendaDisponibilidade.objects.get(
            profissional=self.profissional, dia_semana=6,
        )
        editar = reverse('painel:agenda_horario_semanal_editar', kwargs={
            'uuid': self.empresa.uuid, 'pk': item.pk,
        })
        self.client.post(editar, {
            'profissional': self.profissional.pk,
            'dia_semana': 6,
            'hora_inicio': '10:00',
            'hora_fim': '13:00',
        })
        item.refresh_from_db()
        self.assertEqual(item.hora_inicio, time(10))
        status = reverse('painel:agenda_horario_semanal_status', kwargs={
            'uuid': self.empresa.uuid, 'pk': item.pk,
        })
        self.client.post(status, {'ativo': '0'})
        item.refresh_from_db()
        self.assertFalse(item.ativo)

    def test_horario_semanal_rejeita_intervalo_e_sobreposicao(self):
        existente = AgendaDisponibilidade.objects.get(profissional=self.profissional)
        url = reverse('painel:agenda_horario_semanal_criar', kwargs={'uuid': self.empresa.uuid})
        invalido = self.client.post(url, {
            'profissional': self.profissional.pk,
            'dia_semana': 5, 'hora_inicio': '18:00', 'hora_fim': '08:00',
        })
        self.assertEqual(invalido.status_code, 200)
        self.assertContains(invalido, 'horário final deve ser posterior', html=False)
        sobreposto = self.client.post(url, {
            'profissional': self.profissional.pk,
            'dia_semana': existente.dia_semana,
            'hora_inicio': '09:00', 'hora_fim': '12:00',
        })
        self.assertEqual(sobreposto.status_code, 200)
        self.assertContains(sobreposto, 'conflitante')

    def test_horario_semanal_respeita_funcionamento_empresarial(self):
        AgendaFuncionamentoEmpresa.objects.create(
            empresa=self.empresa, dia_semana=5,
            hora_inicio=time(9), hora_fim=time(12),
        )
        response = self.client.post(reverse(
            'painel:agenda_horario_semanal_criar', kwargs={'uuid': self.empresa.uuid},
        ), {
            'profissional': self.profissional.pk,
            'dia_semana': 5, 'hora_inicio': '08:00', 'hora_fim': '13:00',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'funcionamento da empresa')

    def test_horario_semanal_impede_idor(self):
        membro = EmpresaUsuario.objects.create(
            empresa=self.empresa_alheia, usuario=self.outro, ativo=True,
        )
        profissional = AgendaProfissional.objects.create(empresa_usuario=membro)
        item = AgendaDisponibilidade.objects.create(
            profissional=profissional, dia_semana=1,
            hora_inicio=time(8), hora_fim=time(12),
        )
        url = reverse('painel:agenda_horario_semanal_editar', kwargs={
            'uuid': self.empresa.uuid, 'pk': item.pk,
        })
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_central_aponta_para_nova_tela_de_horarios(self):
        response = self.client.get(self.url)
        horarios = reverse('painel:agenda_horarios', kwargs={'uuid': self.empresa.uuid})
        self.assertEqual(response.context['central']['urls']['horarios'], horarios)
        self.assertContains(response, horarios)

    def test_abertura_valida_fechamento_e_reabertura(self):
        estado_url = reverse('painel:agenda_estado', kwargs={'uuid': self.empresa.uuid})
        self.client.post(estado_url, {'acao': 'abrir'})
        agenda = AgendaEmpresa.objects.get(empresa=self.empresa)
        self.assertEqual(agenda.status, AgendaEmpresa.Status.ABERTA)
        self.assertEqual(agenda.atualizado_por, self.gestor)
        self.assertIsNotNone(agenda.aberto_em)
        self.client.post(estado_url, {'acao': 'fechar'})
        agenda.refresh_from_db()
        self.assertEqual(agenda.status, AgendaEmpresa.Status.FECHADA)
        self.assertIsNotNone(agenda.fechado_em)
        self.client.post(estado_url, {'acao': 'abrir'})
        agenda.refresh_from_db()
        self.assertEqual(agenda.status, AgendaEmpresa.Status.ABERTA)

    def test_abertura_invalida_informa_pendencias(self):
        AgendaDisponibilidade.objects.filter(profissional=self.profissional).update(ativo=False)
        response = self.client.post(reverse(
            'painel:agenda_estado', kwargs={'uuid': self.empresa.uuid},
        ), {'acao': 'abrir'}, follow=True)
        self.assertFalse(AgendaEmpresa.objects.filter(
            empresa=self.empresa, status=AgendaEmpresa.Status.ABERTA,
        ).exists())
        self.assertContains(response, 'Falta apenas definir seus horários.')

    def test_estado_exige_post_e_impede_idor(self):
        url = reverse('painel:agenda_estado', kwargs={'uuid': self.empresa.uuid})
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.force_login(self.outro)
        self.assertEqual(self.client.post(url, {'acao': 'abrir'}).status_code, 404)

    def test_agenda_fechada_preserva_reserva_e_remove_slots_publicos(self):
        AgendaEmpresa.objects.create(
            empresa=self.empresa, status=AgendaEmpresa.Status.ABERTA,
        )
        self.client.post(reverse(
            'painel:agenda_estado', kwargs={'uuid': self.empresa.uuid},
        ), {'acao': 'fechar'})
        self.assertTrue(Agendamento.objects.filter(pk=self.agendamento.pk).exists())
        from apps.agenda.public_services import gerar_slots
        self.assertEqual(gerar_slots(self.vinculo, self.agendamento.inicio.date()), [])

    def test_capacidade_pendente_impede_abertura(self):
        self.empresa.capacidades_empresa.filter(
            capacidade__codigo='ACEITAR_AGENDAMENTOS',
        ).update(status=EmpresaCapacidade.Status.PENDENTE)
        self.client.post(reverse(
            'painel:agenda_estado', kwargs={'uuid': self.empresa.uuid},
        ), {'acao': 'abrir'})
        self.assertFalse(AgendaEmpresa.objects.filter(
            empresa=self.empresa, status=AgendaEmpresa.Status.ABERTA,
        ).exists())

    def test_calendario_oferece_dia_semana_e_mes(self):
        url = reverse('painel:agenda_calendario', kwargs={'uuid': self.empresa.uuid})
        for modo in ('dia', 'semana', 'mes'):
            response = self.client.get(url, {
                'modo': modo, 'data': self.agendamento.inicio.date().isoformat(),
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['modo'], modo)
            self.assertContains(response, f'mode-{modo}')
            if modo == 'dia':
                self.assertEqual(len(response.context['dias']), 1)
            elif modo == 'semana':
                self.assertEqual(len(response.context['dias']), 7)
            else:
                self.assertGreaterEqual(len(response.context['dias']), 28)
        self.assertContains(response, 'Mês')

    def test_calendario_filtra_profissional_e_servico(self):
        url = reverse('painel:agenda_calendario', kwargs={'uuid': self.empresa.uuid})
        response = self.client.get(url, {
            'data': self.agendamento.inicio.date().isoformat(),
            'profissional': self.profissional.pk,
            'servico': self.servico.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['profissional_selecionado'], self.profissional)
        self.assertEqual(response.context['servico_selecionado'], self.servico)
        self.assertContains(response, self.servico.titulo)

    def test_calendario_rejeita_filtros_de_outra_empresa(self):
        membro = EmpresaUsuario.objects.create(
            empresa=self.empresa_alheia, usuario=self.outro, ativo=True,
        )
        profissional = AgendaProfissional.objects.create(empresa_usuario=membro)
        url = reverse('painel:agenda_calendario', kwargs={'uuid': self.empresa.uuid})
        self.assertEqual(self.client.get(url, {'profissional': profissional.pk}).status_code, 404)

    def test_calendario_vazio_e_agenda_fechada_renderizam(self):
        Agendamento.objects.all().delete()
        AgendaDisponibilidade.objects.all().delete()
        AgendaEmpresa.objects.create(
            empresa=self.empresa, status=AgendaEmpresa.Status.FECHADA,
        )
        response = self.client.get(reverse(
            'painel:agenda_calendario', kwargs={'uuid': self.empresa.uuid},
        ), {'modo': 'dia'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h1>Calendário</h1>', html=True)
        self.assertContains(response, 'agcal-mobile-days')

    def test_lista_agendamentos_filtra_e_pagina(self):
        url = reverse('painel:agenda_agendamento_lista', kwargs={'uuid': self.empresa.uuid})
        response = self.client.get(url, {
            'q': 'Serviço Central', 'status': Agendamento.Status.PENDENTE,
            'profissional': self.profissional.pk, 'servico': self.servico.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['itens']), [self.agendamento])
        self.assertEqual(response.context['pagina'].paginator.per_page, 25)

    def test_alteracao_de_status_registra_historico(self):
        response = self.client.post(reverse(
            'painel:agenda_agendamento_status',
            kwargs={'uuid': self.empresa.uuid, 'pk': self.agendamento.pk},
        ), {'status': Agendamento.Status.CONFIRMADO})
        self.assertEqual(response.status_code, 302)
        evento = AgendamentoHistorico.objects.get(agendamento=self.agendamento)
        self.assertEqual(evento.status_anterior, Agendamento.Status.PENDENTE)
        self.assertEqual(evento.status_novo, Agendamento.Status.CONFIRMADO)
        self.assertEqual(evento.realizado_por, self.gestor)

    def test_criacao_manual_usa_disponibilidade_e_historico(self):
        AgendaEmpresa.objects.create(empresa=self.empresa, status=AgendaEmpresa.Status.ABERTA)
        inicio = timezone.localtime(self.agendamento.inicio).replace(hour=12)
        response = self.client.post(reverse(
            'painel:agenda_agendamento_criar', kwargs={'uuid': self.empresa.uuid},
        ), {'cliente_email': self.cliente.email, 'vinculo': self.vinculo.pk,
            'inicio': inicio.strftime('%Y-%m-%dT%H:%M')})
        self.assertEqual(response.status_code, 302)
        criado = Agendamento.objects.exclude(pk=self.agendamento.pk).get()
        self.assertEqual(criado.status, Agendamento.Status.CONFIRMADO)
        self.assertTrue(criado.historico.filter(acao=AgendamentoHistorico.Acao.CRIADO).exists())

    def test_criacao_manual_rejeita_conflito_e_agenda_fechada(self):
        AgendaEmpresa.objects.create(empresa=self.empresa, status=AgendaEmpresa.Status.ABERTA)
        url = reverse('painel:agenda_agendamento_criar', kwargs={'uuid': self.empresa.uuid})
        dados = {'cliente_email': self.cliente.email, 'vinculo': self.vinculo.pk,
                 'inicio': timezone.localtime(self.agendamento.inicio).strftime('%Y-%m-%dT%H:%M')}
        self.assertEqual(self.client.post(url, dados).status_code, 200)
        self.assertEqual(Agendamento.objects.count(), 1)
        AgendaEmpresa.objects.filter(empresa=self.empresa).update(status=AgendaEmpresa.Status.FECHADA)
        self.assertEqual(self.client.post(url, dados).status_code, 200)
        self.assertEqual(Agendamento.objects.count(), 1)

    def test_reagendamento_transacional_registra_historico(self):
        AgendaEmpresa.objects.create(empresa=self.empresa, status=AgendaEmpresa.Status.ABERTA)
        novo_inicio = timezone.localtime(self.agendamento.inicio).replace(hour=12)
        response = self.client.post(reverse(
            'painel:agenda_agendamento_reagendar',
            kwargs={'uuid': self.empresa.uuid, 'pk': self.agendamento.pk},
        ), {'vinculo': self.vinculo.pk,
            'inicio': novo_inicio.strftime('%Y-%m-%dT%H:%M')})
        self.assertEqual(response.status_code, 302)
        self.agendamento.refresh_from_db()
        self.assertEqual(timezone.localtime(self.agendamento.inicio).hour, 12)
        self.assertTrue(self.agendamento.historico.filter(
            acao=AgendamentoHistorico.Acao.REAGENDADO,
        ).exists())

    def test_gestao_agendamento_impede_idor(self):
        outro_membro = EmpresaUsuario.objects.create(
            empresa=self.empresa_alheia, usuario=self.outro, ativo=True,
        )
        outro_profissional = AgendaProfissional.objects.create(empresa_usuario=outro_membro)
        url = reverse('painel:agenda_agendamento_reagendar', kwargs={
            'uuid': self.empresa.uuid, 'pk': self.agendamento.pk,
        })
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotEqual(outro_profissional.pk, self.profissional.pk)

    def test_configuracoes_da_agenda_salvam_politicas_e_impedem_idor(self):
        url = reverse('painel:agenda_configuracoes', kwargs={'uuid': self.empresa.uuid})
        response = self.client.post(url, {
            'antecedencia_minima_minutos': 120,
            'horizonte_maximo_dias': 45,
            'intervalo_grade_minutos': 30,
            'cancelamento_antecedencia_minutos': 180,
        })
        self.assertEqual(response.status_code, 302)
        configuracao = AgendaEmpresa.objects.get(empresa=self.empresa)
        self.assertEqual(configuracao.intervalo_grade_minutos, 30)
        self.assertEqual(configuracao.atualizado_por, self.gestor)
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_slots_respeitam_antecedencia_horizonte_e_grade(self):
        configuracao = AgendaEmpresa.objects.create(
            empresa=self.empresa, status=AgendaEmpresa.Status.ABERTA,
            antecedencia_minima_minutos=60, horizonte_maximo_dias=1,
            intervalo_grade_minutos=30,
        )
        from apps.agenda.public_services import gerar_slots
        agora = self.agendamento.inicio - timedelta(days=3, hours=1)
        self.assertEqual(gerar_slots(self.vinculo, self.agendamento.inicio.date(), agora=agora), [])
        configuracao.horizonte_maximo_dias = 3
        configuracao.save()
        slots = gerar_slots(self.vinculo, self.agendamento.inicio.date(), agora=agora)
        minutos = {(item.hour, item.minute) for item in slots}
        self.assertIn((8, 0), minutos)
        self.assertIn((8, 30), minutos)

    def test_politica_de_cancelamento_publico(self):
        AgendaEmpresa.objects.create(
            empresa=self.empresa, status=AgendaEmpresa.Status.ABERTA,
            cancelamento_antecedencia_minutos=60 * 24 * 10,
        )
        from apps.agenda.public_services import cancelar_agendamento_cliente
        with self.assertRaisesMessage(Exception, 'prazo permitido'):
            cancelar_agendamento_cliente(
                agendamento_uuid=self.agendamento.uuid, cliente=self.cliente,
            )
        self.agendamento.refresh_from_db()
        self.assertEqual(self.agendamento.status, Agendamento.Status.PENDENTE)

    def test_bloqueio_informa_conflito_com_reserva_existente(self):
        url = reverse('painel:agenda_bloqueio_criar', kwargs={'uuid': self.empresa.uuid})
        response = self.client.post(url, {
            'profissional': self.profissional.pk,
            'tipo': AgendaBloqueio.Tipo.OUTRO,
            'inicio': timezone.localtime(self.agendamento.inicio).strftime('%Y-%m-%dT%H:%M'),
            'fim': timezone.localtime(self.agendamento.fim).strftime('%Y-%m-%dT%H:%M'),
            'motivo': 'Ausência',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Há agendamentos ativos neste período')
        self.assertFalse(AgendaBloqueio.objects.exists())

    def test_central_expoe_fluxo_simples_de_quatro_passos(self):
        response = self.client.get(self.url)
        central = response.context['central']
        self.assertEqual(
            [item['titulo'] for item in central['passos']],
            ['Serviços', 'Quem atende', 'Horários', 'Agenda online'],
        )
        self.assertEqual(central['passos_concluidos'], 3)
        self.assertTrue(central['pronto_para_ativar'])
        self.assertContains(response, 'Ativar minha agenda')

    def test_proximo_passo_quando_servicos_estao_ausentes(self):
        Agendamento.objects.filter(pk=self.agendamento.pk).delete()
        AgendaProfissionalServico.objects.filter(pk=self.vinculo.pk).delete()
        Servico.all_objects.filter(pk=self.servico.pk).delete()
        central = self.client.get(self.url).context['central']
        self.assertEqual(central['proximo_passo']['rotulo'], 'Configurar serviços')

    def test_proximo_passo_quando_atendente_esta_ausente(self):
        Agendamento.objects.filter(pk=self.agendamento.pk).delete()
        AgendaProfissional.objects.filter(pk=self.profissional.pk).delete()
        central = self.client.get(self.url).context['central']
        self.assertEqual(central['proximo_passo']['rotulo'], 'Definir quem atende')

    def test_proximo_passo_quando_servico_nao_esta_ligado_ao_atendente(self):
        Agendamento.objects.filter(pk=self.agendamento.pk).delete()
        AgendaProfissionalServico.objects.filter(pk=self.vinculo.pk).delete()
        central = self.client.get(self.url).context['central']
        self.assertEqual(
            central['proximo_passo']['rotulo'],
            'Definir serviços de cada atendente',
        )

    def test_proximo_passo_quando_horarios_estao_ausentes(self):
        AgendaDisponibilidade.objects.filter(profissional=self.profissional).update(
            ativo=False,
        )
        central = self.client.get(self.url).context['central']
        self.assertEqual(central['proximo_passo']['rotulo'], 'Definir horários')
        self.assertEqual(
            central['proximo_passo']['mensagem'],
            'Falta apenas definir seus horários.',
        )

    def test_proximo_passo_quando_perfil_publico_esta_desativado(self):
        Empresa.all_objects.filter(pk=self.empresa.pk).update(perfil_publico=False)
        central = self.client.get(self.url).context['central']
        self.assertEqual(central['proximo_passo']['rotulo'], 'Revisar dados da empresa')
        self.assertFalse(central['pronto_para_ativar'])

    def test_ativar_sem_capacidade_cria_solicitacao_pendente(self):
        self.empresa.capacidades_empresa.filter(
            capacidade__codigo='ACEITAR_AGENDAMENTOS',
        ).delete()
        response = self.client.post(reverse(
            'painel:agenda_estado', kwargs={'uuid': self.empresa.uuid},
        ), {'acao': 'abrir'}, follow=True)
        solicitacao = self.empresa.capacidades_empresa.get(
            capacidade__codigo='ACEITAR_AGENDAMENTOS',
        )
        self.assertEqual(solicitacao.status, EmpresaCapacidade.Status.PENDENTE)
        self.assertFalse(AgendaEmpresa.objects.filter(
            empresa=self.empresa, status=AgendaEmpresa.Status.ABERTA,
        ).exists())
        self.assertContains(response, 'Estamos liberando sua agenda online')
        self.assertNotContains(response, 'ACEITAR_AGENDAMENTOS')

    def test_capacidade_pendente_nao_impede_configuracao(self):
        self.empresa.capacidades_empresa.filter(
            capacidade__codigo='ACEITAR_AGENDAMENTOS',
        ).update(status=EmpresaCapacidade.Status.PENDENTE)
        response = self.client.get(self.url)
        self.assertContains(response, 'Agenda aguardando liberação')
        self.assertNotContains(response, 'Ativar minha agenda')
        for nome in ('agenda_vinculo_lista', 'agenda_horarios', 'agenda_bloqueio_lista'):
            url = reverse(f'painel:{nome}', kwargs={'uuid': self.empresa.uuid})
            self.assertEqual(self.client.get(url).status_code, 200, nome)

    def test_capacidade_inativa_nao_libera_agenda(self):
        AgendaEmpresa.objects.create(
            empresa=self.empresa, status=AgendaEmpresa.Status.ABERTA,
        )
        Capacidade.objects.filter(codigo='ACEITAR_AGENDAMENTOS').update(ativo=False)
        self.assertFalse(self.empresa.pode_aceitar_agendamentos)
        response = self.client.get(self.url)
        central = response.context['central']
        self.assertFalse(central['autorizado'])
        self.assertTrue(central['aguardando_liberacao'])
        self.assertFalse(central['esta_online'])
        self.assertContains(response, 'Desativada')

    def test_desativacao_usa_linguagem_simples_e_preserva_seguranca(self):
        AgendaEmpresa.objects.create(
            empresa=self.empresa, status=AgendaEmpresa.Status.ABERTA,
        )
        response = self.client.post(reverse(
            'painel:agenda_estado', kwargs={'uuid': self.empresa.uuid},
        ), {'acao': 'fechar'}, follow=True)
        self.assertContains(response, 'Desativada')
        self.assertTrue(Agendamento.objects.filter(pk=self.agendamento.pk).exists())
        self.assertFalse(AgendaEmpresa.objects.filter(
            empresa=self.empresa, status=AgendaEmpresa.Status.ABERTA,
        ).exists())
