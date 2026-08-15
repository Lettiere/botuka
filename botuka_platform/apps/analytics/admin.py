from django.contrib import admin

from .models import AnalyticsDailyCompany, AnalyticsDailyCompanyTerm, AnalyticsEvent

admin.site.register((AnalyticsEvent, AnalyticsDailyCompany, AnalyticsDailyCompanyTerm))
