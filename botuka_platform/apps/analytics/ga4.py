from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GA4Overview:
    active_users: int = 0
    sessions: int = 0
    page_views: int = 0
    available: bool = False
    error: str = ""


def _as_int(value: str) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0



def company_public_paths(empresa) -> tuple[str, ...]:
    from django.urls import reverse
    from django.utils import timezone

    from apps.events.models import Evento
    from apps.news.models import ArtigoFonte
    from apps.news.selectors import artigos_publicos
    from apps.products.public_catalog import produtos_publicos
    from apps.recruitment.models import Vaga
    from apps.services.models import Servico
    from apps.sports.models import Atleta, Campeonato, Disputa, Equipe
    from apps.tourism.models import GuiaTuristico, LocalTuristico, TurismoStatus

    paths: set[str] = set()

    # Perfil público da empresa
    if (
        empresa.ativo
        and empresa.perfil_publico
        and empresa.status == empresa.Status.ATIVA
        and empresa.slug
    ):
        paths.add(reverse("publico:empresa", args=[empresa.slug]))

    # Serviços
    for slug in (
        Servico.objects.publicamente_visiveis()
        .filter(empresa=empresa)
        .values_list("slug", flat=True)
    ):
        if slug:
            paths.add(reverse("publico:servico", args=[slug]))

    # Produtos
    for slug in (
        produtos_publicos()
        .filter(empresa_proprietaria=empresa)
        .values_list("slug", flat=True)
    ):
        if slug:
            paths.add(reverse("products:detalhe", args=[slug]))

    # Notícias:
    # mesma regra conservadora do Analytics interno:
    # somente artigo com exatamente uma organização principal válida.
    article_ids = (
        ArtigoFonte.objects.filter(
            organizacao=empresa,
            principal=True,
            ativo=True,
            excluido_em__isnull=True,
        )
        .values_list("artigo_id", flat=True)
        .distinct()
    )

    artigos = artigos_publicos().filter(pk__in=article_ids)

    for artigo in artigos:
        principals = (
            ArtigoFonte.objects.filter(
                artigo=artigo,
                organizacao__isnull=False,
                principal=True,
                ativo=True,
                excluido_em__isnull=True,
            )
            .values_list("organizacao_id", flat=True)
            .distinct()
        )

        if list(principals[:2]) == [empresa.pk]:
            paths.add(artigo.get_absolute_url())

    # Eventos
    for evento in Evento.objects.filter(
        empresa_promotora=empresa,
        status=Evento.Status.PUBLICADO,
        publico=True,
        ativo=True,
        removido_em__isnull=True,
    ):
        paths.add(evento.get_absolute_url())

    # Vagas
    for slug in (
        Vaga.objects.filter(
            empresa=empresa,
            status=Vaga.Status.PUBLICADA,
            ativo=True,
            excluido_em__isnull=True,
            publicado_em__isnull=False,
        )
        .filter(
            models.Q(encerramento__isnull=True)
            | models.Q(encerramento__gte=timezone.localdate())
        )
        .values_list("slug", flat=True)
    ):
        if slug:
            paths.add(reverse("recruitment_public:vaga", args=[slug]))

    # Turismo
    for slug in (
        LocalTuristico.objects.filter(
            empresa_responsavel=empresa,
            status=TurismoStatus.PUBLICADO,
        )
        .values_list("slug", flat=True)
    ):
        if slug:
            paths.add(reverse("tourism_public:local", args=[slug]))

    for slug in (
        GuiaTuristico.objects.filter(
            empresa=empresa,
            status=TurismoStatus.PUBLICADO,
            verificado=True,
        )
        .values_list("slug", flat=True)
    ):
        if slug:
            paths.add(reverse("tourism_public:guia", args=[slug]))

    # Esportes
    public_teams = Equipe.objects.filter(
        organizacao__empresa=empresa,
        ativo=True,
        excluido_em__isnull=True,
        organizacao__ativo=True,
        organizacao__verificado=True,
        organizacao__excluido_em__isnull=True,
    )

    for slug in public_teams.values_list("slug", flat=True):
        if slug:
            paths.add(reverse("sports_public:equipe", args=[slug]))

    for athlete_uuid in (
        Atleta.objects.filter(
            equipe__in=public_teams,
            publico=True,
            ativo=True,
            excluido_em__isnull=True,
        )
        .values_list("uuid", flat=True)
    ):
        paths.add(reverse("sports_public:atleta", args=[athlete_uuid]))

    public_championships = Campeonato.objects.filter(
        organizacao__empresa=empresa,
        ativo=True,
        excluido_em__isnull=True,
        status__in=(
            Campeonato.Status.INSCRICOES,
            Campeonato.Status.AGENDADO,
            Campeonato.Status.EM_ANDAMENTO,
            Campeonato.Status.FINALIZADO,
        ),
        organizacao__ativo=True,
        organizacao__verificado=True,
        organizacao__excluido_em__isnull=True,
    )

    for slug in public_championships.values_list("slug", flat=True):
        if slug:
            paths.add(reverse("sports_public:campeonato", args=[slug]))

    for jogo_uuid in (
        Disputa.objects.filter(
            campeonato__in=public_championships,
            ativo=True,
            excluido_em__isnull=True,
            status__in=(
                Disputa.Status.AGENDADA,
                Disputa.Status.EM_ANDAMENTO,
                Disputa.Status.ENCERRADA,
                Disputa.Status.ADIADA,
                Disputa.Status.WO,
            ),
        )
        .values_list("uuid", flat=True)
    ):
        paths.add(reverse("sports_public:jogo", args=[jogo_uuid]))

    # Agenda da própria empresa
    if empresa.slug:
        paths.add(reverse("agenda_public:empresa", args=[empresa.slug]))

    return tuple(sorted(paths))



