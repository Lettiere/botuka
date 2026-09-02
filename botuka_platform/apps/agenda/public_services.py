from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from apps.services.models import Servico

from .models import (
    Agendamento,
    AgendaBloqueio,
    AgendaDisponibilidade,
    AgendaDisponibilidadeData,
    AgendaFuncionamentoEmpresa,
    AgendaProfissional,
    AgendaProfissionalServico,
)


STATUS_OCUPANTES = (Agendamento.Status.PENDENTE, Agendamento.Status.CONFIRMADO)


def vinculos_publicos_queryset():
    return AgendaProfissionalServico.objects.filter(
        ativo=True,
        profissional__ativo=True,
        profissional__empresa_usuario__ativo=True,
        profissional__empresa_usuario__empresa__ativo=True,
        profissional__empresa_usuario__empresa__perfil_publico=True,
        profissional__empresa_usuario__empresa__status='ATIVA',
        servico__in=Servico.objects.publicamente_visiveis(),
        servico__prestador_tipo=Servico.PrestadorTipo.EMPRESA,
        servico__empresa__isnull=False,
    ).filter(
        servico__empresa_id=models.F(
            'profissional__empresa_usuario__empresa_id'
        )
    ).select_related(
        'servico',
        'servico__profissao',
        'servico__area',
        'servico__tipo_servico',
        'servico__empresa',
        'servico__empresa__cidade',
        'servico__empresa__estado',
        'profissional__empresa_usuario__usuario',
        'profissional__empresa_usuario__empresa',
    )


def vinculo_publicamente_valido(vinculo):
    empresa = vinculo.servico.empresa
    return bool(
        empresa
        and empresa.pode_aceitar_agendamentos
        and vinculo.profissional.empresa_usuario.empresa_id == empresa.pk
    )


def vinculos_agendaveis(*, empresa=None, servico=None):
    queryset = vinculos_publicos_queryset()
    if empresa is not None:
        if not empresa.pode_aceitar_agendamentos:
            return []
        queryset = queryset.filter(servico__empresa=empresa)
    if servico is not None:
        queryset = queryset.filter(servico=servico)
    return [item for item in queryset if vinculo_publicamente_valido(item)]


def servicos_agendaveis(empresa):
    ids = {item.servico_id for item in vinculos_agendaveis(empresa=empresa)}
    return Servico.objects.filter(pk__in=ids).order_by('titulo')


def sugestoes_agenda_publica(texto, *, limite=12):
    """Autocomplete deduplicado, exclusivamente sobre a cadeia pública agendável."""
    termo = (texto or '').strip()
    if len(termo) < 2:
        return []
    sugestoes = {}
    for vinculo in vinculos_publicos_queryset().filter(
        Q(servico__titulo__icontains=termo)
        | Q(servico__profissao__nome__icontains=termo)
        | Q(servico__area__nome__icontains=termo)
        | Q(servico__tipo_servico__nome__icontains=termo)
        | Q(servico__empresa__nome_fantasia__icontains=termo)
        | Q(servico__empresa__razao_social__icontains=termo)
        | Q(profissional__empresa_usuario__usuario__nome_exibicao__icontains=termo)
        | Q(profissional__empresa_usuario__usuario__first_name__icontains=termo)
        | Q(profissional__empresa_usuario__usuario__last_name__icontains=termo)
    )[:100]:
        servico = vinculo.servico
        valores = (
            ('Serviço', servico.titulo),
            ('Profissão', servico.profissao.nome),
            ('Área', servico.area.nome if servico.area_id else ''),
            ('Tipo de serviço', servico.tipo_servico.nome if servico.tipo_servico_id else ''),
            ('Profissional', nome_publico_profissional(vinculo.profissional)),
            ('Empresa', servico.empresa.nome_exibicao),
        )
        for tipo, rotulo in valores:
            if rotulo and termo.casefold() in rotulo.casefold():
                sugestoes.setdefault((tipo, rotulo.casefold()), {
                    'tipo': tipo, 'rotulo': rotulo, 'valor': rotulo,
                })
    return list(sugestoes.values())[:limite]


