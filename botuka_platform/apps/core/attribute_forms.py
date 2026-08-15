from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from apps.core.models import AtributoAdicional
from apps.recruitment.models import Vaga
from apps.services.models import Servico


CLASSIFICATIONS = {
    'vaga': (
        (AtributoAdicional.Classificacao.OBRIGATORIO, 'Obrigatório'),
        (AtributoAdicional.Classificacao.DESEJAVEL, 'Desejável'),
        (AtributoAdicional.Classificacao.INFORMATIVO, 'Informativo'),
    ),
    'servico': (
        (AtributoAdicional.Classificacao.CARACTERISTICA, 'Característica'),
        (AtributoAdicional.Classificacao.DIFERENCIAL, 'Diferencial'),
        (AtributoAdicional.Classificacao.CONDICAO, 'Condição'),
        (AtributoAdicional.Classificacao.INFORMATIVO, 'Informativo'),
    ),
}


class AtributoAdicionalForm(forms.ModelForm):
    def __init__(self, *args, contexto='vaga', **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['classificacao'].choices = CLASSIFICATIONS[contexto]
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
        self.fields['nome_personalizado'].widget.attrs['data-custom-name'] = ''

    class Meta:
        model = AtributoAdicional
        fields = ('tipo', 'nome_personalizado', 'valor', 'classificacao', 'observacao', 'ordem')
        widgets = {
            'tipo': forms.Select(attrs={'data-attribute-type': ''}),
            'valor': forms.TextInput(attrs={'maxlength': 240}),
            'observacao': forms.TextInput(attrs={'maxlength': 300}),
            'ordem': forms.HiddenInput(),
        }


class BaseAtributoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            key = (
                form.cleaned_data.get('tipo'),
                (form.cleaned_data.get('nome_personalizado') or '').strip().casefold(),
                (form.cleaned_data.get('valor') or '').strip().casefold(),
                form.cleaned_data.get('classificacao'),
            )
            if key in seen:
                raise forms.ValidationError('Remova atributos adicionais idênticos.')
            seen.add(key)


VagaAtributoFormSet = inlineformset_factory(
    Vaga, AtributoAdicional, fk_name='vaga', form=AtributoAdicionalForm,
    formset=BaseAtributoFormSet, extra=0, can_delete=True,
)
ServicoAtributoFormSet = inlineformset_factory(
    Servico, AtributoAdicional, fk_name='servico', form=AtributoAdicionalForm,
    formset=BaseAtributoFormSet, extra=0, can_delete=True,
)


def atributo_formset(contexto, *, instance, data=None):
    factory = VagaAtributoFormSet if contexto == 'vaga' else ServicoAtributoFormSet
    if data is not None and 'atributos-TOTAL_FORMS' not in data:
        data = data.copy()
        data.update({
            'atributos-TOTAL_FORMS': '0',
            'atributos-INITIAL_FORMS': '0',
            'atributos-MIN_NUM_FORMS': '0',
            'atributos-MAX_NUM_FORMS': '1000',
        })
    return factory(
        data=data, instance=instance, prefix='atributos',
        form_kwargs={'contexto': contexto},
    )
