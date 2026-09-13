from django.shortcuts import render

from apps.analytics.ga4 import get_ga4_overview
from apps.gestao.decorators import master_required


@master_required
def ga4_dashboard(request):
    period = request.GET.get("period", "7")

    periods = {
        "7": ("7daysAgo", "today", "7 dias"),
        "30": ("30daysAgo", "today", "30 dias"),
        "90": ("90daysAgo", "today", "90 dias"),
    }

    if period not in periods:
        period = "7"

    start_date, end_date, period_label = periods[period]

    ga4 = get_ga4_overview(
        start_date=start_date,
        end_date=end_date,
    )

    return render(
        request,
        "gestao/analytics/ga4_dashboard.html",
        {
            "ga4": ga4,
            "period": period,
            "period_label": period_label,
            "section": "Inteligência",
        },
    )