def vinculos_com_disponibilidade(*, empresa=None):
    """Cadeia pública completa, incluindo ao menos uma faixa ativa válida."""

    hoje = timezone.localdate()
    return [
        item for item in vinculos_agendaveis(empresa=empresa)
        if (
            AgendaDisponibilidade.objects.filter(
                profissional=item.profissional,
                ativo=True,
                hora_fim__gt=models.F('hora_inicio'),
            ).exists()
            or AgendaDisponibilidadeData.objects.filter(
                profissional=item.profissional,
                data__gte=hoje,
                ativo=True,
                hora_fim__gt=models.F('hora_inicio'),
            ).exists()
        )
    ]


def empresas_agendaveis(*, limite=None):
    """Empresas públicas deduplicadas que podem gerar horários reais."""

    empresas = {}
    for vinculo in vinculos_com_disponibilidade():
        empresa = vinculo.servico.empresa
        empresas.setdefault(empresa.pk, empresa)
        if limite and len(empresas) >= limite:
            break
    return list(empresas.values())


def pesquisar_agenda_publica(parametros, *, hoje=None, dias=14, limite=40):
    """Retorna somente vínculos públicos que produzem slots reais na busca."""

    texto = (parametros.get('q') or '').strip()
    localizacao = (parametros.get('localizacao') or '').strip()
    modalidade = (parametros.get('modalidade') or '').strip().lower()
    profissional = (parametros.get('profissional') or '').strip()
    empresa = (parametros.get('empresa') or '').strip()
    horario = (parametros.get('horario') or '').strip()
    horario_aproximado = (parametros.get('horario_aproximado') or '').strip()
    periodo = (parametros.get('periodo') or '').strip().lower()
    data_texto = (parametros.get('data') or '').strip()
    queryset = vinculos_publicos_queryset()
    if modalidade == 'presencial':
        queryset = queryset.filter(servico__atendimento_presencial=True)
    elif modalidade == 'online':
        queryset = queryset.filter(servico__atendimento_remoto=True)
    if texto:
        queryset = queryset.filter(
            Q(servico__titulo__icontains=texto)
            | Q(servico__profissao__nome__icontains=texto)
            | Q(servico__tipo_servico__nome__icontains=texto)
            | Q(servico__area__nome__icontains=texto)
            | Q(servico__empresa__nome_fantasia__icontains=texto)
            | Q(servico__empresa__razao_social__icontains=texto)
            | Q(profissional__empresa_usuario__usuario__nome_exibicao__icontains=texto)
            | Q(profissional__empresa_usuario__usuario__first_name__icontains=texto)
            | Q(profissional__empresa_usuario__usuario__last_name__icontains=texto)
        )
    if localizacao:
        queryset = queryset.filter(
            Q(servico__empresa__cidade__nome__icontains=localizacao)
            | Q(servico__empresa__estado__nome__icontains=localizacao)
            | Q(servico__empresa__estado__sigla__iexact=localizacao)
            | Q(servico__empresa__bairro__icontains=localizacao)
        )
    if profissional:
        queryset = queryset.filter(
            Q(profissional__empresa_usuario__usuario__nome_exibicao__icontains=profissional)
            | Q(profissional__empresa_usuario__usuario__first_name__icontains=profissional)
            | Q(profissional__empresa_usuario__usuario__last_name__icontains=profissional)
        )
    if empresa:
        queryset = queryset.filter(
            Q(servico__empresa__nome_fantasia__icontains=empresa)
            | Q(servico__empresa__razao_social__icontains=empresa)
        )

    hoje = hoje or timezone.localdate()
    if data_texto:
        try:
            data_inicial = date.fromisoformat(data_texto)
        except ValueError:
            data_inicial = hoje
        datas = (data_inicial,) if data_inicial >= hoje else ()
    else:
        datas = tuple(hoje + timedelta(days=offset) for offset in range(dias))

    resultados = []
    for vinculo in queryset[:limite]:
        dias_disponiveis = []
        for dia in datas:
            slots = gerar_slots(vinculo, dia)

            if horario:
                slots = [
                    slot for slot in slots
                    if slot.strftime('%H:%M') == horario
                ]

            elif horario_aproximado:
                try:
                    alvo_h, alvo_m = map(int, horario_aproximado.split(':', 1))
                    alvo_min = alvo_h * 60 + alvo_m
                except (TypeError, ValueError):
                    alvo_min = None

                if alvo_min is not None:
                    slots = [
                        slot for slot in slots
                        if abs(
                            (slot.hour * 60 + slot.minute) - alvo_min
                        ) <= 60
                    ]
                    slots = sorted(
                        slots,
                        key=lambda slot: abs(
                            (slot.hour * 60 + slot.minute) - alvo_min
                        ),
                    )

            if periodo == 'manha':
                slots = [
                    slot for slot in slots
                    if 6 <= slot.hour < 12
                ]
            elif periodo == 'tarde':
                slots = [
                    slot for slot in slots
                    if 12 <= slot.hour < 18
                ]
            elif periodo == 'noite':
                slots = [
                    slot for slot in slots
                    if 18 <= slot.hour <= 23
                ]

            if slots:
                dias_disponiveis.append({
                    'data': dia,
                    'slots': slots,
                })
        if not dias_disponiveis:
            continue
        servico = vinculo.servico
        empresa_item = servico.empresa
        modalidades = []
        if servico.atendimento_presencial:
            modalidades.append('Presencial')
        if servico.atendimento_remoto:
            modalidades.append('Online')
        resultados.append({
            'vinculo': vinculo,
            'servico': servico,
            'empresa': empresa_item,
            'profissional': vinculo.profissional,
            'profissional_nome': nome_publico_profissional(vinculo.profissional),
            'profissao': servico.profissao,
            'area': servico.area,
            'localizacao': empresa_item.endereco_resumido,
            'modalidades': modalidades,
            'dias': dias_disponiveis,
            'proximo_dia': dias_disponiveis[0]['data'],
            'proximo_slot': dias_disponiveis[0]['slots'][0],
        })
    return resultados


