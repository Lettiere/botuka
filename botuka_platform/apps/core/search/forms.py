from django import forms


class GlobalSearchForm(forms.Form):
    q = forms.CharField(
        label='Buscar no BOTUKA', max_length=120, required=False,
        widget=forms.SearchInput(attrs={
            'placeholder': 'Empresas, serviços, vagas, notícias...',
            'autocomplete': 'off',
        }),
    )
