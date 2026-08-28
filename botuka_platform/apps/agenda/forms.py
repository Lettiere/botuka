from datetime import datetime, time, timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.services.models import Servico

from .models import (
    AgendaBloqueio,
    AgendaDisponibilidade,
    AgendaDisponibilidadeData,
    AgendaFuncionamentoEmpresa,
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
        fields = (
            'profissional', 'servico', 'duracao_minutos',
            'buffer_antes_minutos', 'buffer_depois_minutos',
        )

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

    def clean(self):
        cleaned = super().clean()
        for campo in ('buffer_antes_minutos', 'buffer_depois_minutos'):
            if cleaned.get(campo, 0) > 1440:
                self.add_error(campo, 'O buffer não pode exceder 24 horas.')
        return cleaned


class FuncionamentoEmpresaForm(forms.ModelForm):
    class Meta:
        model = AgendaFuncionamentoEmpresa
        fields = ('dia_semana', 'hora_inicio', 'hora_fim')
        widgets = {
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fim': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, empresa, **kwargs):
        self.empresa = empresa
        super().__init__(*args, **kwargs)
        self.instance.empresa = empresa


class DisponibilidadeForm(EmpresaScopedModelForm):
    class Meta:
        model = AgendaDisponibilidadeData
        fields = ('profissional', 'data', 'hora_inicio', 'hora_fim')
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fim': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profissional'].queryset = profissionais_ativos(self.empresa)

    def clean(self):
        cleaned = super().clean()
        data = cleaned.get('data')
        inicio = cleaned.get('hora_inicio')
        fim = cleaned.get('hora_fim')

        if not data or not inicio or not fim:
            return cleaned

        configurado = AgendaFuncionamentoEmpresa.objects.filter(
            empresa=self.empresa,
        ).exists()

        if configurado and not AgendaFuncionamentoEmpresa.objects.filter(
            empresa=self.empresa,
            dia_semana=data.weekday(),
            ativo=True,
            hora_inicio__lte=inicio,
            hora_fim__gte=fim,
        ).exists():
            raise ValidationError(
                'A disponibilidade precisa caber integralmente no '
                'funcionamento da empresa nesta data.'
            )

        return cleaned


class BloqueioForm(EmpresaScopedModelForm):
    dia_inteiro = forms.BooleanField(required=False, label='Bloquear o dia inteiro')
    periodo_inteiro = forms.BooleanField(required=False, label='Bloquear período de datas')
    data_inicio = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    data_fim = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

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

    def clean(self):
        cleaned = super().clean()
        data_inicio = cleaned.get('data_inicio')
        data_fim = cleaned.get('data_fim')
        if cleaned.get('dia_inteiro'):
            if not data_inicio:
                self.add_error('data_inicio', 'Informe a data do bloqueio.')
            else:
                cleaned['inicio'] = timezone.make_aware(datetime.combine(data_inicio, time.min))
                cleaned['fim'] = cleaned['inicio'] + timedelta(days=1)
        elif cleaned.get('periodo_inteiro'):
            if not data_inicio or not data_fim:
                raise ValidationError('Informe as datas inicial e final.')
            if data_fim < data_inicio:
                self.add_error('data_fim', 'A data final não pode ser anterior à inicial.')
            else:
                cleaned['inicio'] = timezone.make_aware(datetime.combine(data_inicio, time.min))
                cleaned['fim'] = timezone.make_aware(datetime.combine(data_fim + timedelta(days=1), time.min))
        return cleaned

    def _post_clean(self):
        super()._post_clean()
        if self.cleaned_data.get('inicio'):
            self.instance.inicio = self.cleaned_data['inicio']
        if self.cleaned_data.get('fim'):
            self.instance.fim = self.cleaned_data['fim']
