"""Diagnostico centralizado da prontidao da Agenda empresarial."""

from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import Empresa, EmpresaCapacidade
from apps.services.models import Servico

from .models import (
    Agendamento,
    AgendaEmpresa,
    AgendaBloqueio,
    AgendaDisponibilidade,
    AgendaDisponibilidadeData,
    AgendaFuncionamentoEmpresa,
    AgendaProfissional,
    AgendaProfissionalServico,
)
from .public_services import STATUS_OCUPANTES, vinculos_agendaveis


def _capacidade_aprovada(empresa, codigo):
    return empresa.capacidades_empresa.filter(
        capacidade__codigo=codigo,
        capacidade__ativo=True,
        ativo=True,
        status=EmpresaCapacidade.Status.APROVADA,
    ).exists()


def _funcionamento_compativel(empresa, semanais, especificas):
    funcionamentos = list(AgendaFuncionamentoEmpresa.objects.filter(empresa=empresa))
    if not funcionamentos:
        return True

    faixas_ativas = [item for item in funcionamentos if item.ativo]
    for disponibilidade in semanais:
        if any(
            faixa.dia_semana == disponibilidade.dia_semana
            and faixa.hora_inicio <= disponibilidade.hora_inicio
            and faixa.hora_fim >= disponibilidade.hora_fim
            for faixa in faixas_ativas
        ):
            return True
    for disponibilidade in especificas:
        if any(
            faixa.dia_semana == disponibilidade.data.weekday()
            and faixa.hora_inicio <= disponibilidade.hora_inicio
            and faixa.hora_fim >= disponibilidade.hora_fim
            for faixa in faixas_ativas
        ):
            return True
    return False


