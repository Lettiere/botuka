from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import AnalyticsDailyCompany, AnalyticsDailyCompanyTerm, AnalyticsEvent


METRICS = (
    'impressions', 'views', 'visitors', 'search_views', 'service_views',
    'product_views', 'whatsapp_clicks', 'phone_clicks', 'email_clicks',
    'website_clicks', 'directions_clicks', 'leads',
)

DEMOGRAPHIC_MIN_USERS = 5


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



def company_audience_data(empresa, start, end):
    """
    Consolida usuários que tiveram relacionamento real com a empresa
    no período, sem expor dados pessoais sensíveis.
    """
    from django.contrib.auth import get_user_model

    from apps.agenda.models import Agendamento
    from apps.services.models import ServicoAvaliacao, ServicoFavorito
    from apps.social.models import EmpresaSeguidor

    User = get_user_model()

    identified_ids = set(
        AnalyticsEvent.objects.filter(
            empresa=empresa,
            user__isnull=False,
            created_at__date__range=(start, end),
        ).values_list('user_id', flat=True).distinct()
    )

    follower_ids = set(
        EmpresaSeguidor.objects.filter(
            empresa=empresa,
            criado_em__date__range=(start, end),
        ).values_list('usuario_id', flat=True).distinct()
    )

    favorite_ids = set(
        ServicoFavorito.objects.filter(
            servico__empresa=empresa,
            criado_em__date__range=(start, end),
        ).values_list('usuario_id', flat=True).distinct()
    )

    reviewer_ids = set(
        ServicoAvaliacao.objects.filter(
            servico__empresa=empresa,
            criado_em__date__range=(start, end),
            excluido_em__isnull=True,
        ).values_list('usuario_avaliador_id', flat=True).distinct()
    )

    appointment_ids = set(
        Agendamento.objects.filter(
            profissional_servico__servico__empresa=empresa,
            criado_em__date__range=(start, end),
        ).values_list('cliente_id', flat=True).distinct()
    )

    all_ids = (
        identified_ids
        | follower_ids
        | favorite_ids
        | reviewer_ids
        | appointment_ids
    )

    users = list(
        User.objects.filter(
            pk__in=all_ids,
            is_active=True,
        ).select_related('cidade', 'estado')
    )

    demographics_available = len(users) >= DEMOGRAPHIC_MIN_USERS

    age_bands = {
        'Até 17': 0,
        '18–24': 0,
        '25–34': 0,
        '35–44': 0,
        '45–54': 0,
        '55–64': 0,
        '65+': 0,
        'Não informado': 0,
    }

    today = timezone.localdate()
    locations = {}

    for user in users if demographics_available else []:
        if user.data_nascimento:
            age = (
                today.year
                - user.data_nascimento.year
                - (
                    (today.month, today.day)
                    < (user.data_nascimento.month, user.data_nascimento.day)
                )
            )

            if age < 18:
                band = 'Até 17'
            elif age <= 24:
                band = '18–24'
            elif age <= 34:
                band = '25–34'
            elif age <= 44:
                band = '35–44'
            elif age <= 54:
                band = '45–54'
            elif age <= 64:
                band = '55–64'
            else:
                band = '65+'
        else:
            band = 'Não informado'

        age_bands[band] += 1

        if (
            user.visibilidade_localizacao != user.VisibilidadeLocalizacao.PRIVADA
            and user.cidade_id
            and user.estado_id
        ):
            location = f'{user.cidade} / {user.estado}'
            locations[location] = locations.get(location, 0) + 1

    age_bands = [
        {'label': label, 'total': total}
        for label, total in age_bands.items()
        if total
    ]

    locations = [
        {'label': label, 'total': total}
        for label, total in sorted(
            locations.items(),
            key=lambda item: (-item[1], item[0]),
        )[:10]
    ]

    return {
        'unique_users': len(all_ids),
        'identified_users': len(identified_ids),
        'followers': len(follower_ids),
        'favorites': len(favorite_ids),
        'reviewers': len(reviewer_ids),
        'appointment_clients': len(appointment_ids),
        'demographics_available': demographics_available,
        'demographic_min_users': DEMOGRAPHIC_MIN_USERS,
        'age_bands': age_bands if demographics_available else [],
        'locations': locations if demographics_available else [],
    }

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
                row.whatsapp_clicks + row.phone_clicks + row.email_clicks
                + row.website_clicks + row.directions_clicks
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

    content_counts = events.aggregate(
        company_views=Count(
            'id',
            filter=Q(event_name='view_company', object_type='company'),
        ),
        service_views=Count(
            'id',
            filter=Q(event_name='view_service'),
        ),
        product_views=Count(
            'id',
            filter=Q(event_name='view_item'),
        ),
        article_views=Count(
            'id',
            filter=Q(event_name='view_content', object_type='article'),
        ),
        tourism_views=Count(
            'id',
            filter=Q(
                event_name='view_content',
                object_type__in=('tourism_place', 'tourism_guide', 'tourism_company'),
            ),
        ),
        sports_views=Count(
            'id',
            filter=Q(
                event_name='view_content',
                object_type__in=('sports_team', 'sports_athlete', 'sports_org'),
            ),
        ),
        event_views=Count(
            'id',
            filter=Q(event_name='view_event'),
        ),
        job_views=Count(
            'id',
            filter=Q(event_name='view_job'),
        ),
        appointments=Count(
            'id',
            filter=Q(event_name='generate_lead', object_type='appointment'),
        ),
        ad_impressions=Count(
            'id',
            filter=Q(event_name='ad_impression', object_type='ad_campaign'),
        ),
        ad_clicks=Count(
            'id',
            filter=Q(event_name='ad_click', object_type='ad_campaign'),
        ),
    )

    content_metrics = [
        ('Perfil da empresa', content_counts['company_views']),
        ('Serviços', content_counts['service_views']),
        ('Produtos', content_counts['product_views']),
        ('Notícias', content_counts['article_views']),
        ('Turismo', content_counts['tourism_views']),
        ('Esportes', content_counts['sports_views']),
        ('Eventos', content_counts['event_views']),
        ('Vagas', content_counts['job_views']),
        ('Agendamentos gerados', content_counts['appointments']),
    ]

    advertising_metrics = {
        'impressions': content_counts['ad_impressions'],
        'clicks': content_counts['ad_clicks'],
    }

    contact_total = sum(current[key] for key in (
        'whatsapp_clicks', 'phone_clicks', 'email_clicks',
        'website_clicks', 'directions_clicks',
    ))
    previous_contact = sum(previous[key] for key in (
        'whatsapp_clicks', 'phone_clicks', 'email_clicks',
        'website_clicks', 'directions_clicks',
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
        'content_metrics': content_metrics,
        'advertising_metrics': advertising_metrics,
        'audience': company_audience_data(empresa, start, end),
    }
