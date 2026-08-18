from django import forms

from .models import SocialPost, SocialStory


class SocialProfileForm(forms.Form):
    nome_exibicao = forms.CharField(max_length=120)
    biografia = forms.CharField(max_length=1000, required=False, widget=forms.Textarea)
    avatar = forms.ImageField(required=False)


class SocialPostForm(forms.ModelForm):
    class Meta:
        model = SocialPost
        fields = ['imagem', 'legenda', 'visibilidade']
        widgets = {'legenda': forms.Textarea(attrs={'rows': 3})}


class SocialStoryForm(forms.ModelForm):
    class Meta:
        model = SocialStory
        fields = ['imagem', 'visibilidade']