def construir_central_agenda(empresa, *, considerar_estado=True):
    """Retorna o contrato de exibicao da Central, sempre isolado por empresa."""
    agora = timezone.now()
    hoje = timezone.localdate()

    profissionais = list(AgendaProfissional.objects.filter(
        empresa_usuario__empresa=empresa,
    ).select_related('empresa_usuario__usuario').order_by(
        'empresa_usuario__usuario__nome_exibicao',
        'empresa_usuario__usuario__first_name',
    ))
    profissionais_ativos = [
        item for item in profissionais
        if item.ativo and item.empresa_usuario.ativo
    ]

    servicos_publicados = Servico.objects.filter(
        empresa=empresa,
        prestador_tipo=Servico.PrestadorTipo.EMPRESA,
        status=Servico.Status.PUBLICADO,
        publicado_em__isnull=False,
        ativo=True,
    )
    vinculos = AgendaProfissionalServico.objects.filter(
        profissional__empresa_usuario__empresa=empresa,
    ).select_related(
        'servico', 'profissional__empresa_usuario__usuario',
    )
    vinculos_ativos = vinculos.filter(
        ativo=True,
        duracao_minutos__gt=0,
        profissional__ativo=True,
        profissional__empresa_usuario__ativo=True,
    )

    disponibilidades_semanais = list(AgendaDisponibilidade.objects.filter(
        profissional__empresa_usuario__empresa=empresa,
        profissional__ativo=True,
        profissional__empresa_usuario__ativo=True,
        ativo=True,
        hora_fim__gt=F('hora_inicio'),
    ).select_related('profissional'))
    disponibilidades_especificas = list(AgendaDisponibilidadeData.objects.filter(
        profissional__empresa_usuario__empresa=empresa,
        profissional__ativo=True,
        profissional__empresa_usuario__ativo=True,
        ativo=True,
        data__gte=hoje,
        hora_fim__gt=F('hora_inicio'),
    ).select_related('profissional').order_by('data', 'hora_inicio'))
    profissionais_com_disponibilidade = {
        item.profissional_id
        for item in disponibilidades_semanais + disponibilidades_especificas
    }

    funcionamentos = AgendaFuncionamentoEmpresa.objects.filter(empresa=empresa)
    funcionamento_compativel = _funcionamento_compativel(
        empresa, disponibilidades_semanais, disponibilidades_especificas,
    )
    proximos = Agendamento.objects.filter(
        profissional_servico__profissional__empresa_usuario__empresa=empresa,
        status__in=STATUS_OCUPANTES,
        inicio__gte=agora,
    ).select_related(
        'cliente', 'profissional_servico__servico',
        'profissional_servico__profissional__empresa_usuario__usuario',
    ).order_by('inicio')
    bloqueios = AgendaBloqueio.objects.filter(
        profissional__empresa_usuario__empresa=empresa,
        ativo=True,
        fim__gte=agora,
    ).select_related(
        'profissional__empresa_usuario__usuario',
    ).order_by('inicio')

    empresa_apta = empresa.ativo and empresa.status == Empresa.Status.ATIVA
    perfil_publico = empresa.perfil_publico
    prestar_servicos = _capacidade_aprovada(empresa, 'PRESTAR_SERVICOS')
    aceitar_agendamentos = _capacidade_aprovada(empresa, 'ACEITAR_AGENDAMENTOS')
    registro_aceitar_agendamentos = empresa.capacidades_empresa.filter(
        capacidade__codigo='ACEITAR_AGENDAMENTOS',
    ).first()
    tem_profissional = bool(profissionais_ativos)
    tem_servico_publicado = servicos_publicados.exists()
    tem_vinculo = vinculos_ativos.exists()
    duracao_valida = tem_vinculo
    tem_horario = bool(profissionais_com_disponibilidade)

    urls = {
        'empresa': reverse('painel:empresa_detalhe', kwargs={'uuid': empresa.uuid}),
        'empresa_editar': reverse('painel:empresa_editar', kwargs={'uuid': empresa.uuid}),
        'capacidades': reverse('painel:empresa_capacidades', kwargs={'uuid': empresa.uuid}),
        'profissionais': reverse('painel:empresa_equipe', kwargs={'uuid': empresa.uuid}),
        'servicos': reverse('painel:agenda_vinculo_lista', kwargs={'uuid': empresa.uuid}),
        'horarios': reverse('painel:agenda_horarios', kwargs={'uuid': empresa.uuid}),
        'funcionamento': reverse('painel:agenda_funcionamento_lista', kwargs={'uuid': empresa.uuid}),
        'bloqueios': reverse('painel:agenda_bloqueio_lista', kwargs={'uuid': empresa.uuid}),
        'calendario': reverse('painel:agenda_calendario', kwargs={'uuid': empresa.uuid}),
        'agendamentos': reverse('painel:agenda_agendamento_lista', kwargs={'uuid': empresa.uuid}),
        'configuracoes': reverse('painel:agenda_configuracoes', kwargs={'uuid': empresa.uuid}),
    }
    checklist = [
        {'rotulo': 'Empresa apta', 'ok': empresa_apta, 'acao': 'Revisar empresa', 'url': urls['empresa_editar']},
        {'rotulo': 'Perfil público', 'ok': perfil_publico, 'acao': 'Configurar perfil', 'url': urls['empresa_editar']},
        {'rotulo': 'Capacidade para prestar serviços', 'ok': prestar_servicos, 'acao': 'Ver capacidades', 'url': urls['capacidades']},
        {'rotulo': 'Capacidade para aceitar agendamentos', 'ok': aceitar_agendamentos, 'acao': 'Ver capacidades', 'url': urls['capacidades']},
        {'rotulo': 'Profissional ativo', 'ok': tem_profissional, 'acao': 'Adicionar profissional', 'url': urls['profissionais']},
        {'rotulo': 'Serviço publicado', 'ok': tem_servico_publicado, 'acao': 'Configurar serviços', 'url': reverse('painel:servicos_lista') + f'?empresa={empresa.uuid}'},
        {'rotulo': 'Profissional vinculado ao serviço', 'ok': tem_vinculo, 'acao': 'Vincular serviço', 'url': urls['servicos']},
        {'rotulo': 'Duração válida', 'ok': duracao_valida, 'acao': 'Revisar serviços', 'url': urls['servicos']},
        {'rotulo': 'Horário ou disponibilidade configurado', 'ok': tem_horario, 'acao': 'Configurar horários', 'url': urls['horarios']},
        {'rotulo': 'Funcionamento empresarial compatível', 'ok': funcionamento_compativel, 'acao': 'Configurar funcionamento', 'url': urls['funcionamento']},
    ]

    autorizado = empresa_apta and prestar_servicos and aceitar_agendamentos
    configurado = all(item['ok'] for item in checklist[4:]) and perfil_publico
    efetivamente_agendaveis = vinculos_agendaveis(empresa=empresa) if autorizado else []
    try:
        agenda_empresa = empresa.agenda_configuracao
    except AgendaEmpresa.DoesNotExist:
        agenda_empresa = None
    if not autorizado:
        estado = 'PENDENTE DE AUTORIZAÇÃO'
        mensagem = 'Conclua as autorizações necessárias enquanto prepara a configuração.'
    elif not configurado:
        estado = 'PENDENTE DE CONFIGURAÇÃO'
        mensagem = 'Complete os itens pendentes para disponibilizar horários ao público.'
    elif considerar_estado and agenda_empresa and agenda_empresa.status == AgendaEmpresa.Status.ABERTA:
        estado = 'ATIVA'
        mensagem = 'A Agenda está aberta e apta a receber agendamentos.'
    elif considerar_estado and agenda_empresa and agenda_empresa.status == AgendaEmpresa.Status.FECHADA:
        estado = 'FECHADA'
        mensagem = 'A configuração foi preservada, mas novos agendamentos estão fechados.'
    else:
        estado = 'PRONTA PARA ABRIR'
        mensagem = 'A configuração está completa e a Agenda pode ser aberta.'

    servicos_ok = tem_servico_publicado
    atendentes_ok = tem_profissional and tem_vinculo
    horarios_ok = tem_horario and funcionamento_compativel
    online_ok = bool(
        agenda_empresa and agenda_empresa.status == AgendaEmpresa.Status.ABERTA
        and autorizado
    )
    passos = [
        {
            'numero': 1,
            'titulo': 'Serviços',
            'descricao': (
                'Seus serviços já estão cadastrados.'
                if servicos_ok else
                'Escolha os serviços que poderão ser agendados.'
            ),
            'ok': servicos_ok,
            'url': reverse('painel:servicos_lista') + f'?empresa={empresa.uuid}',
        },
        {
            'numero': 2,
            'titulo': 'Quem atende',
            'descricao': (
                'Quem atende e seus serviços já foram definidos.'
                if atendentes_ok else
                'Informe quem realiza cada serviço.'
            ),
            'ok': atendentes_ok,
            'url': urls['profissionais'] if not tem_profissional else urls['servicos'],
        },
        {
            'numero': 3,
            'titulo': 'Horários',
            'descricao': (
                'Os horários de atendimento já estão definidos.'
                if horarios_ok else
                'Defina os dias e horários de atendimento.'
            ),
            'ok': horarios_ok,
            'url': urls['horarios'],
        },
        {
            'numero': 4,
            'titulo': 'Agenda online',
            'descricao': (
                'Clientes já podem escolher horários.' if online_ok else
                'Ative quando terminar a configuração.'
            ),
            'ok': online_ok,
            'url': '',
        },
    ]
    if not servicos_ok:
        proximo_passo = {
            'mensagem': 'Comece escolhendo os serviços que poderão ser agendados.',
            'rotulo': 'Configurar serviços',
            'url': passos[0]['url'],
        }
    elif not tem_profissional:
        proximo_passo = {
            'mensagem': 'Agora informe quem realiza os atendimentos.',
            'rotulo': 'Definir quem atende',
            'url': urls['profissionais'],
        }
    elif not tem_vinculo:
        proximo_passo = {
            'mensagem': 'Falta definir qual serviço cada pessoa atende.',
            'rotulo': 'Definir serviços de cada atendente',
            'url': urls['servicos'],
        }
    elif not horarios_ok:
        proximo_passo = {
            'mensagem': 'Falta apenas definir seus horários.',
            'rotulo': 'Definir horários',
            'url': urls['horarios'],
        }
    elif not empresa_apta or not perfil_publico:
        proximo_passo = {
            'mensagem': 'Antes de ativar, confirme os dados públicos da sua empresa.',
            'rotulo': 'Revisar dados da empresa',
            'url': urls['empresa_editar'],
        }
    else:
        proximo_passo = None

    aguardando_liberacao = bool(
        prestar_servicos
        and registro_aceitar_agendamentos
        and not aceitar_agendamentos
    )
    pronto_para_ativar = (
        empresa_apta and perfil_publico and prestar_servicos
        and servicos_ok and atendentes_ok and horarios_ok
        and not aguardando_liberacao
    )

    return {
        'estado': estado,
        'mensagem': mensagem,
        'autorizado': autorizado,
        'configurado': configurado,
        'agenda_empresa': agenda_empresa,
        'pode_abrir': autorizado and configurado,
        'esta_aberta': bool(
            agenda_empresa and agenda_empresa.status == AgendaEmpresa.Status.ABERTA
        ),
        'esta_online': online_ok,
        'checklist': checklist,
        'checklist_ok': sum(item['ok'] for item in checklist),
        'checklist_total': len(checklist),
        'urls': urls,
        'profissionais': profissionais,
        'profissionais_total': len(profissionais),
        'profissionais_ativos': len(profissionais_ativos),
        'servicos_publicados': servicos_publicados.count(),
        'servicos_vinculados': vinculos.values('servico_id').distinct().count(),
        'vinculos_ativos': vinculos_ativos.count(),
        'servicos_agendaveis': len({item.servico_id for item in efetivamente_agendaveis}),
        'funcionamentos_ativos': funcionamentos.filter(ativo=True).count(),
        'disponibilidades_semanais': len(disponibilidades_semanais),
        'disponibilidades_especificas': disponibilidades_especificas[:5],
        'disponibilidades_especificas_total': len(disponibilidades_especificas),
        'profissionais_com_disponibilidade': len(profissionais_com_disponibilidade),
        'bloqueios_ativos': bloqueios.count(),
        'proximos_bloqueios': bloqueios[:3],
        'proximos_total': proximos.count(),
        'proximos': proximos[:5],
        'passos': passos,
        'passos_concluidos': sum(item['ok'] for item in passos),
        'proximo_passo': proximo_passo,
        'aguardando_liberacao': aguardando_liberacao,
        'pronto_para_ativar': pronto_para_ativar,
    }
