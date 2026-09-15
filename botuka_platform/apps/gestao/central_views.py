"""Visões administrativas centrais e deliberadamente somente leitura.

Entidades históricas, editoriais, operacionais e financeiras só são mutadas
pelos serviços de domínio existentes. Esta camada oferece descoberta e
diagnóstico global sem criar atalhos de negócio.
"""

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import NoReverseMatch, reverse
from django.utils.dateparse import parse_date

from apps.gestao.decorators import master_required


def _models():
    from apps.advertising.models import (
        AuditoriaPublicidade, Campanha, CampanhaSegmentacao,
        ContratacaoPublicidade, Criativo, EntregaPublicidade,
        PlanoPublicitario, Posicionamento,
    )
    from apps.agenda.models import Agendamento, AgendaProfissional, AgendaProfissionalServico
    from apps.analytics.models import (
        AnalyticsDailyCompany, AnalyticsDailyCompanyTerm, AnalyticsEvent,
    )
    from apps.core.models import Auditoria
    from apps.events.models import Evento
    from apps.government.models import AcaoPublica, OrgaoPublico
    from apps.media.models import Episodio, Transmissao, Video
    from apps.news.models import Artigo, CategoriaNoticia
    from apps.payments.models import (
        ChaveIdempotencia, Cobranca, ItemCobranca, Pagamento, Transacao, Webhook,
    )
    from apps.products.models import Produto
    from apps.recruitment.models import Vaga
    from apps.services.models import Servico
    from apps.tourism.models import ExperienciaTuristica, LocalTuristico, RoteiroTuristico

    # kind: model, título, seção, campos de busca, colunas seguras, filtro status
    return {
        'artigos': (Artigo, 'Notícias e artigos', 'Conteúdo', ('titulo', 'slug', 'categoria__nome', 'autor_editorial__nome'), ('titulo', 'categoria', 'autor_editorial', 'status', 'publicado_em'), 'status'),
        'categorias-noticias': (CategoriaNoticia, 'Categorias de notícias', 'Conteúdo', ('nome', 'slug', 'categoria_pai__nome'), ('nome', 'categoria_pai', 'ordem', 'ativo'), 'ativo'),
        'eventos': (Evento, 'Eventos', 'Conteúdo', ('titulo', 'slug', 'categoria', 'empresa_promotora__nome_fantasia'), ('titulo', 'empresa_promotora', 'status', 'inicio', 'publicado_em'), 'status'),
        'videos': (Video, 'Vídeos do YuBotuka', 'Conteúdo', ('titulo', 'slug', 'canal__nome', 'categoria__nome'), ('titulo', 'canal', 'categoria', 'tipo', 'status', 'publicado_em'), 'status'),
        'episodios': (Episodio, 'Episódios do YuBotuka', 'Conteúdo', ('titulo', 'slug', 'programa__nome'), ('titulo', 'programa', 'temporada', 'tipo', 'status', 'publicado_em'), 'status'),
        'transmissoes': (Transmissao, 'Transmissões do YuBotuka', 'Conteúdo', ('titulo', 'slug', 'canal__nome', 'programa__nome'), ('titulo', 'canal', 'programa', 'status', 'data_prevista', 'inicio'), 'status'),
        'turismo': (LocalTuristico, 'Locais turísticos', 'Conteúdo', ('nome', 'slug', 'categoria__nome', 'cidade'), ('nome', 'categoria', 'cidade', 'status', 'publicado_em'), 'status'),
        'roteiros-turisticos': (RoteiroTuristico, 'Roteiros turísticos', 'Conteúdo', ('titulo', 'slug'), ('titulo', 'status', 'publicado_em', 'ativo'), 'status'),
        'experiencias-turisticas': (ExperienciaTuristica, 'Experiências turísticas', 'Conteúdo', ('titulo', 'slug', 'local__nome'), ('titulo', 'local', 'status', 'publicado_em', 'ativo'), 'status'),
        'orgaos-publicos': (OrgaoPublico, 'Órgãos públicos', 'Conteúdo', ('nome', 'sigla', 'slug'), ('nome', 'sigla', 'tipo', 'verificado', 'ativo'), 'ativo'),
        'acoes-publicas': (AcaoPublica, 'Conteúdo institucional', 'Conteúdo', ('titulo', 'slug', 'orgao__nome', 'cidade'), ('titulo', 'orgao', 'tipo', 'situacao', 'status', 'publicado_em'), 'status'),
        'produtos': (Produto, 'Produtos', 'Negócios', ('nome', 'codigo_interno', 'slug', 'empresa_proprietaria__nome_fantasia', 'categoria_taxonomia__nome'), ('nome', 'empresa_proprietaria', 'categoria_taxonomia', 'preco', 'disponibilidade', 'status', 'atualizado_em'), 'status'),
        'servicos': (Servico, 'Serviços', 'Negócios', ('titulo', 'slug', 'empresa__nome_fantasia', 'setor__nome', 'profissao__nome'), ('titulo', 'empresa', 'setor', 'profissao', 'preco_inicial', 'preco_final', 'status', 'atualizado_em'), 'status'),
        'profissionais-agenda': (AgendaProfissional, 'Profissionais da Agenda', 'Negócios', ('empresa_usuario__usuario__username', 'empresa_usuario__empresa__nome_fantasia', 'usuario_autonomo__username'), ('empresa_usuario.empresa', 'empresa_usuario.usuario', 'usuario_autonomo', 'ativo', 'atualizado_em'), 'ativo'),
        'servicos-agenda': (AgendaProfissionalServico, 'Serviços por profissional', 'Negócios', ('profissional__empresa_usuario__empresa__nome_fantasia', 'profissional__empresa_usuario__usuario__username', 'profissional__usuario_autonomo__username', 'servico__titulo'), ('profissional', 'servico', 'duracao_minutos', 'ativo', 'atualizado_em'), 'ativo'),
        'agendamentos': (Agendamento, 'Agendamentos', 'Negócios', ('cliente__username', 'cliente__email', 'profissional_servico__servico__titulo', 'profissional_servico__profissional__empresa_usuario__empresa__nome_fantasia', 'observacoes'), ('profissional_servico.profissional.empresa_usuario.empresa', 'profissional_servico.servico', 'cliente', 'status', 'inicio', 'fim', 'atualizado_em'), 'status'),
        'vagas': (Vaga, 'Vagas e oportunidades', 'Negócios', ('titulo', 'empresa__nome_fantasia', 'perfil_pessoa_fisica__username', 'categoria', 'area_atuacao', 'cidade'), ('titulo', 'empresa', 'perfil_pessoa_fisica', 'tipo_contrato', 'modalidade', 'cidade', 'status', 'atualizado_em'), 'status'),
        'planos-publicitarios': (PlanoPublicitario, 'Planos publicitários', 'Publicidade', ('nome', 'descricao'), ('nome', 'nivel', 'preco_diario', 'prioridade', 'exclusivo', 'limite_anunciantes', 'impressoes_por_usuario_dia', 'ativo'), 'ativo'),
        'posicionamentos-publicitarios': (Posicionamento, 'Posicionamentos publicitários', 'Publicidade', ('nome', 'codigo', 'contexto'), ('nome', 'codigo', 'contexto', 'largura', 'altura', 'tamanho_maximo_bytes', 'aceita_takeover', 'ativo'), 'ativo'),
        'campanhas': (Campanha, 'Campanhas publicitárias', 'Publicidade', ('nome', 'empresa__nome_fantasia', 'plano__nome'), ('nome', 'empresa', 'plano', 'status', 'inicio', 'fim', 'atualizado_em'), 'status'),
        'segmentacoes': (CampanhaSegmentacao, 'Segmentações publicitárias', 'Publicidade', ('campanha__nome',), ('campanha', 'termos'), ''),
        'criativos': (Criativo, 'Criativos publicitários', 'Publicidade', ('titulo', 'campanha__nome', 'posicionamento__nome'), ('titulo', 'campanha', 'posicionamento', 'tipo', 'aprovado', 'ativo'), 'ativo'),
        'contratacoes': (ContratacaoPublicidade, 'Contratações publicitárias', 'Publicidade', ('campanha__nome', 'cobranca__external_reference'), ('campanha', 'cobranca', 'quantidade_dias', 'valor_diario', 'valor_total', 'criado_em'), ''),
        'entregas': (EntregaPublicidade, 'Entregas publicitárias', 'Publicidade', ('campanha__nome', 'posicionamento__nome', 'contexto'), ('campanha', 'criativo', 'posicionamento', 'contexto', 'entregue_em', 'clicado_em'), ''),
        'auditoria-publicidade': (AuditoriaPublicidade, 'Auditoria de publicidade', 'Publicidade', ('acao', 'campanha__nome', 'usuario__username'), ('campanha', 'acao', 'usuario', 'criado_em'), 'acao'),
        'cobrancas': (Cobranca, 'Cobranças', 'Financeiro', ('external_reference', 'empresa__nome_fantasia'), ('uuid', 'empresa', 'origem', 'status', 'valor_total', 'vencimento'), 'status'),
        'itens-cobranca': (ItemCobranca, 'Itens de cobrança', 'Financeiro', ('codigo', 'descricao'), ('cobranca', 'codigo', 'descricao', 'quantidade', 'valor_total'), ''),
        'pagamentos': (Pagamento, 'Pagamentos', 'Financeiro', ('external_reference', 'referencia_gateway'), ('uuid', 'cobranca', 'gateway', 'status', 'valor', 'criado_em'), 'status'),
        'transacoes': (Transacao, 'Transações', 'Financeiro', ('referencia_gateway', 'idempotency_key'), ('uuid', 'pagamento', 'tipo', 'valor', 'sucesso', 'criado_em'), 'sucesso'),
        'webhooks': (Webhook, 'Webhooks', 'Financeiro', ('event_id', 'tipo', 'gateway'), ('gateway', 'event_id', 'tipo', 'assinatura_valida', 'processado_em', 'recebido_em'), 'assinatura_valida'),
        'idempotencia': (ChaveIdempotencia, 'Chaves de idempotência', 'Financeiro', ('chave', 'operacao'), ('chave', 'operacao', 'pagamento', 'criado_em'), ''),
        'analytics-eventos': (AnalyticsEvent, 'Eventos de analytics', 'Inteligência', ('event_name', 'source', 'path'), ('event_name', 'empresa', 'user', 'source', 'device_type', 'created_at'), 'event_name'),
        'analytics-empresas': (AnalyticsDailyCompany, 'Métricas diárias por empresa', 'Inteligência', ('empresa__nome_fantasia',), ('date', 'empresa', 'impressions', 'views', 'visitors', 'leads'), ''),
        'analytics-termos': (AnalyticsDailyCompanyTerm, 'Termos por empresa', 'Inteligência', ('term', 'empresa__nome_fantasia'), ('date', 'empresa', 'term', 'impressions', 'selections'), ''),
        'auditoria': (Auditoria, 'Auditoria da plataforma', 'Inteligência', ('acao', 'entidade', 'registro_id'), ('criado_em', 'usuario', 'acao', 'entidade', 'registro_id', 'sucesso'), 'acao'),
    }


