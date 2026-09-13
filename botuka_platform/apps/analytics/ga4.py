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
                        start_date=start_date,
                        end_date=end_date,
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
                        start_date=start_date,
                        end_date=end_date,
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
