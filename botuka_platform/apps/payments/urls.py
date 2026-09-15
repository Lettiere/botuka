from django.urls import path

from . import views

app_name = 'payments'
urlpatterns = [
    path('webhooks/mercadopago/', views.mercado_pago_webhook, name='mercado_pago_webhook'),
    path('webhooks/c6/', views.c6_webhook, name='c6_webhook'),
    path('webhooks/<slug:gateway_code>/', views.webhook, name='webhook'),
]
