from django.urls import path

from . import public_views


app_name = 'agenda_public'

urlpatterns = [
    path('agenda/', public_views.agenda_home, name='home'),
    path('agenda/autocomplete/', public_views.autocomplete, name='autocomplete'),
    path('agenda/slots/<uuid:vinculo_uuid>/', public_views.slots, name='slots'),
    path('agenda/confirmar/<uuid:vinculo_uuid>/', public_views.confirmar, name='confirmar'),
    path('agenda/<slug:empresa_slug>/', public_views.agenda_empresa, name='empresa'),
    path('agenda/<slug:empresa_slug>/profissional/<uuid:profissional_uuid>/', public_views.agenda_profissional, name='profissional'),
    path('agenda/<slug:empresa_slug>/<slug:servico_slug>/', public_views.agenda_servico, name='servico'),
    path('meus-agendamentos/', public_views.meus_agendamentos, name='meus_agendamentos'),
    path('minha-agenda-profissional/', public_views.minha_agenda_profissional, name='minha_agenda_profissional'),
    path('meus-agendamentos/<uuid:uuid>/', public_views.meu_agendamento, name='meu_agendamento'),
    path('meus-agendamentos/<uuid:uuid>/cancelar/', public_views.cancelar, name='cancelar'),
]
