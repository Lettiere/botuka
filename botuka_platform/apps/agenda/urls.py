from django.urls import path

from . import views


urlpatterns = [
    path('', views.dashboard, name='empresa_agenda'),
    path('estado/', views.agenda_estado, name='agenda_estado'),
    path('configuracoes/', views.agenda_configuracoes, name='agenda_configuracoes'),
    path('calendario/', views.calendario_operacional, name='agenda_calendario'),
    path('funcionamento/', views.funcionamento_lista, name='agenda_funcionamento_lista'),
    path('funcionamento/novo/', views.funcionamento_form, name='agenda_funcionamento_criar'),
    path('funcionamento/<int:pk>/editar/', views.funcionamento_form, name='agenda_funcionamento_editar'),
    path('funcionamento/<int:pk>/status/', views.funcionamento_status, name='agenda_funcionamento_status'),
    path('servicos/', views.vinculo_lista, name='agenda_vinculo_lista'),
    path('servicos/novo/', views.vinculo_form, name='agenda_vinculo_criar'),
    path('servicos/<int:pk>/editar/', views.vinculo_form, name='agenda_vinculo_editar'),
    path('servicos/<int:pk>/status/', views.vinculo_status, name='agenda_vinculo_status'),
    path('horarios/', views.horarios_lista, name='agenda_horarios'),
    path('horarios/semanais/novo/', views.disponibilidade_semanal_form, name='agenda_horario_semanal_criar'),
    path('horarios/semanais/<int:pk>/editar/', views.disponibilidade_semanal_form, name='agenda_horario_semanal_editar'),
    path('horarios/semanais/<int:pk>/status/', views.disponibilidade_semanal_status, name='agenda_horario_semanal_status'),
    path('disponibilidades/', views.disponibilidade_lista, name='agenda_disponibilidade_lista'),
    path('disponibilidades/nova/', views.disponibilidade_form, name='agenda_disponibilidade_criar'),
    path('disponibilidades/<int:pk>/editar/', views.disponibilidade_form, name='agenda_disponibilidade_editar'),
    path('disponibilidades/<int:pk>/status/', views.disponibilidade_status, name='agenda_disponibilidade_status'),
    path('bloqueios/', views.bloqueio_lista, name='agenda_bloqueio_lista'),
    path('bloqueios/novo/', views.bloqueio_form, name='agenda_bloqueio_criar'),
    path('bloqueios/<int:pk>/editar/', views.bloqueio_form, name='agenda_bloqueio_editar'),
    path('bloqueios/<int:pk>/status/', views.bloqueio_status, name='agenda_bloqueio_status'),
    path('agendamentos/', views.agendamento_lista, name='agenda_agendamento_lista'),
    path('agendamentos/novo/', views.agendamento_criar, name='agenda_agendamento_criar'),
    path('agendamentos/<int:pk>/', views.agendamento_detalhe, name='agenda_agendamento_detalhe'),
    path('agendamentos/<int:pk>/reagendar/', views.agendamento_reagendar, name='agenda_agendamento_reagendar'),
    path('agendamentos/<int:pk>/status/', views.agendamento_status, name='agenda_agendamento_status'),
]
