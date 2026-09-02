from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agenda.forms import (
    BloqueioForm,
    DisponibilidadeForm,
    ProfissionalServicoForm,
)
from apps.agenda.models import (
    Agendamento,
    AgendaBloqueio,
    AgendaDisponibilidade,
    AgendaDisponibilidadeData,
    AgendaProfissional,
    AgendaProfissionalServico,
)
from apps.agenda.services import alterar_status_agendamento
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
    ProfissaoTipoServico,
    Servico,
    Setor,
    TipoServico,
)


class AgendaOperacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.owner_a = Usuario.objects.create_user(
            'owner-a', 'owner-a@example.com', 'senha-forte'
        )
        cls.owner_b = Usuario.objects.create_user(
            'owner-b', 'owner-b@example.com', 'senha-forte'
        )
        cls.membro_a = Usuario.objects.create_user(
            'membro-a', 'membro-a@example.com', 'senha-forte'
        )
        cls.membro_b = Usuario.objects.create_user(
            'membro-b', 'membro-b@example.com', 'senha-forte'
        )
        cls.cliente = Usuario.objects.create_user(
            'cliente-agenda', 'cliente@example.com', 'senha-forte'
        )
        pais = Pais.objects.create(
            nome='Brasil Agenda', codigo_iso_2='BA', codigo_iso_3='BAG'
        )
        estado = Estado.objects.create(pais=pais, nome='Estado Agenda', sigla='EA')
        cidade = Cidade.objects.create(estado=estado, nome='Cidade Agenda')
        cls.empresa_a = cls._empresa(cls.owner_a, 'Empresa Agenda A', cidade, estado)
        cls.empresa_b = cls._empresa(cls.owner_b, 'Empresa Agenda B', cidade, estado)
        for empresa in (cls.empresa_a, cls.empresa_b):
            for codigo in ('PRESTAR_SERVICOS', 'ACEITAR_AGENDAMENTOS'):
                capacidade, _ = Capacidade.objects.get_or_create(
                    codigo=codigo, defaults={'nome': codigo}
                )
                EmpresaCapacidade.objects.update_or_create(
                    empresa=empresa,
                    capacidade=capacidade,
                    defaults={
                        'status': EmpresaCapacidade.Status.APROVADA,
                        'ativo': True,
                    },
                )
        cls.eu_a = EmpresaUsuario.objects.create(
            empresa=cls.empresa_a, usuario=cls.membro_a, ativo=True
        )
        cls.eu_b = EmpresaUsuario.objects.create(
            empresa=cls.empresa_b, usuario=cls.membro_b, ativo=True
        )
        cls.prof_a = AgendaProfissional.objects.create(empresa_usuario=cls.eu_a)
        cls.prof_b = AgendaProfissional.objects.create(empresa_usuario=cls.eu_b)
        setor = Setor.objects.create(nome='Setor Agenda')
        area = AreaProfissional.objects.create(setor=setor, nome='Área Agenda')
        profissao = Profissao.objects.create(
            setor=setor, area=area, nome='Profissão Agenda'
        )
        tipo = TipoServico.objects.create(nome='Tipo Agenda')
        ProfissaoTipoServico.objects.create(profissao=profissao, tipo_servico=tipo)
        cobranca = FormaCobranca.objects.create(nome='Cobrança Agenda')
        cls.service_args = {
            'setor': setor,
            'area': area,
            'profissao': profissao,
            'tipo_servico': tipo,
            'forma_cobranca': cobranca,
            'prestador_tipo': Servico.PrestadorTipo.EMPRESA,
        }
        cls.servico_a = cls._servico(
            cls.owner_a, cls.empresa_a, 'Serviço Agenda A'
        )
        cls.servico_b = cls._servico(
            cls.owner_b, cls.empresa_b, 'Serviço Agenda B'
        )
        cls.vinculo_a = AgendaProfissionalServico.objects.create(
            profissional=cls.prof_a, servico=cls.servico_a, duracao_minutos=60
        )
        agora = timezone.now()
        dias = (7 - agora.weekday()) % 7 or 7
        proxima_segunda = (agora + timedelta(days=dias)).date()
        cls.disponibilidade_a = AgendaDisponibilidade.objects.create(
            profissional=cls.prof_a,
            dia_semana=proxima_segunda.weekday(),
            hora_inicio=time(8),
            hora_fim=time(18),
        )
        cls.inicio = timezone.make_aware(datetime.combine(proxima_segunda, time(10)))

    @classmethod
    def _empresa(cls, owner, nome, cidade, estado):
        return Empresa.objects.create(
            usuario_proprietario=owner,
            nome_fantasia=nome,
            cidade=cidade,
            estado=estado,
            status=Empresa.Status.ATIVA,
            atuacao=Empresa.Atuacao.SERVICOS,
            perfil_publico=True,
        )

    @classmethod
    def _servico(cls, owner, empresa, titulo, status=Servico.Status.PUBLICADO):
        return Servico.objects.create(
            usuario_responsavel=owner,
            empresa=empresa,
            titulo=titulo,
            status=status,
            **cls.service_args,
        )

    def test_criar_vinculo_valido(self):
        outro = self._servico(self.owner_a, self.empresa_a, 'Outro serviço A')
        form = ProfissionalServicoForm(
            {
                'profissional': self.prof_a.pk,
                'servico': outro.pk,
                'duracao_minutos': 30,
                'buffer_antes_minutos': 0,
                'buffer_depois_minutos': 0,
            },
            empresa=self.empresa_a,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save().ativo)

    def test_rejeitar_profissional_de_outra_empresa(self):
        form = ProfissionalServicoForm(
            {'profissional': self.prof_b.pk, 'servico': self.servico_a.pk, 'duracao_minutos': 30},
            empresa=self.empresa_a,
        )
        self.assertFalse(form.is_valid())

    def test_rejeitar_servico_de_outra_empresa(self):
        form = ProfissionalServicoForm(
            {'profissional': self.prof_a.pk, 'servico': self.servico_b.pk, 'duracao_minutos': 30},
            empresa=self.empresa_a,
        )
        self.assertFalse(form.is_valid())

    def test_rejeitar_servico_nao_publicado(self):
        rascunho = self._servico(
            self.owner_a, self.empresa_a, 'Rascunho Agenda', Servico.Status.RASCUNHO
        )
        form = ProfissionalServicoForm(
            {'profissional': self.prof_a.pk, 'servico': rascunho.pk, 'duracao_minutos': 30},
            empresa=self.empresa_a,
        )
        self.assertFalse(form.is_valid())

    def test_impedir_duplicidade_e_duracao_invalida(self):
        duplicado = ProfissionalServicoForm(
            {'profissional': self.prof_a.pk, 'servico': self.servico_a.pk, 'duracao_minutos': 30},
            empresa=self.empresa_a,
        )
        invalido = ProfissionalServicoForm(
            {'profissional': self.prof_a.pk, 'servico': self.servico_a.pk, 'duracao_minutos': 0},
            empresa=self.empresa_a,
        )
        self.assertFalse(duplicado.is_valid())
        self.assertFalse(invalido.is_valid())

    def test_criar_disponibilidade_valida(self):
        form = DisponibilidadeForm(
            {
                'profissional': self.prof_a.pk,
                'data': (timezone.localdate() + timedelta(days=30)).isoformat(),
                'hora_inicio': '09:00',
                'hora_fim': '12:00',
            },
            empresa=self.empresa_a,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

    def test_impedir_disponibilidade_sobreposta(self):
        AgendaDisponibilidadeData.objects.create(
            profissional=self.prof_a,
            data=self.inicio.date(),
            hora_inicio=time(8),
            hora_fim=time(18),
        )
        form = DisponibilidadeForm(
            {
                'profissional': self.prof_a.pk,
                'data': self.inicio.date().isoformat(),
                'hora_inicio': '09:00',
                'hora_fim': '11:00',
            },
            empresa=self.empresa_a,
        )
        self.assertFalse(form.is_valid())

    def test_disponibilidade_impede_profissional_de_outra_empresa(self):
        form = DisponibilidadeForm(
            {
                'profissional': self.prof_b.pk,
                'data': (self.inicio.date() + timedelta(days=1)).isoformat(),
                'hora_inicio': '09:00',
                'hora_fim': '11:00',
            },
            empresa=self.empresa_a,
        )
        self.assertFalse(form.is_valid())

    def test_criar_bloqueio_valido_e_rejeitar_periodo_invalido(self):
        fim = self.inicio + timedelta(hours=1)
        valido = BloqueioForm(
            {'profissional': self.prof_a.pk, 'tipo': AgendaBloqueio.Tipo.FOLGA,
             'inicio': self.inicio.strftime('%Y-%m-%dT%H:%M'),
             'fim': fim.strftime('%Y-%m-%dT%H:%M'), 'motivo': 'Teste'},
            empresa=self.empresa_a,
        )
        invalido = BloqueioForm(
            {'profissional': self.prof_a.pk, 'tipo': AgendaBloqueio.Tipo.FOLGA,
             'inicio': fim.strftime('%Y-%m-%dT%H:%M'),
             'fim': self.inicio.strftime('%Y-%m-%dT%H:%M')},
            empresa=self.empresa_a,
        )
        self.assertTrue(valido.is_valid(), valido.errors)
        valido.save()
        self.assertFalse(invalido.is_valid())

    def test_bloqueio_impede_profissional_de_outra_empresa(self):
        form = BloqueioForm(
            {'profissional': self.prof_b.pk, 'tipo': AgendaBloqueio.Tipo.OUTRO,
             'inicio': self.inicio.strftime('%Y-%m-%dT%H:%M'),
             'fim': (self.inicio + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')},
            empresa=self.empresa_a,
        )
        self.assertFalse(form.is_valid())

    def _agendamento(self, status=Agendamento.Status.PENDENTE):
        return Agendamento.objects.create(
            profissional_servico=self.vinculo_a,
            cliente=self.cliente,
            inicio=self.inicio,
            fim=self.inicio + timedelta(hours=1),
            status=status,
        )

    def test_confirmar_e_cancelar_agendamento(self):
        item = self._agendamento()
        alterar_status_agendamento(
            empresa=self.empresa_a, agendamento_id=item.pk,
            novo_status=Agendamento.Status.CONFIRMADO,
        )
        alterar_status_agendamento(
            empresa=self.empresa_a, agendamento_id=item.pk,
            novo_status=Agendamento.Status.CANCELADO,
        )
        item.refresh_from_db()
        self.assertEqual(item.status, Agendamento.Status.CANCELADO)

    def test_concluir_e_marcar_falta(self):
        concluido = self._agendamento(Agendamento.Status.CONFIRMADO)
        alterar_status_agendamento(
            empresa=self.empresa_a, agendamento_id=concluido.pk,
            novo_status=Agendamento.Status.CONCLUIDO,
        )
        concluido.refresh_from_db()
        self.assertEqual(concluido.status, Agendamento.Status.CONCLUIDO)
        Agendamento.objects.filter(pk=concluido.pk).update(status=Agendamento.Status.CANCELADO)
        faltou = self._agendamento(Agendamento.Status.CONFIRMADO)
        alterar_status_agendamento(
            empresa=self.empresa_a, agendamento_id=faltou.pk,
            novo_status=Agendamento.Status.FALTOU,
        )
        faltou.refresh_from_db()
        self.assertEqual(faltou.status, Agendamento.Status.FALTOU)

    def test_impedir_transicao_invalida(self):
        item = self._agendamento()
        with self.assertRaises(ValidationError):
            alterar_status_agendamento(
                empresa=self.empresa_a, agendamento_id=item.pk,
                novo_status=Agendamento.Status.CONCLUIDO,
            )

    def test_idor_get_e_post_agendamento_de_outra_empresa(self):
        item = self._agendamento()
        self.client.force_login(self.owner_b)
        get_response = self.client.get(reverse(
            'painel:agenda_agendamento_detalhe', args=[self.empresa_b.uuid, item.pk]
        ))
        post_response = self.client.post(reverse(
            'painel:agenda_agendamento_status', args=[self.empresa_b.uuid, item.pk]
        ), {'status': Agendamento.Status.CONFIRMADO})
        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)
        item.refresh_from_db()
        self.assertEqual(item.status, Agendamento.Status.PENDENTE)

    def test_membro_inativo_nao_e_profissional_selecionavel(self):
        EmpresaUsuario.objects.filter(pk=self.eu_a.pk).update(ativo=False)
        form = DisponibilidadeForm(
            {
                'profissional': self.prof_a.pk,
                'data': (self.inicio.date() + timedelta(days=2)).isoformat(),
                'hora_inicio': '09:00',
                'hora_fim': '10:00',
            },
            empresa=self.empresa_a,
        )
        self.assertFalse(form.is_valid())

    def test_desativacao_preserva_historico(self):
        disponibilidade = AgendaDisponibilidadeData.objects.create(
            profissional=self.prof_a,
            data=self.inicio.date() + timedelta(days=1),
            hora_inicio=time(9),
            hora_fim=time(12),
        )
        self.client.force_login(self.owner_a)
        response = self.client.post(reverse(
            'painel:agenda_disponibilidade_status',
            args=[self.empresa_a.uuid, disponibilidade.pk],
        ), {'ativo': '0'})
        self.assertEqual(response.status_code, 302)
        disponibilidade.refresh_from_db()
        self.assertFalse(disponibilidade.ativo)
        self.assertTrue(AgendaDisponibilidadeData.objects.filter(
            pk=disponibilidade.pk
        ).exists())
