from django.urls import path

from .views import collect, company_dashboard

app_name = 'analytics'
urlpatterns = [
    path('api/analytics/events/', collect, name='collect'),
    path('painel/empresas/<uuid:uuid>/analytics/', company_dashboard, name='company_dashboard'),
]
