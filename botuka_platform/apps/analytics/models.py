import uuid

from django.conf import settings
from django.db import models


class AnalyticsEvent(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event_name = models.CharField(max_length=48, db_index=True)
    visitor_id = models.CharField(max_length=64, db_index=True)
    session_id = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    empresa = models.ForeignKey('organizations.Empresa', null=True, blank=True, on_delete=models.SET_NULL, related_name='analytics_events')
    object_type = models.CharField(max_length=32, blank=True, db_index=True)
    object_id = models.UUIDField(null=True, blank=True, db_index=True)
    source = models.CharField(max_length=64, blank=True, db_index=True)
    medium = models.CharField(max_length=64, blank=True)
    campaign = models.CharField(max_length=120, blank=True)
    term = models.CharField(max_length=120, blank=True)
    content = models.CharField(max_length=120, blank=True)
    first_source = models.CharField(max_length=64, blank=True)
    first_medium = models.CharField(max_length=64, blank=True)
    first_campaign = models.CharField(max_length=120, blank=True)
    gclid = models.CharField(max_length=180, blank=True)
    gbraid = models.CharField(max_length=180, blank=True)
    wbraid = models.CharField(max_length=180, blank=True)
    referrer_host = models.CharField(max_length=180, blank=True)
    landing_path = models.CharField(max_length=300, blank=True)
    path = models.CharField(max_length=300)
    device_type = models.CharField(max_length=16, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['empresa', 'created_at', 'event_name'], name='analytics_co_date_event_idx'),
            models.Index(fields=['object_type', 'object_id', 'created_at'], name='analytics_object_date_idx'),
            models.Index(fields=['source', 'created_at'], name='analytics_source_date_idx'),
        ]


class AnalyticsDailyCompany(models.Model):
    date = models.DateField()
    empresa = models.ForeignKey('organizations.Empresa', on_delete=models.CASCADE, related_name='analytics_daily')
    impressions = models.PositiveBigIntegerField(default=0)
    views = models.PositiveBigIntegerField(default=0)
    visitors = models.PositiveBigIntegerField(default=0)
    search_views = models.PositiveBigIntegerField(default=0)
    service_views = models.PositiveBigIntegerField(default=0)
    product_views = models.PositiveBigIntegerField(default=0)
    whatsapp_clicks = models.PositiveBigIntegerField(default=0)
    phone_clicks = models.PositiveBigIntegerField(default=0)
    website_clicks = models.PositiveBigIntegerField(default=0)
    directions_clicks = models.PositiveBigIntegerField(default=0)
    leads = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['date', 'empresa'], name='analytics_daily_company_uk')]
        indexes = [models.Index(fields=['empresa', 'date'], name='analytics_daily_company_idx')]


class AnalyticsDailyCompanyTerm(models.Model):
    date = models.DateField()
    empresa = models.ForeignKey('organizations.Empresa', on_delete=models.CASCADE, related_name='analytics_terms')
    term = models.CharField(max_length=120)
    impressions = models.PositiveBigIntegerField(default=0)
    selections = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['date', 'empresa', 'term'], name='analytics_daily_term_uk')]
        indexes = [models.Index(fields=['empresa', 'date', 'term'], name='analytics_company_term_idx')]
