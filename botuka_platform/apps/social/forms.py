from django import forms
from apps.core.services.images import optimize_uploaded_image

from .models import SocialPost, SocialProfile, SocialStory


class SocialProfileForm(forms.Form):
    nome_exibicao = forms.CharField(max_length=120)
    biografia = forms.CharField(max_length=1000, required=False, widget=forms.Textarea)
    avatar = forms.ImageField(required=False)
    quem_pode_solicitar_mensagem = forms.ChoiceField(
        label='Quem pode solicitar conversa', choices=SocialProfile.InteracaoPrivada.choices,
    )
    quem_pode_responder_story = forms.ChoiceField(
        label='Quem pode responder Stories', choices=SocialProfile.InteracaoPrivada.choices,
    )
    permitir_reacoes = forms.BooleanField(label='Permitir reações em Stories', required=False)
    confirmacao_leitura = forms.BooleanField(label='Exibir confirmações de leitura', required=False)

    def clean_avatar(self):
        return optimize_uploaded_image(self.cleaned_data.get('avatar'), policy='avatar')


class SocialPostForm(forms.ModelForm):
    class Meta:
        model = SocialPost
        fields = ['imagem', 'legenda', 'visibilidade']
        widgets = {'legenda': forms.Textarea(attrs={'rows': 3})}

    def clean_imagem(self):
        return optimize_uploaded_image(self.cleaned_data.get('imagem'), policy='card')


class SocialStoryForm(forms.ModelForm):
    class Meta:
        model = SocialStory
        fields = ['imagem', 'visibilidade']

    def clean_imagem(self):
        return optimize_uploaded_image(self.cleaned_data.get('imagem'), policy='story')
