from __future__ import annotations

import hashlib
import math
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.organizations.permissions import usuario_pode_gerenciar_empresa
from apps.payments.models import Cobranca
from apps.payments.services import criar_cobranca

from .models import AuditoriaPublicidade, Campanha, ContratacaoPublicidade, EntregaPublicidade, Posicionamento


def _auditar(campanha, acao, usuario=None, **detalhes):
    return AuditoriaPublicidade.objects.create(campanha=campanha, usuario=usuario, acao=acao, detalhes=detalhes)


def calcular_preco(campanha):
    dias = max(1, math.ceil((campanha.fim - campanha.inicio).total_seconds() / 86400))
    valor_diario = Decimal(campanha.plano.preco_diario)
    return dias, valor_diario, (valor_diario * dias).quantize(Decimal('0.01'))


def _conflitos(campanha, *, lock=False):
    queryset = Campanha.objects.filter(
        posicionamentos__in=campanha.posicionamentos.all(), inicio__lt=campanha.fim,
        fim__gt=campanha.inicio,
        status__in=[Campanha.Status.AGUARDANDO_APROVACAO, Campanha.Status.APROVADA,
                    Campanha.Status.ATIVA, Campanha.Status.PAUSADA],
    ).exclude(pk=campanha.pk).distinct()
    if lock:
        ids = list(queryset.values_list('pk', flat=True))
        list(Campanha.objects.select_for_update().filter(pk__in=ids).values_list('pk', flat=True))
    return queryset


def validar_disponibilidade(campanha, *, lock=False):
    if campanha.plano.nivel == campanha.plano.Nivel.ZERO and not campanha.posicionamentos.filter(aceita_takeover=True).exists():
        raise ValidationError('Takeover exige posicionamento compatível.')
    conflitos = _conflitos(campanha, lock=lock)
    if campanha.plano.exclusivo and conflitos.exists():
        raise ValidationError('Já existe campanha no período de exclusividade solicitado.')
    if conflitos.filter(plano__exclusivo=True).exists():
        raise ValidationError('O período está reservado por campanha exclusiva.')
    if campanha.plano.limite_anunciantes:
        empresas_ativas = conflitos.values('empresa_id').distinct().count()
        if empresas_ativas >= campanha.plano.limite_anunciantes:
            raise ValidationError('Limite de anunciantes do posicionamento atingido.')
    return True


def _ativar_se_elegivel(campanha, *, usuario=None):
    agora = timezone.now()
    if (campanha.status == Campanha.Status.APROVADA and campanha.contratacao.esta_paga
            and campanha.inicio <= agora < campanha.fim):
        anterior = campanha.status
        campanha.status = Campanha.Status.ATIVA
        campanha.save(update_fields=['status', 'atualizado_em'])
        _auditar(campanha, 'ATIVADA', usuario, anterior=anterior, novo=campanha.status)
    return campanha


@transaction.atomic
def contratar_campanha(*, campanha_id, usuario) -> ContratacaoPublicidade:
    campanha = Campanha.objects.select_for_update().select_related('empresa', 'plano').get(pk=campanha_id)
    if not usuario_pode_gerenciar_empresa(usuario, campanha.empresa):
        raise PermissionDenied
    if campanha.status != Campanha.Status.RASCUNHO:
        raise ValidationError('A campanha já foi contratada ou não está disponível.')
    if not campanha.posicionamentos.exists() or not campanha.criativos.exists():
        raise ValidationError('A campanha exige posicionamento e criativo.')
    segmentacao = getattr(campanha, 'segmentacao', None)
    if (campanha.plano.nivel == campanha.plano.Nivel.TRES
            and not (segmentacao and (
                segmentacao.categorias.exists() or segmentacao.subcategorias.exists()
                or segmentacao.cnaes.exists() or segmentacao.termos
            ))):
        raise ValidationError('A segmentação obrigatória para o nível do plano não foi informada.')
    validar_disponibilidade(campanha, lock=True)
    dias, valor_diario, total = calcular_preco(campanha)
    cobranca = criar_cobranca(
        empresa=campanha.empresa,
        usuario=usuario,
        origem=Cobranca.Origem.PUBLICIDADE,
        external_reference=f'advertising:{campanha.uuid}',
        metadata={'campanha_uuid': str(campanha.uuid)},
        itens=[{
        'codigo': f'PUBLICIDADE-{campanha.uuid}', 'descricao': f'Campanha {campanha.nome}',
        'quantidade': dias, 'valor_unitario': valor_diario,
    }])
    contratacao = ContratacaoPublicidade.objects.create(campanha=campanha, cobranca=cobranca, quantidade_dias=dias, valor_diario=valor_diario, valor_total=total)
    anterior = campanha.status
    campanha.status = Campanha.Status.AGUARDANDO_APROVACAO
    campanha.save(update_fields=['status', 'atualizado_em'])
    _auditar(campanha, 'CONTRATADA', usuario, anterior=anterior, novo=campanha.status,
             valor_total=str(total), cobranca=str(cobranca.uuid))
    return contratacao


