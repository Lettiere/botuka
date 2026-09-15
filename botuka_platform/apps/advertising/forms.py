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
        fields = (
            'posicionamento', 'tipo', 'titulo', 'texto', 'imagem', 'imagem_mobile',
            'video', 'video_mobile', 'url_destino', 'ativo',
        )

    def __init__(self, *args, campanha=None, **kwargs):
        uploads = kwargs.get('files')
        if uploads is None and len(args) > 1:
            uploads = args[1]
        self._upload_content_types = {
            name: getattr(upload, 'content_type', '')
            for name, upload in (uploads or {}).items()
        }
        super().__init__(*args, **kwargs)
        self.fields['imagem'].label = 'Imagem desktop'
        self.fields['video'].label = 'Vídeo desktop'
        self.fields['imagem_mobile'].label = 'Imagem mobile (opcional)'
        self.fields['video_mobile'].label = 'Vídeo mobile (opcional)'
        if campanha is not None:
            self.instance.campanha = campanha
            posicoes = campanha.posicionamentos.filter(ativo=True).order_by('nome', 'codigo')
            self.fields['posicionamento'].queryset = posicoes
            self.fields['posicionamento'].label_from_instance = (
                lambda posicao: f'{posicao.nome.upper()} — {posicao.codigo}'
            )
            posicionamento_id = self.data.get('posicionamento') or self.initial.get('posicionamento')
            if not posicionamento_id and self.instance.pk:
                posicionamento_id = self.instance.posicionamento_id
            try:
                selecionado = posicoes.get(pk=posicionamento_id)
            except (Posicionamento.DoesNotExist, TypeError, ValueError):
                selecionado = None
            if selecionado:
                self._configurar_ajuda_midia(selecionado)

    def _configurar_ajuda_midia(self, posicao):
        formatos = ', '.join(posicao.formatos_permitidos) or 'não configurados'
        limite = f'{posicao.tamanho_maximo_bytes / (1024 * 1024):g} MB'
        desktop = self._dimensoes(posicao.largura, posicao.altura)
        mobile = self._dimensoes(posicao.largura_mobile, posicao.altura_mobile)
        comuns = f'Formatos permitidos: {formatos}. Tamanho máximo: {limite} por arquivo.'
        for campo in ('imagem', 'video'):
            self.fields[campo].help_text = f'Desktop — {desktop}. {comuns}'
        for campo in ('imagem_mobile', 'video_mobile'):
            self.fields[campo].help_text = (
                f'Mobile — {mobile}. Opcional; sem arquivo, usa a mídia desktop. {comuns}'
            )

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo')
        prefix = 'image/' if tipo == Criativo.Tipo.IMAGEM else (
            'video/' if tipo == Criativo.Tipo.VIDEO else None
        )
        if prefix:
            for field_name in ('imagem', 'imagem_mobile', 'video', 'video_mobile'):
                upload = self.files.get(field_name)
                content_type = self._upload_content_types.get(field_name, '')
                if upload and content_type and not content_type.startswith(prefix):
                    self.add_error(
                        field_name,
                        'MIME do arquivo incompatível com o tipo de criativo.',
                    )
        return cleaned

    @staticmethod
    def _dimensoes(largura, altura):
        return f'{largura} × {altura} px recomendado' if largura and altura else 'dimensões livres'


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