def _config(kind):
    try:
        return _models()[kind]
    except KeyError as exc:
        raise Http404 from exc


CONTENT_KINDS = (
    'artigos', 'categorias-noticias', 'eventos', 'videos', 'episodios',
    'transmissoes', 'turismo', 'roteiros-turisticos',
    'experiencias-turisticas', 'orgaos-publicos', 'acoes-publicas',
)

_WORKFLOW_ROUTES = {
    'artigos': ('painel:news_artigo_lista', (), 'CRUD e fluxo editorial auditado'),
    'categorias-noticias': ('painel:news_auxiliar_lista', ('categorias',), 'CRUD de taxonomia editorial'),
    'eventos': ('painel:eventos_lista', (), 'CRUD e mudanças de status auditadas'),
    'videos': ('painel:yubotuka_videos', (), 'CRUD e moderação auditada'),
    'episodios': ('painel:yubotuka_episodios', (), 'CRUD editorial'),
    'transmissoes': ('painel:yubotuka_transmissoes', (), 'CRUD e moderação auditada'),
    'turismo': ('painel:turismo_entidade_lista', ('locais',), 'CRUD e publicação auditada'),
    'roteiros-turisticos': ('painel:turismo_entidade_lista', ('roteiros',), 'CRUD e publicação auditada'),
    'experiencias-turisticas': ('painel:turismo_entidade_lista', ('experiencias',), 'CRUD e publicação auditada'),
    'orgaos-publicos': ('painel:government_orgaopublico_lista', (), 'CRUD institucional'),
    'acoes-publicas': ('painel:government_acaopublica_lista', (), 'CRUD editorial institucional'),
}

