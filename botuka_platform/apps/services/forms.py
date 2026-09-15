from django import forms

from apps.organizations.models import EmpresaSolicitacao


class EmpresaReivindicacaoForm(forms.ModelForm):
    class Meta:
        model = EmpresaSolicitacao
        fields = [
            "funcao_pretendida",
            "relacao_empresa",
            "justificativa",
        ]
        labels = {
            "funcao_pretendida": "Sua função na empresa",
            "relacao_empresa": "Qual é sua relação com a empresa?",
            "justificativa": "Informações adicionais",
        }
        widgets = {
            "funcao_pretendida": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex.: proprietário, sócio, administrador",
            }),
            "relacao_empresa": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Explique sua relação com a empresa",
            }),
            "justificativa": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Informe dados que ajudem na análise da solicitação",
            }),
        }

    def clean(self):
        cleaned = super().clean()

        if not cleaned.get("funcao_pretendida"):
            self.add_error(
                "funcao_pretendida",
                "Informe sua função na empresa.",
            )

        if not cleaned.get("relacao_empresa"):
            self.add_error(
                "relacao_empresa",
                "Informe sua relação com a empresa.",
            )

        return cleaned



class EmpresaLeadForm(forms.Form):
    nome = forms.CharField(
        max_length=160,
        label="Nome",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "autocomplete": "name",
            "placeholder": "Seu nome",
        }),
    )

    telefone = forms.CharField(
        max_length=20,
        label="Telefone",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "autocomplete": "tel",
            "inputmode": "tel",
            "placeholder": "(14) 99999-9999",
        }),
    )

    email = forms.EmailField(
        max_length=254,
        label="E-mail",
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "autocomplete": "email",
            "placeholder": "voce@exemplo.com",
        }),
    )

    assunto = forms.CharField(
        max_length=180,
        label="Assunto",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Sobre o que deseja falar?",
        }),
    )

    mensagem = forms.CharField(
        max_length=2000,
        label="Mensagem",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 5,
            "placeholder": "Escreva sua mensagem para a empresa",
        }),
    )

    # Honeypot antispam. Usuários reais não devem preencher.
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    def clean_telefone(self):
        telefone = self.cleaned_data["telefone"].strip()
        digits = "".join(ch for ch in telefone if ch.isdigit())

        if not 10 <= len(digits) <= 13:
            raise forms.ValidationError(
                "Informe um telefone válido com DDD."
            )

        return telefone

    def clean(self):
        cleaned = super().clean()

        if cleaned.get("website"):
            raise forms.ValidationError(
                "Não foi possível processar o contato."
            )

        return cleaned
