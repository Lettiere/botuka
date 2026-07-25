from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from .models import Candidatura, Vaga
from .permissions import vagas_administraveis


def painel_vagas(usuario, filtros):
    queryset = vagas_administraveis(usuario).select_related(
        'empresa', 'perfil_pessoa_fisica', 'usuario_criador',
    ).annotate(total_candidaturas=Count('candidaturas'))
    q = filtros.get('q', '').strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(titulo__icontains=q) | Q(descricao__icontains=q)
            | Q(empresa__nome_fantasia__icontains=q)
        )
    for parameter, field in (
        ('status', 'status'), ('modalidade', 'modalidade'),
        ('contrato', 'tipo_contrato'), ('cidade', 'cidade'),
    ):
        value = filtros.get(parameter)
        if value:
            queryset = queryset.filter(**{field: value})
    empresa = filtros.get('empresa')
    if empresa:
        queryset = queryset.filter(empresa__uuid=empresa)
    responsavel = filtros.get('responsavel', '').strip()[:100]
    if responsavel:
        queryset = queryset.filter(
            Q(usuario_responsavel__username__icontains=responsavel)
            | Q(usuario_responsavel__first_name__icontains=responsavel)
            | Q(usuario_responsavel__last_name__icontains=responsavel)
        )
    periodo = filtros.get('periodo')
    if periodo and periodo.isdigit():
        queryset = queryset.filter(criado_em__gte=timezone.now() - timedelta(days=min(int(periodo), 365)))
    return queryset.order_by('-criado_em')


def indicadores_vagas(queryset):
    hoje = timezone.localdate()
    dados = queryset.aggregate(
        total=Count('pk'),
        publicadas=Count('pk', filter=Q(status=Vaga.Status.PUBLICADA)),
        em_analise=Count('pk', filter=Q(status=Vaga.Status.EM_ANALISE)),
        rascunhos=Count('pk', filter=Q(status=Vaga.Status.RASCUNHO)),
        pausadas=Count('pk', filter=Q(status=Vaga.Status.PAUSADA)),
        encerradas=Count('pk', filter=Q(status=Vaga.Status.ENCERRADA)),
        expiradas=Count('pk', filter=Q(status=Vaga.Status.EXPIRADA)),
        candidaturas_total=Count('candidaturas', distinct=True),
        candidaturas_novas=Count(
            'candidaturas', filter=Q(candidaturas__status=Candidatura.Status.ENVIADA),
            distinct=True,
        ),
        proximas_vencimento=Count(
            'pk', filter=Q(
                encerramento__gte=hoje, encerramento__lte=hoje + timedelta(days=7),
                status=Vaga.Status.PUBLICADA,
            ),
        ),
    )
    dados['candidaturas'] = dados.pop('candidaturas_total')
    return dados