_HEAVY_LIST_FIELDS = {
    'artigos': ('conteudo', 'resumo'), 'eventos': ('descricao',),
    'videos': ('descricao',), 'episodios': ('descricao',),
    'transmissoes': ('descricao',),
    'acoes-publicas': ('descricao', 'objetivo', 'resumo'),
}

BUSINESS_KINDS = (
    'produtos', 'servicos', 'profissionais-agenda', 'servicos-agenda',
    'agendamentos', 'vagas',
)

_BUSINESS_WORKFLOW_ROUTES = {
    'produtos': ('painel:produtos_lista', (), 'CRUD e moderação auditada'),
    'servicos': ('painel:servicos_lista', (), 'CRUD operacional por prestador'),
    'vagas': ('painel:vagas_lista', (), 'CRUD e publicação auditada'),
}

_BUSINESS_HEAVY_LIST_FIELDS = {
    'produtos': ('descricao_completa', 'especificacoes', 'garantia'),
    'servicos': ('descricao_completa', 'experiencia'),
    'agendamentos': ('observacoes',),
    'vagas': ('descricao', 'requisitos', 'responsabilidades', 'beneficios'),
}

_BUSINESS_SELECT_RELATED = {
    'profissionais-agenda': (
        'empresa_usuario__empresa', 'empresa_usuario__usuario', 'usuario_autonomo',
    ),
    'servicos-agenda': (
        'profissional__empresa_usuario__empresa',
        'profissional__empresa_usuario__usuario',
        'profissional__usuario_autonomo', 'servico',
    ),
    'agendamentos': (
        'cliente', 'profissional_servico__servico',
        'profissional_servico__profissional__empresa_usuario__empresa',
        'profissional_servico__profissional__empresa_usuario__usuario',
        'profissional_servico__profissional__usuario_autonomo',
    ),
}

