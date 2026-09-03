"""Resumo operacional seguro e centralizado do painel de uma empresa."""

from django.urls import reverse
from apps.agenda.dashboard import construir_central_agenda
from apps.agenda.models import AgendaProfissional
from apps.organizations.models import Capacidade, Empresa, EmpresaCapacidade
from apps.products.models import Produto
from apps.recruitment.models import Vaga
from apps.recruitment.selectors import indicadores_vagas
from apps.products.services import calcular_limite
from apps.services.models import Servico


def construir_painel_empresa(*, empresa, usuario, permissoes):
    central_agenda = construir_central_agenda(empresa)
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
            'elegivel': agenda_elegivel, 'estado': central_agenda['estado'],
            'mensagem': central_agenda['mensagem'],
            'profissionais': central_agenda['profissionais_ativos'],
            'servicos': central_agenda['servicos_vinculados'],
            'proximos_total': central_agenda['proximos_total'],
            'proximos': central_agenda['proximos'],
            'disponibilidades': (
                central_agenda['disponibilidades_semanais']
                + central_agenda['disponibilidades_especificas_total']
            ),
            'bloqueios': central_agenda['bloqueios_ativos'],
        },
        'capacidades': capacidade_resumo,
        'links_total': empresa.links.filter(ativo=True, excluido_em__isnull=True).count(),
        'url_publica': reverse('publico:empresa', args=[empresa.slug]) if empresa.perfil_publico and empresa_operacional else '',
    }