@transaction.atomic
def sincronizar_status_pagamento(*, campanha_id) -> Campanha:
    campanha = Campanha.objects.select_for_update().get(pk=campanha_id)
    if campanha.contratacao.cobranca.status == Cobranca.Status.PAGA:
        _auditar(campanha, 'PAGAMENTO_CONFIRMADO', novo=campanha.status)
        return _ativar_se_elegivel(campanha)
    return campanha


@transaction.atomic
def aprovar_campanha(*, campanha_id, usuario) -> Campanha:
    from apps.accounts.permissions import usuario_e_master
    if not usuario_e_master(usuario):
        raise PermissionDenied
    campanha = Campanha.objects.select_for_update().get(pk=campanha_id)
    if campanha.status != Campanha.Status.AGUARDANDO_APROVACAO:
        raise ValidationError('Campanha não está aguardando aprovação.')
    if not campanha.criativos.filter(ativo=True).exists():
        raise ValidationError('Campanha sem criativo ativo.')
    campanha.criativos.filter(ativo=True).update(aprovado=True)
    campanha.aprovada_em = timezone.now()
    campanha.aprovada_por = usuario
    anterior = campanha.status
    campanha.status = Campanha.Status.APROVADA
    campanha.save(update_fields=['aprovada_em', 'aprovada_por', 'status', 'atualizado_em'])
    _auditar(campanha, 'APROVADA', usuario, anterior=anterior, novo=campanha.status)
    return _ativar_se_elegivel(campanha, usuario=usuario)


@transaction.atomic
def moderar_campanha(*, campanha_id, usuario, acao, motivo=''):
    from apps.accounts.permissions import usuario_e_master
    if not usuario_e_master(usuario):
        raise PermissionDenied
    campanha = Campanha.objects.select_for_update().get(pk=campanha_id)
    anterior = campanha.status
    transicoes = {
        'REJEITAR': ({Campanha.Status.AGUARDANDO_APROVACAO}, Campanha.Status.REJEITADA),
        'PAUSAR': ({Campanha.Status.ATIVA}, Campanha.Status.PAUSADA),
        'REATIVAR': ({Campanha.Status.PAUSADA}, Campanha.Status.APROVADA),
    }
    permitidos, novo = transicoes.get(acao, (set(), None))
    if campanha.status not in permitidos:
        raise ValidationError('Transição operacional inválida.')
    if acao == 'REJEITAR' and not motivo.strip():
        raise ValidationError('Informe o motivo da rejeição.')
    campanha.status = novo
    if acao == 'REJEITAR':
        campanha.motivo_rejeicao = motivo.strip()
    campanha.save(update_fields=['status', 'motivo_rejeicao', 'atualizado_em'])
    _auditar(campanha, acao, usuario, anterior=anterior, novo=novo, motivo=motivo.strip())
    return _ativar_se_elegivel(campanha, usuario=usuario) if acao == 'REATIVAR' else campanha


@transaction.atomic
def cancelar_campanha(*, campanha_id, usuario, motivo=''):
    campanha = Campanha.objects.select_for_update().select_related('empresa').get(pk=campanha_id)
    if not usuario_pode_gerenciar_empresa(usuario, campanha.empresa):
        raise PermissionDenied
    if campanha.status in {Campanha.Status.ATIVA, Campanha.Status.ENCERRADA, Campanha.Status.CANCELADA}:
        raise ValidationError('Campanha não pode ser cancelada neste estado.')
    anterior = campanha.status
    campanha.status = Campanha.Status.CANCELADA
    campanha.save(update_fields=['status', 'atualizado_em'])
    _auditar(campanha, 'CANCELADA', usuario, anterior=anterior, novo=campanha.status,
             motivo=motivo.strip())
    return campanha


def _segmentacao_q(*, categoria=None, subcategoria=None, cnae=None, termo=''):
    query = Q(plano__nivel__in=[0, 1, 2, 4]) | Q(segmentacao__isnull=True)
    if categoria:
        query |= Q(segmentacao__categorias=categoria)
    if subcategoria:
        query |= Q(segmentacao__subcategorias=subcategoria)
    if cnae:
        query |= Q(segmentacao__cnaes=cnae)
    if termo.strip():
        query |= Q(segmentacao__termos__contains=[termo.strip().casefold()])
    return query


