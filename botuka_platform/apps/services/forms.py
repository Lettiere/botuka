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