def _ga4_date(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def get_company_ga4_overview(
    empresa,
    start_date,
    end_date,
) -> GA4Overview:
    from hashlib import sha256

    from django.core.cache import cache

    if not getattr(settings, "ENABLE_GA4_DATA_API", False):
        return GA4Overview(error="GA4 indisponível.")

    property_id = str(
        getattr(settings, "GA4_PROPERTY_ID", "")
    ).strip()

    if not property_id:
        return GA4Overview(error="GA4 indisponível.")

    paths = company_public_paths(empresa)

    if not paths:
        return GA4Overview(available=True)

    start_date = str(start_date)
    end_date = str(end_date)

    paths_hash = sha256(
        "\n".join(paths).encode("utf-8")
    ).hexdigest()[:16]

    cache_key = (
        f"analytics:ga4:company:{empresa.uuid}:"
        f"{start_date}:{end_date}:{paths_hash}"
    )

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Filter,
            FilterExpression,
            Metric,
            RunReportRequest,
        )

        client = BetaAnalyticsDataClient()

        response = client.run_report(
            RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=[
                    DateRange(
                        start_date=_ga4_date(start_date),
                        end_date=_ga4_date(end_date),
                    )
                ],
                metrics=[
                    Metric(name="activeUsers"),
                    Metric(name="sessions"),
                    Metric(name="screenPageViews"),
                ],
                dimension_filter=FilterExpression(
                    filter=Filter(
                        field_name="pagePath",
                        in_list_filter=Filter.InListFilter(
                            values=list(paths),
                            case_sensitive=True,
                        ),
                    )
                ),
            )
        )

        if not response.rows:
            result = GA4Overview(available=True)
        else:
            values = response.rows[0].metric_values

            result = GA4Overview(
                active_users=_as_int(values[0].value),
                sessions=_as_int(values[1].value),
                page_views=_as_int(values[2].value),
                available=True,
            )

        cache.set(cache_key, result, 600)

        return result

    except Exception:
        logger.exception(
            "Falha ao consultar GA4 da empresa %s.",
            empresa.uuid,
        )

        return GA4Overview(
            error="Google Analytics temporariamente indisponível."
        )


def get_ga4_overview(
    start_date: str = "7daysAgo",
    end_date: str = "today",
) -> GA4Overview:
    from django.core.cache import cache

    if not getattr(settings, "ENABLE_GA4_DATA_API", False):
        return GA4Overview(error="GA4 indisponível.")

    property_id = str(
        getattr(settings, "GA4_PROPERTY_ID", "")
    ).strip()

    if not property_id:
        return GA4Overview(error="GA4 indisponível.")

    cache_key = (
        f"analytics:ga4:global:{property_id}:"
        f"{start_date}:{end_date}"
    )

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Metric,
            RunReportRequest,
        )

        client = BetaAnalyticsDataClient()

        response = client.run_report(
            RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=[
                    DateRange(
                        start_date=_ga4_date(start_date),
                        end_date=_ga4_date(end_date),
                    )
                ],
                metrics=[
                    Metric(name="activeUsers"),
                    Metric(name="sessions"),
                    Metric(name="screenPageViews"),
                ],
            )
        )

        if not response.rows:
            result = GA4Overview(available=True)
        else:
            values = response.rows[0].metric_values

            result = GA4Overview(
                active_users=_as_int(values[0].value),
                sessions=_as_int(values[1].value),
                page_views=_as_int(values[2].value),
                available=True,
            )

        cache.set(cache_key, result, 600)
        return result

    except Exception:
        logger.exception(
            "Falha ao consultar Google Analytics Data API."
        )

        result = GA4Overview(
            error="Google Analytics temporariamente indisponível."
        )

        # Evita bombardear a API durante indisponibilidade temporária.
        cache.set(cache_key, result, 60)

        return result