def calendario_servico_publico(*, servico, inicio, dias=7, vinculo_uuid=None):
    """Consolida uma janela real de slots para um serviço e profissional opcional."""

    vinculos = vinculos_agendaveis(empresa=servico.empresa, servico=servico)
    if vinculo_uuid:
        vinculos = [item for item in vinculos if str(item.uuid) == str(vinculo_uuid)]
    calendario = []
    for offset in range(dias):
        data_item = inicio + timedelta(days=offset)
        opcoes = {}
        for vinculo in vinculos:
            for slot in gerar_slots(vinculo, data_item):
                chave = slot.isoformat()
                opcoes.setdefault(chave, {
                    'inicio': slot,
                    'vinculo': vinculo,
                    'profissional_nome': nome_publico_profissional(vinculo.profissional),
                })
        calendario.append({
            'data': data_item,
            'opcoes': [opcoes[chave] for chave in sorted(opcoes)],
        })
    proximo = next(
        (opcao for dia in calendario for opcao in dia['opcoes']), None
    )
    return {'dias': calendario, 'proximo': proximo, 'vinculos': vinculos}


def resumo_operacional_empresa(empresa):
    profissionais = AgendaProfissional.objects.filter(
        empresa_usuario__empresa=empresa,
        ativo=True,
        empresa_usuario__ativo=True,
    )
    vinculos = AgendaProfissionalServico.objects.filter(
        profissional__empresa_usuario__empresa=empresa,
        profissional__ativo=True,
        profissional__empresa_usuario__ativo=True,
        ativo=True,
    )
    proximos = Agendamento.objects.filter(
        profissional_servico__profissional__empresa_usuario__empresa=empresa,
        status__in=STATUS_OCUPANTES,
        inicio__gte=timezone.now(),
    ).select_related(
        'cliente', 'profissional_servico__servico',
        'profissional_servico__profissional__empresa_usuario__usuario',
    ).order_by('inicio')
    hoje = timezone.localdate()
    inicio_hoje = timezone.make_aware(datetime.combine(hoje, datetime.min.time()))
    fim_hoje = inicio_hoje + timedelta(days=1)
    todos = Agendamento.objects.filter(
        profissional_servico__profissional__empresa_usuario__empresa=empresa,
    )
    return {
        'habilitada': empresa.pode_aceitar_agendamentos,
        'profissionais_ativos': profissionais.count(),
        'servicos_agendaveis': vinculos.count(),
        'disponibilidades_ativas': AgendaDisponibilidade.objects.filter(
            profissional__empresa_usuario__empresa=empresa, ativo=True,
        ).count(),
        'bloqueios_ativos': AgendaBloqueio.objects.filter(
            profissional__empresa_usuario__empresa=empresa,
            ativo=True,
            fim__gte=timezone.now(),
        ).count(),
        'proximos_total': proximos.count(),
        'proximos': proximos[:5],
        'hoje_total': todos.filter(inicio__gte=inicio_hoje, inicio__lt=fim_hoje).count(),
        'pendentes_total': todos.filter(status=Agendamento.Status.PENDENTE).count(),
        'confirmados_total': todos.filter(status=Agendamento.Status.CONFIRMADO).count(),
        'concluidos_total': todos.filter(status=Agendamento.Status.CONCLUIDO).count(),
        'cancelados_total': todos.filter(status=Agendamento.Status.CANCELADO).count(),
    }


