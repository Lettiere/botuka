from django import forms
from django.core.exceptions import ValidationError

from apps.services.models import Servico

from .models import (
    AgendaBloqueio,
    AgendaDisponibilidade,
    AgendaProfissional,
    AgendaProfissionalServico,
)


def profissionais_ativos(empresa):
    return AgendaProfissional.objects.filter(
        empresa_usuario__empresa=empresa,
        empresa_usuario__ativo=True,
        ativo=True,
    ).select_related('empresa_usuario__usuario')


def servicos_operacionais(empresa):
    return Servico.objects.filter(
        empresa=empresa,
        prestador_tipo=Servico.PrestadorTipo.EMPRESA,
        status=Servico.Status.PUBLICADO,
        ativo=True,
    )


class EmpresaScopedModelForm(forms.ModelForm):
    def __init__(self, *args, empresa, **kwargs):
        self.empresa = empresa
        super().__init__(*args, **kwargs)

    def clean_profissional(self):
        profissional = self.cleaned_data['profissional']
        if not profissionais_ativos(self.empresa).filter(pk=profissional.pk).exists():
            raise ValidationError('Selecione um profissional ativo desta empresa.')
        return profissional


class ProfissionalServicoForm(EmpresaScopedModelForm):
    class Meta:
        model = AgendaProfissionalServico
        fields = ('profissional', 'servico', 'duracao_minutos')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profissional'].queryset = profissionais_ativos(self.empresa)
        self.fields['servico'].queryset = servicos_operacionais(self.empresa)

    def clean_servico(self):
        servico = self.cleaned_data['servico']
        if not servicos_operacionais(self.empresa).filter(pk=servico.pk).exists():
            raise ValidationError('Selecione um serviço publicado e ativo desta empresa.')
        return servico

    def clean_duracao_minutos(self):
        duracao = self.cleaned_data['duracao_minutos']
        if duracao <= 0:
            raise ValidationError('A duração deve ser maior que zero.')
        return duracao


class DisponibilidadeForm(EmpresaScopedModelForm):
    class Meta:
        model = AgendaDisponibilidade
        fields = ('profissional', 'dia_semana', 'hora_inicio', 'hora_fim')
        widgets = {
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fim': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profissional'].queryset = profissionais_ativos(self.empresa)


class BloqueioForm(EmpresaScopedModelForm):
    class Meta:
        model = AgendaBloqueio
        fields = ('profissional', 'tipo', 'inicio', 'fim', 'motivo')
        widgets = {
            'inicio': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}
            ),
            'fim': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profissional'].queryset = profissionais_ativos(self.empresa)
        self.fields['inicio'].input_formats = ('%Y-%m-%dT%H:%M',)
        self.fields['fim'].input_formats = ('%Y-%m-%dT%H:%M',)