# ============================================================
# Analytics 360 — camada reutilizável de relatórios GA4
# ============================================================

def _ga4_number(value):
    """
    Converte valores retornados pelo GA4 preservando inteiros e decimais.
    """
    if value in (None, ""):
        return 0

    try:
        if "." in str(value):
            return float(value)
        return int(value)
    except (TypeError, ValueError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0


def get_ga4_report(
    *,
    dimensions=(),
    metrics=(),
    start_date="7daysAgo",
    end_date="today",
    paths=None,
    limit=100,
    order_bys=(),
):
    """
    Executa um relatório genérico na GA4 Data API.

    Retorno:
        {
            "available": bool,
            "error": str,
            "dimensions": [...],
            "metrics": [...],
            "rows": [
                {
                    "dimension_name": "...",
                    "metric_name": 123,
                }
            ],
        }

    Se `paths` for informado, restringe o relatório às páginas públicas
    associadas à entidade/empresa.
    """
    from hashlib import sha256

    from django.core.cache import cache

    if not getattr(settings, "ENABLE_GA4_DATA_API", False):
        return {
            "available": False,
            "error": "GA4 indisponível.",
            "dimensions": list(dimensions),
            "metrics": list(metrics),
            "rows": [],
        }

    property_id = str(
        getattr(settings, "GA4_PROPERTY_ID", "")
    ).strip()

    if not property_id:
        return {
            "available": False,
            "error": "GA4 indisponível.",
            "dimensions": list(dimensions),
            "metrics": list(metrics),
            "rows": [],
        }

    dimensions = tuple(dimensions)
    metrics = tuple(metrics)

    if not metrics:
        return {
            "available": False,
            "error": "Nenhuma métrica GA4 informada.",
            "dimensions": list(dimensions),
            "metrics": [],
            "rows": [],
        }

    if len(metrics) > 10:
        return {
            "available": False,
            "error": "O GA4 aceita no máximo 10 métricas por relatório.",
            "dimensions": list(dimensions),
            "metrics": list(metrics),
            "rows": [],
        }

    normalized_paths = tuple(sorted(set(paths or ())))

    cache_signature = "|".join(
        [
            property_id,
            str(start_date),
            str(end_date),
            ",".join(dimensions),
            ",".join(metrics),
            ",".join(normalized_paths),
            str(limit),
            ",".join(order_bys),
        ]
    )

    signature = sha256(
        cache_signature.encode("utf-8")
    ).hexdigest()[:24]

    cache_key = f"analytics:ga4:report:{signature}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Filter,
            FilterExpression,
            Metric,
            OrderBy,
            RunReportRequest,
        )

        request_kwargs = {
            "property": f"properties/{property_id}",
            "date_ranges": [
                DateRange(
                    start_date=_ga4_date(start_date),
                    end_date=_ga4_date(end_date),
                )
            ],
            "dimensions": [
                Dimension(name=name)
                for name in dimensions
            ],
            "metrics": [
                Metric(name=name)
                for name in metrics
            ],
            "limit": int(limit),
        }

        if normalized_paths:
            request_kwargs["dimension_filter"] = FilterExpression(
                filter=Filter(
                    field_name="pagePath",
                    in_list_filter=Filter.InListFilter(
                        values=list(normalized_paths),
                        case_sensitive=True,
                    ),
                )
            )

        if order_bys:
            ga4_order_bys = []

            for field_name in order_bys:
                descending = True

                if field_name.startswith("+"):
                    descending = False
                    field_name = field_name[1:]
                elif field_name.startswith("-"):
                    field_name = field_name[1:]

                if field_name in metrics:
                    ga4_order_bys.append(
                        OrderBy(
                            metric=OrderBy.MetricOrderBy(
                                metric_name=field_name
                            ),
                            desc=descending,
                        )
                    )
                elif field_name in dimensions:
                    ga4_order_bys.append(
                        OrderBy(
                            dimension=OrderBy.DimensionOrderBy(
                                dimension_name=field_name
                            ),
                            desc=descending,
                        )
                    )

            if ga4_order_bys:
                request_kwargs["order_bys"] = ga4_order_bys

        client = BetaAnalyticsDataClient()

        response = client.run_report(
            RunReportRequest(**request_kwargs)
        )

        rows = []

        for row in response.rows:
            item = {}

            for index, name in enumerate(dimensions):
                item[name] = row.dimension_values[index].value

            for index, name in enumerate(metrics):
                item[name] = _ga4_number(
                    row.metric_values[index].value
                )

            rows.append(item)

        result = {
            "available": True,
            "error": "",
            "dimensions": list(dimensions),
            "metrics": list(metrics),
            "rows": rows,
        }

        cache.set(cache_key, result, 600)
        return result

    except Exception:
        logger.exception(
            "Falha ao executar relatório genérico GA4."
        )

        result = {
            "available": False,
            "error": "Google Analytics temporariamente indisponível.",
            "dimensions": list(dimensions),
            "metrics": list(metrics),
            "rows": [],
        }

        cache.set(cache_key, result, 60)
        return result


