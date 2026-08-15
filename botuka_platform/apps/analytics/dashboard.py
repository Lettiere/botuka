from datetime import date, timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from .models import AnalyticsDailyCompany, AnalyticsDailyCompanyTerm, AnalyticsEvent


METRICS = (
    'impressions', 'views', 'visitors', 'search_views', 'service_views',
    'product_views', 'whatsapp_clicks', 'phone_clicks', 'website_clicks',
    'directions_clicks', 'leads',
)


def resolve_period(params):
    today = timezone.localdate()
    choice = params.get('period', '30')
    if choice == 'today':
        start = end = today
    elif choice == 'month':
        start, end = today.replace(day=1), today
    elif choice == 'previous_month':
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
    elif choice == 'custom':
        try:
            start = date.fromisoformat(params.get('start', ''))
            end = date.fromisoformat(params.get('end', ''))
            if start > end or (end - start).days > 366 or end > today:
                raise ValueError
        except (TypeError, ValueError):
            choice, start, end = '30', today - timedelta(days=29), today
    else:
        days = int(choice) if choice in {'7', '30', '90'} else 30
        choice, start, end = str(days), today - timedelta(days=days - 1), today
    length = (end - start).days + 1
    return choice, start, end, start - timedelta(days=length), start - timedelta(days=1)


def _totals(queryset):
    values = queryset.aggregate(**{field: Sum(field) for field in METRICS})
    return {field: values[field] or 0 for field in METRICS}


def _change(current, previous):
    if not previous:
        return None if current else 0
    return round(((current - previous) / previous) * 100, 1)


def dashboard_data(empresa, start, end, previous_start, previous_end):
    daily = AnalyticsDailyCompany.objects.filter(empresa=empresa, date__range=(start, end))
    current = _totals(daily)
    previous = _totals(AnalyticsDailyCompany.objects.filter(
        empresa=empresa, date__range=(previous_start, previous_end),
    ))
    days = {row.date: row for row in daily}
    series = []
    cursor = start
    while cursor <= end:
        row = days.get(cursor)
        series.append({
            'date': cursor,
            'views': row.views if row else 0,
            'contacts': (
                row.whatsapp_clicks + row.phone_clicks + row.website_clicks
                + row.directions_clicks
            ) if row else 0,
        })
        cursor += timedelta(days=1)
    max_views = max((row['views'] for row in series), default=0) or 1
    for row in series:
        row['height'] = max(2, round(row['views'] / max_views * 100)) if row['views'] else 0

    events = AnalyticsEvent.objects.filter(empresa=empresa, created_at__date__range=(start, end))
    sources = list(events.values('source', 'medium').annotate(total=Count('id')).order_by('-total')[:8])
    terms = list(AnalyticsDailyCompanyTerm.objects.filter(
        empresa=empresa, date__range=(start, end),
    ).values('term').annotate(
        impressions=Sum('impressions'), selections=Sum('selections'),
    ).order_by('-selections', '-impressions')[:10])
    top_content = list(events.filter(
        event_name__in=('view_service', 'view_item', 'view_job', 'view_event'),
    ).values('object_type', 'object_id').annotate(total=Count('id')).order_by('-total')[:10])

    contact_total = sum(current[key] for key in (
        'whatsapp_clicks', 'phone_clicks', 'website_clicks', 'directions_clicks',
    ))
    previous_contact = sum(previous[key] for key in (
        'whatsapp_clicks', 'phone_clicks', 'website_clicks', 'directions_clicks',
    ))
    cards = [
        ('Visualizações', current['views'], _change(current['views'], previous['views'])),
        ('Visitantes', current['visitors'], _change(current['visitors'], previous['visitors'])),
        ('Contatos', contact_total, _change(contact_total, previous_contact)),
        ('Leads', current['leads'], _change(current['leads'], previous['leads'])),
    ]
    insights = []
    view_change = _change(current['views'], previous['views'])
    if view_change is not None and abs(view_change) >= 15:
        direction = 'cresceram' if view_change > 0 else 'caíram'
        insights.append(f'As visualizações {direction} {abs(view_change):g}% em relação ao período anterior.')
    if terms:
        insights.append(f'“{terms[0]["term"]}” foi o termo de busca com maior destaque no período.')
    if current['views'] >= 30:
        rate = round(contact_total / current['views'] * 100, 1)
        if rate < 2:
            insights.append('A taxa de contato está abaixo de 2%; revise chamadas para ação e dados de contato.')
        elif rate >= 8:
            insights.append(f'A taxa de contato foi de {rate:g}%, um sinal de boa intenção dos visitantes.')
    if not insights:
        insights.append('Ainda não há volume suficiente para uma tendência confiável neste período.')
    return {
        'cards': cards, 'totals': current, 'series': series, 'sources': sources,
        'terms': terms, 'top_content': top_content, 'insights': insights,
    }