ADVERTISING_KINDS = (
    'planos-publicitarios', 'posicionamentos-publicitarios', 'campanhas',
    'segmentacoes', 'criativos', 'contratacoes', 'entregas',
    'auditoria-publicidade',
)

_ADVERTISING_WORKFLOW_ROUTES = {
    'planos-publicitarios': ('advertising:configuracao_comercial', (), 'Configuração comercial MASTER'),
    'posicionamentos-publicitarios': ('advertising:configuracao_comercial', (), 'Configuração comercial MASTER'),
    'campanhas': ('advertising:campanha_administracao', (), 'Moderação auditada MASTER'),
}


def _content_context(kind):
    if kind not in CONTENT_KINDS:
        return {}
    route, args, capability = _WORKFLOW_ROUTES[kind]
    try:
        workflow_url = reverse(route, args=args)
    except NoReverseMatch:
        workflow_url = ''
    models = _models()
    return {
        'content_modules': [
            {'kind': item, 'title': models[item][1]} for item in CONTENT_KINDS
        ],
        'workflow_url': workflow_url,
        'capability': capability,
    }


def _business_context(kind):
    if kind not in BUSINESS_KINDS:
        return {}
    workflow = _BUSINESS_WORKFLOW_ROUTES.get(kind)
    workflow_url = ''
    capability = 'Operação pelo contexto de empresa na Agenda'
    if workflow:
        route, args, capability = workflow
        try:
            workflow_url = reverse(route, args=args)
        except NoReverseMatch:
            workflow_url = ''
    models = _models()
    return {
        'business_modules': [
            {'kind': item, 'title': models[item][1]} for item in BUSINESS_KINDS
        ],
        'workflow_url': workflow_url,
        'capability': capability,
    }


