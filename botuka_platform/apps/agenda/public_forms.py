from django import forms


class ConfirmacaoAgendamentoForm(forms.Form):
    inicio = forms.CharField(widget=forms.HiddenInput)