def get_ga4_360_reports(
    start_date="7daysAgo",
    end_date="today",
    *,
    paths=None,
):
    """
    Conjunto principal de relatórios usados pelo Analytics 360.
    Pode ser utilizado globalmente ou filtrado pelos caminhos
    públicos de uma empresa.
    """

    return {
        "overview": get_ga4_report(
            start_date=start_date,
            end_date=end_date,
            paths=paths,
            metrics=(
                "activeUsers",
                "totalUsers",
                "newUsers",
                "sessions",
                "engagedSessions",
                "engagementRate",
                "bounceRate",
                "averageSessionDuration",
                "screenPageViews",
                "screenPageViewsPerSession",
            ),
        ),

        "engagement": get_ga4_report(
            start_date=start_date,
            end_date=end_date,
            paths=paths,
            metrics=(
                "sessionsPerUser",
                "eventCount",
                "keyEvents",
                "userEngagementDuration",
            ),
        ),

        "timeseries": get_ga4_report(
            start_date=start_date,
            end_date=end_date,
            paths=paths,
            dimensions=("date",),
            metrics=(
                "activeUsers",
                "sessions",
                "screenPageViews",
                "engagedSessions",
                "keyEvents",
            ),
            limit=400,
            order_bys=("+date",),
        ),

        "acquisition": get_ga4_report(
            start_date=start_date,
            end_date=end_date,
            paths=paths,
            dimensions=(
                "sessionDefaultChannelGroup",
                "sessionSource",
                "sessionMedium",
            ),
            metrics=(
                "activeUsers",
                "sessions",
                "engagedSessions",
                "engagementRate",
                "keyEvents",
            ),
            limit=100,
            order_bys=("-sessions",),
        ),

        "pages": get_ga4_report(
            start_date=start_date,
            end_date=end_date,
            paths=paths,
            dimensions=("pagePath", "pageTitle"),
            metrics=(
                "activeUsers",
                "screenPageViews",
                "userEngagementDuration",
                "eventCount",
            ),
            limit=100,
            order_bys=("-screenPageViews",),
        ),

        "devices": get_ga4_report(
            start_date=start_date,
            end_date=end_date,
            paths=paths,
            dimensions=("deviceCategory",),
            metrics=(
                "activeUsers",
                "sessions",
                "screenPageViews",
            ),
            limit=20,
            order_bys=("-sessions",),
        ),

        "geography": get_ga4_report(
            start_date=start_date,
            end_date=end_date,
            paths=paths,
            dimensions=("city", "region", "country"),
            metrics=(
                "activeUsers",
                "sessions",
                "screenPageViews",
            ),
            limit=100,
            order_bys=("-activeUsers",),
        ),

        "events": get_ga4_report(
            start_date=start_date,
            end_date=end_date,
            paths=paths,
            dimensions=("eventName",),
            metrics=(
                "eventCount",
                "activeUsers",
                "keyEvents",
            ),
            limit=100,
            order_bys=("-eventCount",),
        ),
    }