def nome_publico_profissional(profissional):
    usuario = profissional.usuario
    nome = (usuario.nome_exibicao or usuario.get_full_name()).strip()
    return nome or 'Profissional'


def _aware_local(valor):
    if timezone.is_naive(valor):
        return timezone.make_aware(valor, timezone.get_current_timezone())
    return timezone.localtime(valor)


def interpretar_inicio(valor):
    try:
        inicio = datetime.fromisoformat(valor)
    except (TypeError, ValueError) as exc:
        raise ValidationError('Horário inválido.') from exc
    return _aware_local(inicio)


def _sobrepoe(inicio, fim, outro_inicio, outro_fim):
    return outro_inicio < fim and outro_fim > inicio


def gerar_slots(vinculo, data, *, agora=None):
    if not isinstance(data, date):
        raise ValidationError('Data inválida.')
    if not vinculo_publicamente_valido(vinculo):
        return []
    agora = timezone.localtime(agora or timezone.now())
    duracao = timedelta(minutes=vinculo.duracao_minutos)
    buffer_antes = timedelta(minutes=vinculo.buffer_antes_minutos)
    buffer_depois = timedelta(minutes=vinculo.buffer_depois_minutos)
    disponibilidades_data = AgendaDisponibilidadeData.objects.filter(
        profissional=vinculo.profissional,
        data=data,
        ativo=True,
    ).order_by('hora_inicio')

    if disponibilidades_data.exists():
        disponibilidades = disponibilidades_data
    else:
        disponibilidades = AgendaDisponibilidade.objects.filter(
            profissional=vinculo.profissional,
            ativo=True,
            dia_semana=data.weekday(),
        ).order_by('hora_inicio')

    empresa = vinculo.servico.empresa
    funcionamento_configurado = AgendaFuncionamentoEmpresa.objects.filter(
        empresa=empresa,
    ).exists()
    funcionamentos = list(AgendaFuncionamentoEmpresa.objects.filter(
        empresa=empresa, dia_semana=data.weekday(), ativo=True,
    ).order_by('hora_inicio')) if funcionamento_configurado else []
    inicio_dia = timezone.make_aware(datetime.combine(data, datetime.min.time()))
    fim_dia = inicio_dia + timedelta(days=1)
    bloqueios = list(AgendaBloqueio.objects.filter(
        profissional=vinculo.profissional, ativo=True,
        inicio__lt=fim_dia + buffer_depois, fim__gt=inicio_dia - buffer_antes,
    ))
    agendamentos = list(Agendamento.objects.filter(
        profissional_servico__profissional=vinculo.profissional,
        status__in=STATUS_OCUPANTES,
        inicio__lt=fim_dia + timedelta(days=1), fim__gt=inicio_dia - timedelta(days=1),
    ).select_related('profissional_servico'))
    slots = {}
    for faixa in disponibilidades:
        cursor = timezone.make_aware(
            datetime.combine(data, faixa.hora_inicio),
            timezone.get_current_timezone(),
        )
        limite = timezone.make_aware(
            datetime.combine(data, faixa.hora_fim),
            timezone.get_current_timezone(),
        )
        while cursor + duracao <= limite:
            fim = cursor + duracao
            ocupacao_inicio = cursor - buffer_antes
            ocupacao_fim = fim + buffer_depois
            cabe_profissional = (
                ocupacao_inicio.time() >= faixa.hora_inicio
                and ocupacao_fim.date() == data
                and ocupacao_fim.time() <= faixa.hora_fim
            )
            cabe_empresa = not funcionamento_configurado or any(
                ocupacao_inicio.time() >= faixa_empresa.hora_inicio
                and ocupacao_fim.date() == data
                and ocupacao_fim.time() <= faixa_empresa.hora_fim
                for faixa_empresa in funcionamentos
            )
            if cursor > agora and cabe_profissional and cabe_empresa:
                bloqueado = any(_sobrepoe(
                    ocupacao_inicio, ocupacao_fim, item.inicio, item.fim,
                ) for item in bloqueios)
                ocupado = any(_sobrepoe(
                    ocupacao_inicio, ocupacao_fim,
                    item.inicio - timedelta(minutes=item.profissional_servico.buffer_antes_minutos),
                    item.fim + timedelta(minutes=item.profissional_servico.buffer_depois_minutos),
                ) for item in agendamentos)
                if not bloqueado and not ocupado:
                    slots[cursor.isoformat()] = cursor
            cursor = fim
    return list(slots.values())