def identidade_visitante(request):
    if request.user.is_authenticated:
        return f'user:{request.user.pk}'
    if not request.session.session_key:
        request.session.create()
    return f'session:{request.session.session_key}'


def _registrar_analytics(request, entrega, evento):
    from apps.core.seo.context import _consent
    if not _consent(request).get('analytics'):
        return None
    from apps.analytics.services import register_event
    identidade = identidade_visitante(request)
    return register_event(request, {
        'event_name': evento,
        'visitor_id': identidade,
        'session_id': request.session.session_key or identidade,
        'object_type': 'ad_campaign',
        'object_id': str(entrega.campanha.uuid),
        'path': request.path,
        'dedupe_key': f'{evento}:{entrega.uuid}',
        'metadata': {'context': entrega.contexto, 'position': entrega.posicionamento.codigo},
    })


@transaction.atomic
def entregar_publicidade(*, posicionamento_codigo, visitante_id, contexto, categoria=None, subcategoria=None, cnae=None, termo='', agora=None):
    agora = agora or timezone.now()
    posicionamento = Posicionamento.objects.get(codigo=posicionamento_codigo, ativo=True)
    visitante_hash = hashlib.sha256(str(visitante_id).encode()).hexdigest()
    qs = Campanha.objects.filter(
        status=Campanha.Status.ATIVA, aprovada_em__isnull=False, inicio__lte=agora, fim__gt=agora,
        posicionamentos=posicionamento, contratacao__cobranca__status=Cobranca.Status.PAGA,
        criativos__ativo=True, criativos__aprovado=True,
    ).filter(
        _segmentacao_q(
            categoria=categoria, subcategoria=subcategoria, cnae=cnae, termo=termo,
        )
    ).select_related('plano', 'segmentacao').annotate(
        impressoes_visitante=Count(
            'entregas',
            filter=Q(
                entregas__visitante_hash=visitante_hash,
                entregas__entregue_em__gte=agora - timedelta(hours=24),
            ),
            distinct=True,
        ),
        impressoes_totais=Count('entregas', distinct=True),
    ).filter(
        impressoes_visitante__lt=F('plano__impressoes_por_usuario_dia'),
    ).distinct()
    termo_norm = termo.strip().casefold()
    candidatas = [c for c in qs if not hasattr(c, 'segmentacao') or not c.segmentacao.termos or termo_norm in c.segmentacao.termos]
    elegiveis = candidatas
    if not elegiveis:
        return None
    exclusivas = [c for c in elegiveis if c.plano.exclusivo]
    if exclusivas:
        elegiveis = exclusivas
    elegiveis.sort(
        key=lambda c: (
            c.plano.nivel, -c.plano.prioridade, c.impressoes_totais, c.pk,
        )
    )
    campanha = elegiveis[0]
    criativo = campanha.criativos.filter(ativo=True, aprovado=True).annotate(total=Count('entregas')).order_by('total', 'pk').first()
    return EntregaPublicidade.objects.create(campanha=campanha, criativo=criativo, posicionamento=posicionamento, visitante_hash=visitante_hash, contexto=contexto)


def entregar_para_request(request, *, posicionamento_codigo, contexto, categoria=None,
                           subcategoria=None, cnae=None, termo=''):
    cache = getattr(request, '_advertising_slots', set())
    if posicionamento_codigo in cache:
        return None
    cache.add(posicionamento_codigo)
    request._advertising_slots = cache
    try:
        entrega = entregar_publicidade(
            posicionamento_codigo=posicionamento_codigo,
            visitante_id=identidade_visitante(request), contexto=contexto,
            categoria=categoria, subcategoria=subcategoria, cnae=cnae, termo=termo,
        )
    except Posicionamento.DoesNotExist:
        return None
    if entrega:
        _registrar_analytics(request, entrega, 'ad_impression')
    return entrega


@transaction.atomic
def registrar_clique(*, entrega_uuid, request=None):
    entrega = EntregaPublicidade.objects.select_for_update().get(uuid=entrega_uuid)
    if entrega.clicado_em is None:
        entrega.clicado_em = timezone.now()
        entrega.save(update_fields=['clicado_em'])
        if request is not None:
            _registrar_analytics(request, entrega, 'ad_click')
    return entrega


def url_destino_segura(entrega):
    value = entrega.criativo.url_destino
    parsed = urlsplit(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        return None
    return value
