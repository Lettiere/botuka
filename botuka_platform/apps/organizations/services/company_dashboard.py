"""Resumo operacional seguro e centralizado do painel de uma empresa."""

from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import (
    AgendaBloqueio, AgendaDisponibilidade, AgendaProfissional,
    AgendaProfissionalServico, Agendamento,
)
from apps.agenda.public_services import STATUS_OCUPANTES
from apps.organizations.models import Capacidade, Empresa, EmpresaCapacidade
from apps.products.models import Produto
from apps.recruitment.models import Vaga
from apps.recruitment.selectors import indicadores_vagas
from apps.products.services import calcular_limite
from apps.services.models import Servico


def construir_painel_empresa(*, empresa, usuario, permissoes):
    elegiveis = empresa.capacidades_elegiveis_por_atuacao
    empresa_operacional = empresa.ativo and empresa.status == Empresa.Status.ATIVA
    produtos_elegiveis = 'VENDER_PRODUTOS' in elegiveis
    servicos_elegiveis = 'PRESTAR_SERVICOS' in elegiveis
    agenda_elegivel = 'ACEITAR_AGENDAMENTOS' in elegiveis

    produtos_qs = Produto.objects.filter(empresa_proprietaria=empresa)
    servicos_qs = Servico.objects.filter(empresa=empresa)
    vagas_qs = Vaga.objects.filter(empresa=empresa)
    vagas_indicadores = indicadores_vagas(vagas_qs)
    equipe_qs = empresa.usuarios_vinculados.select_related('usuario').order_by(
        '-proprietario', '-administrador', 'usuario__first_name',
    )
    profissionais_qs = AgendaProfissional.objects.filter(
        empresa_usuario__empresa=empresa,
    ).select_related('empresa_usuario__usuario')

    produtos_operacao_ativa = empresa_operacional and empresa.pode_publicar_produto
    limite_produtos = None
    if produtos_operacao_ativa and permissoes['pode_gerenciar']:
        limite_produtos = calcular_limite(
            usuario, Produto.TitularTipo.EMPRESA, empresa,
        )

    servicos_operacao_ativa = empresa_operacional and empresa.pode_publicar_servico
    agenda_habilitada = empresa_operacional and empresa.pode_aceitar_agendamentos
    agora = timezone.now()
    agenda_vinculos = AgendaProfissionalServico.objects.filter(
        profissional__empresa_usuario__empresa=empresa, ativo=True,
        profissional__ativo=True, profissional__empresa_usuario__ativo=True,
    ) if agenda_elegivel else AgendaProfissionalServico.objects.none()
    proximos = Agendamento.objects.filter(
        profissional_servico__profissional__empresa_usuario__empresa=empresa,
        status__in=STATUS_OCUPANTES, inicio__gte=agora,
    ).select_related(
        'profissional_servico__servico',
        'profissional_servico__profissional__empresa_usuario__usuario',
    ).order_by('inicio') if agenda_elegivel else Agendamento.objects.none()
    profissionais_ativos = profissionais_qs.filter(
        ativo=True, empresa_usuario__ativo=True,
    ).count() if agenda_elegivel else 0
    disponibilidades = AgendaDisponibilidade.objects.filter(
        profissional__empresa_usuario__empresa=empresa, ativo=True,
    ).count() if agenda_elegivel else 0
    bloqueios = AgendaBloqueio.objects.filter(
        profissional__empresa_usuario__empresa=empresa, ativo=True, fim__gte=agora,
    ).count() if agenda_elegivel else 0
    if agenda_habilitada and profissionais_ativos and agenda_vinculos.exists() and disponibilidades:
        agenda_estado = 'ATIVA'
        agenda_mensagem = 'Agenda pronta para receber e administrar agendamentos.'
    elif agenda_habilitada:
        agenda_estado = 'INCOMPLETA'
        agenda_mensagem = 'Adicione profissional, serviço agendável e disponibilidade.'
    elif agenda_elegivel:
        agenda_estado = 'PENDENTE'
        agenda_mensagem = 'Ative as capacidades Prestar serviços e Aceitar agendamentos.'
    else:
        agenda_estado = 'INCOMPATIVEL'
        agenda_mensagem = 'Agenda não se aplica à atuação atual da empresa.'

    etapas = [
        bool(empresa.nome_fantasia and empresa.tipo_cadastro), bool(empresa.atuacao),
        bool(empresa.descricao_curta or empresa.descricao_completa or empresa.logo),
        bool(empresa.telefone or empresa.whatsapp or empresa.email or empresa.site),
        bool(empresa.estado_id and empresa.cidade_id),
        bool(empresa.atende_local or empresa.atende_online or empresa.horario_atendimento),
        empresa.status != Empresa.Status.RASCUNHO,
    ]
    percentual = round(sum(etapas) / len(etapas) * 100)
    proxima_etapa = next((i for i, completo in enumerate(etapas, 1) if not completo), 7)

    capacidades = list(
        empresa.capacidades_empresa.filter(ativo=True).select_related('capacidade')
    )
    codigos_vinculados = {item.capacidade.codigo for item in capacidades}
    capacidades_ativas = list(Capacidade.objects.filter(ativo=True).order_by('nome'))
    capacidade_resumo = {
        'aprovadas': sum(item.status == EmpresaCapacidade.Status.APROVADA for item in capacidades),
        'pendentes': sum(item.status == EmpresaCapacidade.Status.PENDENTE for item in capacidades),
        'disponiveis': sum(
            item.codigo in elegiveis and item.codigo not in codigos_vinculados
            for item in capacidades_ativas
        ),
        'incompativeis': sum(item.capacidade.codigo not in elegiveis for item in capacidades),
        'itens': capacidades,
    }

    pendencias = []
    if empresa.status == Empresa.Status.RASCUNHO:
        pendencias.append({
            'titulo': 'Concluir cadastro', 'descricao': f'{percentual}% preenchido',
            'url': reverse('painel:empresa_configurar', kwargs={
                'uuid': empresa.uuid, 'etapa': proxima_etapa,
            }),
        })
    if not empresa.perfil_publico:
        pendencias.append({'titulo': 'Preparar página pública', 'descricao': 'Revise apresentação e visibilidade.', 'url': reverse('painel:empresa_editar', kwargs={'uuid': empresa.uuid})})
    if servicos_elegiveis and not servicos_operacao_ativa:
        pendencias.append({'titulo': 'Ativar operação de serviços', 'descricao': 'Revise status e capacidades.', 'url': reverse('painel:empresa_capacidades', kwargs={'uuid': empresa.uuid})})

    return {
        'empresa_operacional': empresa_operacional,
        'cadastro': {'percentual': percentual, 'proxima_etapa': proxima_etapa, 'pendencias': pendencias[:4]},
        'produtos': {
            'elegivel': produtos_elegiveis, 'operacao_ativa': produtos_operacao_ativa,
            'total': produtos_qs.count(),
            'publicados': produtos_qs.filter(status=Produto.Status.PUBLICADO).count(),
            'pendentes': produtos_qs.filter(status__in=[Produto.Status.RASCUNHO, Produto.Status.EM_ANALISE, Produto.Status.APROVADO]).count(),
            'ultimos': produtos_qs.order_by('-atualizado_em')[:5], 'limite': limite_produtos,
            'pode_criar': bool(permissoes['pode_criar_produto'] and produtos_operacao_ativa and limite_produtos and limite_produtos.permitido),
        },
        'servicos': {
            'elegivel': servicos_elegiveis, 'operacao_ativa': servicos_operacao_ativa,
            'total': servicos_qs.count(),
            'publicados': servicos_qs.filter(status=Servico.Status.PUBLICADO).count(),
            'pendentes': servicos_qs.filter(status__in=[Servico.Status.RASCUNHO, Servico.Status.PENDENTE, Servico.Status.EM_ANALISE]).count(),
            'ultimos': servicos_qs.order_by('-atualizado_em')[:5],
            'pode_criar': bool(permissoes['pode_editar'] and servicos_operacao_ativa),
        },
        'vagas': {
            **vagas_indicadores,
            'ultimas': vagas_qs.order_by('-atualizado_em')[:5],
            'url_gerenciar': (
                reverse('painel:vagas_lista')
                + f'?empresa={empresa.uuid}'
            ),
            'url_criar': (
                reverse('painel:vaga_criar')
                + f'?empresa={empresa.uuid}'
            ),
        },
        'equipe': {
            'total': equipe_qs.count(), 'ativos': equipe_qs.filter(ativo=True).count(),
            'gestores': equipe_qs.filter(ativo=True).filter(proprietario=True).count() + equipe_qs.filter(ativo=True, administrador=True, proprietario=False).count(),
            'profissionais': profissionais_qs.filter(ativo=True).count(), 'membros': equipe_qs[:5],
        },
        'agenda': {
            'elegivel': agenda_elegivel, 'estado': agenda_estado,
            'mensagem': agenda_mensagem, 'profissionais': profissionais_ativos,
            'servicos': agenda_vinculos.count(), 'proximos_total': proximos.count(),
            'proximos': proximos[:5], 'disponibilidades': disponibilidades,
            'bloqueios': bloqueios,
        },
        'capacidades': capacidade_resumo,
        'links_total': empresa.links.filter(ativo=True, excluido_em__isnull=True).count(),
        'url_publica': reverse('publico:empresa', args=[empresa.slug]) if empresa.perfil_publico and empresa_operacional else '',
    }