def _advertising_context(kind):
    if kind not in ADVERTISING_KINDS:
        return {}
    workflow = _ADVERTISING_WORKFLOW_ROUTES.get(kind)
    workflow_url = ''
    capability = 'Consulta global somente leitura'
    if workflow:
        route, args, capability = workflow
        try:
            workflow_url = reverse(route, args=args)
        except NoReverseMatch:
            workflow_url = ''
    models = _models()
    return {
        'advertising_modules': [
            {'kind': item, 'title': models[item][1]} for item in ADVERTISING_KINDS
        ],
        'workflow_url': workflow_url,
        'capability': capability,
    }


@master_required
def lista(request, kind):
    model, title, section, search_fields, columns, filter_field = _config(kind)
    manager = getattr(model, 'all_objects', model.objects)
    qs = manager.all()
    if kind in _HEAVY_LIST_FIELDS:
        qs = qs.defer(*_HEAVY_LIST_FIELDS[kind])
    if kind in _BUSINESS_HEAVY_LIST_FIELDS:
        qs = qs.defer(*_BUSINESS_HEAVY_LIST_FIELDS[kind])
    relation_names = {
        name.split('__', 1)[0] for name in (*search_fields, *columns)
        if name.split('__', 1)[0] in {
            field.name for field in model._meta.fields if field.is_relation
        }
    }
    if relation_names:
        qs = qs.select_related(*relation_names)
    if kind in _BUSINESS_SELECT_RELATED:
        qs = qs.select_related(*_BUSINESS_SELECT_RELATED[kind])
    query = request.GET.get('q', '').strip()[:120]
    selected = request.GET.get('status', '').strip()[:80]
    date_from = parse_date(request.GET.get('de', ''))
    date_to = parse_date(request.GET.get('ate', ''))
    if query:
        predicate = Q()
        for field in search_fields:
            predicate |= Q(**{f'{field}__icontains': query})
        qs = qs.filter(predicate)
    if selected and filter_field:
        qs = qs.filter(**{filter_field: selected})
    date_field = next((name for name in ('criado_em', 'created_at', 'recebido_em', 'date') if name in {f.name for f in model._meta.fields}), '')
    if date_field and date_from:
        qs = qs.filter(**{f'{date_field}__date__gte': date_from}) if date_field != 'date' else qs.filter(date__gte=date_from)
    if date_field and date_to:
        qs = qs.filter(**{f'{date_field}__date__lte': date_to}) if date_field != 'date' else qs.filter(date__lte=date_to)
    order_field = next((name for name in ('-criado_em', '-created_at', '-recebido_em', '-date', '-pk') if name.lstrip('-') in {f.name for f in model._meta.fields}), '-pk')
    page_obj = Paginator(qs.order_by(order_field), 25).get_page(request.GET.get('page'))
    choices = []
    if filter_field:
        field = model._meta.get_field(filter_field)
        choices = list(field.choices) if field.choices else [('1', 'Sim'), ('0', 'Não')] if field.get_internal_type() == 'BooleanField' else []
    context = {
        'kind': kind, 'title': title, 'section': section, 'columns': columns,
        'page_obj': page_obj, 'query': query, 'selected_filter': selected,
        'filter_choices': choices, 'read_only': True,
        'is_paginated': page_obj.paginator.num_pages > 1,
        'date_field': date_field, 'date_from': date_from, 'date_to': date_to,
    }
    context.update(_content_context(kind))
    context.update(_business_context(kind))
    context.update(_advertising_context(kind))
    return render(request, 'gestao/central/lista.html', context)


@master_required
def detalhe(request, kind, pk):
    model, title, section, _search_fields, columns, _filter_field = _config(kind)
    manager = getattr(model, 'all_objects', model.objects)
    relation_names = [field for field in columns if field in {
        item.name for item in model._meta.fields if item.is_relation
    }]
    qs = manager.select_related(*relation_names) if relation_names else manager.all()
    if kind in _BUSINESS_SELECT_RELATED:
        qs = qs.select_related(*_BUSINESS_SELECT_RELATED[kind])
    context = {
        'kind': kind, 'title': title.rstrip('s'), 'section': section,
        'object': get_object_or_404(qs, pk=pk),
        'columns': columns, 'read_only': True,
    }
    context.update(_content_context(kind))
    context.update(_business_context(kind))
    context.update(_advertising_context(kind))
    return render(request, 'gestao/central/detalhe.html', context)