def obter_vinculo_publico(uuid):
    try:
        vinculo = vinculos_publicos_queryset().get(uuid=uuid)
    except AgendaProfissionalServico.DoesNotExist as exc:
        raise ValidationError('Vínculo de Agenda indisponível.') from exc
    if not vinculo_publicamente_valido(vinculo):
        raise ValidationError('Agenda indisponível para esta empresa.')
    return vinculo


@transaction.atomic
def criar_agendamento_publico(*, vinculo_uuid, cliente, inicio):
    vinculo_inicial = obter_vinculo_publico(vinculo_uuid)
    AgendaProfissional.objects.select_for_update().get(
        pk=vinculo_inicial.profissional_id
    )
    vinculo = obter_vinculo_publico(vinculo_uuid)
    inicio = interpretar_inicio(inicio) if isinstance(inicio, str) else _aware_local(inicio)
    slots = gerar_slots(vinculo, timezone.localdate(inicio))
    if inicio not in slots:
        raise ValidationError('O horário selecionado não está mais disponível.')
    fim = inicio + timedelta(minutes=vinculo.duracao_minutos)
    agendamento = Agendamento(
        profissional_servico=vinculo,
        cliente=cliente,
        inicio=inicio,
        fim=fim,
        status=Agendamento.Status.PENDENTE,
    )
    agendamento.full_clean()
    agendamento.save()
    return agendamento


@transaction.atomic
def cancelar_agendamento_cliente(*, agendamento_uuid, cliente):
    try:
        agendamento = Agendamento.objects.select_for_update().get(
            uuid=agendamento_uuid,
            cliente=cliente,
        )
    except Agendamento.DoesNotExist as exc:
        raise ValidationError('Agendamento não encontrado.') from exc
    if agendamento.status not in (
        Agendamento.Status.PENDENTE,
        Agendamento.Status.CONFIRMADO,
    ):
        raise ValidationError('Este agendamento não pode ser cancelado.')
    Agendamento.objects.filter(pk=agendamento.pk).update(
        status=Agendamento.Status.CANCELADO
    )
    agendamento.status = Agendamento.Status.CANCELADO
    return agendamento
