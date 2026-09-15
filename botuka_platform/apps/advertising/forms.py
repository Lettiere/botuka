from django import forms

from apps.organizations.permissions import empresas_gerenciaveis_para_usuario

from .models import (Campanha, CampanhaSegmentacao, Criativo,
                     PlanoPublicitario, Posicionamento)


class CampanhaForm(forms.ModelForm):
    class Meta:
        model = Campanha
        fields = ('empresa', 'plano', 'nome', 'inicio', 'fim', 'posicionamentos', 'observacoes')
        widgets = {
            'inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'fim': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.fields['empresa'].queryset = empresas_gerenciaveis_para_usuario(usuario)
        self.fields['plano'].queryset = self.fields['plano'].queryset.filter(ativo=True)
        self.fields['posicionamentos'].queryset = self.fields['posicionamentos'].queryset.filter(ativo=True)

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.criado_por = self.usuario
        obj.full_clean()
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class CriativoForm(forms.ModelForm):
    class Meta:
        model = Criativo
        fields = ('tipo', 'titulo', 'texto', 'imagem', 'video', 'url_destino', 'ativo')

    def __init__(self, *args, campanha=None, **kwargs):
        super().__init__(*args, **kwargs)
        if campanha is not None:
            self.instance.campanha = campanha
            regras = []
            for posicao in campanha.posicionamentos.all():
                dimensao = (
                    f'{posicao.largura} × {posicao.altura} px'
                    if posicao.largura and posicao.altura else 'dimensões livres'
                )
                regras.append(
                    f'{posicao.nome}: formato recomendado {dimensao}; '
                    f'formatos {", ".join(posicao.formatos_permitidos) or "não configurados"}; '
                    f'máximo {posicao.tamanho_maximo_bytes} bytes.'
                )
            ajuda = ' '.join(regras)
            self.fields['imagem'].help_text = ajuda
            self.fields['video'].help_text = ajuda


class SegmentacaoForm(forms.ModelForm):
    class Meta:
        model = CampanhaSegmentacao
        fields = ('categorias', 'subcategorias', 'cnaes', 'termos')


class PlanoPublicitarioForm(forms.ModelForm):
    class Meta:
        model = PlanoPublicitario
        fields = ('nome', 'nivel', 'descricao', 'preco_diario', 'prioridade',
                  'exclusivo', 'limite_anunciantes', 'impressoes_por_usuario_dia',
                  'duracao_segundos', 'ativo')


class PosicionamentoForm(forms.ModelForm):
    formatos_permitidos = forms.CharField(
        help_text='Separe por vírgulas: jpg, png, webp, mp4, webm.', required=False,
    )

    class Meta:
        model = Posicionamento
        fields = ('nome', 'codigo', 'descricao', 'contexto', 'largura', 'altura',
                  'largura_mobile', 'altura_mobile', 'proporcao_recomendada',
                  'tamanho_maximo_bytes', 'formatos_permitidos', 'permite_imagem',
                  'permite_video', 'permite_texto', 'dimensoes_obrigatorias',
                  'aceita_takeover', 'ativo')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial['formatos_permitidos'] = ', '.join(self.instance.formatos_permitidos)

    def clean_formatos_permitidos(self):
        return [item.strip().lower().lstrip('.') for item in
                self.cleaned_data['formatos_permitidos'].split(',') if item.strip()]
