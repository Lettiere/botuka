import re

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.db.models import Q
from PIL import Image

from apps.organizations.permissions import empresas_disponiveis_para_usuario
from apps.accounts.permissions import usuario_tem_permissao

from .models import (
    CategoriaTurismo, ContatoTurismo, EmpresaTuristica, EstruturaTurismo,
    ExperienciaTuristica, GuiaTuristico, LocalTuristico, RedeSocialTurismo,
    RoteiroTuristico, ServicoTurismo, TurismoFoto, TurismoPlaylist,
    TurismoPlaylistVideo, TurismoStatus, TurismoVideo,
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


SIM_NAO = (('true', 'Sim'), ('false', 'Não'))


class SimNaoField(forms.TypedChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('choices', SIM_NAO)
        kwargs.setdefault('coerce', lambda value: value in (True, 'true', 'True', '1'))
        kwargs.setdefault('widget', forms.RadioSelect)
        super().__init__(*args, **kwargs)


class LocalTuristicoForm(StyledModelForm):
    class Meta:
        model = LocalTuristico
        exclude = (
            'usuario_criador', 'usuario_atualizador', 'publicado_por',
            'publicado_em', 'moderado_por', 'moderado_em', 'status',
            'ativo', 'removido_em', 'categoria_legada', 'etapa_atual',
            'imagem_principal_webp', 'imagem_thumbnail',
            'estrutura_disponivel', 'estacionamento', 'banheiros',
            'alimentacao', 'acessibilidade', 'redes_sociais',
        )
        widgets = {
            'descricao_completa': forms.Textarea(attrs={'rows': 6}),
            'historia': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['empresa_responsavel'].queryset = empresas_disponiveis_para_usuario(usuario).filter(ativo=True)
        if not usuario_tem_permissao(usuario, 'TURISMO_LOCAL_DESTACAR_HOME'):
            self.fields.pop('destaque_home', None)
        elif 'destaque_home' in self.fields:
            self.fields['destaque_home'].label = 'Destacar este local na HOME?'
            self.fields['destaque_home'].widget = forms.RadioSelect(choices=SIM_NAO)


class GuiaTuristicoForm(StyledModelForm):
    class Meta:
        model = GuiaTuristico
        exclude = (
            'usuario', 'usuario_criador', 'usuario_atualizador',
            'publicado_por', 'publicado_em', 'moderado_por', 'moderado_em',
            'status', 'ativo', 'removido_em', 'verificado',
        )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.fields['empresa'].queryset = empresas_disponiveis_para_usuario(usuario).filter(ativo=True)

    def clean_empresa(self):
        empresa = self.cleaned_data.get('empresa')
        if empresa and empresa not in self.fields['empresa'].queryset:
            raise forms.ValidationError('Empresa indisponível para este usuário.')
        return empresa


class TurismoVideoForm(StyledModelForm):
    class Meta:
        model = TurismoVideo
        fields = (
            'local', 'guia', 'empresa', 'roteiro', 'experiencia',
            'titulo', 'descricao', 'url_youtube', 'ordem',
        )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario_tem_permissao(usuario, 'TURISMO_VIDEO_MODERAR'):
            return
        self.fields['local'].queryset = self.fields['local'].queryset.filter(usuario_criador=usuario)
        self.fields['guia'].queryset = self.fields['guia'].queryset.filter(usuario_criador=usuario)
        self.fields['empresa'].queryset = self.fields['empresa'].queryset.filter(usuario_criador=usuario)
        self.fields['roteiro'].queryset = self.fields['roteiro'].queryset.filter(usuario_criador=usuario)
        self.fields['experiencia'].queryset = self.fields['experiencia'].queryset.filter(usuario_criador=usuario)


class TurismoPlaylistForm(StyledModelForm):
    class Meta:
        model = TurismoPlaylist
        fields = (
            'titulo', 'slug', 'descricao', 'capa', 'url_youtube',
            'cidade', 'categoria', 'local', 'guia', 'roteiro', 'experiencia',
            'empresa',
        )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario_tem_permissao(usuario, 'TURISMO_PLAYLIST_MODERAR'):
            return
        self.fields['local'].queryset = self.fields['local'].queryset.filter(usuario_criador=usuario)
        self.fields['guia'].queryset = self.fields['guia'].queryset.filter(usuario_criador=usuario)
        self.fields['roteiro'].queryset = self.fields['roteiro'].queryset.filter(usuario_criador=usuario)
        self.fields['experiencia'].queryset = self.fields['experiencia'].queryset.filter(usuario_criador=usuario)
        self.fields['empresa'].queryset = self.fields['empresa'].queryset.filter(usuario_criador=usuario)


class RoteiroTuristicoForm(StyledModelForm):
    class Meta:
        model = RoteiroTuristico
        fields = (
            'titulo', 'slug', 'resumo', 'descricao', 'duracao', 'dificuldade',
            'custo_estimado', 'publico_indicado', 'mapa_url', 'locais', 'guias',
        )
        widgets = {'descricao': forms.Textarea(attrs={'rows': 6})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not usuario_tem_permissao(usuario, 'TURISMO_ROTEIRO_PUBLICAR'):
            self.fields['locais'].queryset = self.fields['locais'].queryset.filter(usuario_criador=usuario)
            self.fields['guias'].queryset = self.fields['guias'].queryset.filter(usuario_criador=usuario)


class ExperienciaTuristicaForm(StyledModelForm):
    class Meta:
        model = ExperienciaTuristica
        fields = (
            'titulo', 'slug', 'resumo', 'descricao', 'empresa', 'guia', 'local',
            'duracao', 'valor', 'capacidade', 'datas', 'acessibilidade',
            'requisitos', 'contato',
        )
        widgets = {'descricao': forms.Textarea(attrs={'rows': 6})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not usuario_tem_permissao(usuario, 'TURISMO_EXPERIENCIA_PUBLICAR'):
            for name in ('empresa', 'guia', 'local'):
                self.fields[name].queryset = self.fields[name].queryset.filter(usuario_criador=usuario)


class EmpresaTuristicaForm(StyledModelForm):
    class Meta:
        model = EmpresaTuristica
        fields = ('empresa', 'tipo_atuacao', 'apresentacao', 'regioes_atendidas', 'contato_publico')
        widgets = {'apresentacao': forms.Textarea(attrs={'rows': 5})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = empresas_disponiveis_para_usuario(usuario).filter(ativo=True)
        if self.instance.pk:
            queryset = queryset | queryset.model.objects.filter(pk=self.instance.empresa_id)
        self.fields['empresa'].queryset = queryset.distinct()


class TurismoPlaylistVideoForm(StyledModelForm):
    class Meta:
        model = TurismoPlaylistVideo
        fields = ('video', 'ordem')

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not usuario_tem_permissao(usuario, 'TURISMO_PLAYLIST_MODERAR'):
            self.fields['video'].queryset = self.fields['video'].queryset.filter(usuario_criador=usuario)


class TurismoFotoForm(StyledModelForm):
    class Meta:
        model = TurismoFoto
        fields = ('imagem', 'texto_alternativo', 'legenda', 'credito', 'ordem', 'principal')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['texto_alternativo'].required = True

    def clean_imagem(self):
        return validar_imagem_turismo(self.cleaned_data['imagem'])


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleImageInput

    def clean(self, data, initial=None):
        values = data if isinstance(data, (list, tuple)) else [data]
        return [validar_imagem_turismo(super(MultipleImageField, self).clean(value, initial)) for value in values]


class GaleriaUploadForm(forms.Form):
    imagens = MultipleImageField(
        label='Imagens', help_text='Selecione uma ou mais imagens JPEG, PNG ou WebP.',
    )
    texto_alternativo = forms.CharField(
        max_length=160, label='Descrição acessível',
        help_text='Quando houver várias imagens, o nome do arquivo será acrescentado.',
    )
    credito = forms.CharField(max_length=180, required=False, label='Crédito')


def validar_imagem_turismo(arquivo):
    if arquivo.size > 8 * 1024 * 1024:
        raise ValidationError('A imagem deve possuir no máximo 8 MB.')
    try:
        imagem = Image.open(arquivo)
        imagem.verify()
        arquivo.seek(0)
        imagem = Image.open(arquivo)
        if imagem.format not in {'JPEG', 'PNG', 'WEBP'}:
            raise ValidationError('Use uma imagem JPEG, PNG ou WebP.')
        if imagem.width < 800 or imagem.height < 450:
            raise ValidationError('A imagem deve possuir no mínimo 800 × 450 pixels.')
        arquivo.seek(0)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError('O arquivo enviado não é uma imagem válida.') from exc
    return arquivo


class LocalIdentificacaoForm(StyledModelForm):
    class Meta:
        model = LocalTuristico
        fields = ('nome', 'slug', 'descricao_curta', 'descricao_completa', 'historia', 'situacao_local')
        widgets = {
            'descricao_completa': forms.Textarea(attrs={'rows': 6}),
            'historia': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['slug'].help_text = 'Opcional. Se ficar vazio, será criado a partir do nome.'

    def clean_slug(self):
        slug = self.cleaned_data.get('slug') or slugify(self.cleaned_data.get('nome', ''))
        queryset = LocalTuristico.all_objects.filter(slug=slug)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError('Já existe um local com este endereço amigável.')
        return slug


class LocalCategoriaForm(StyledModelForm):
    class Meta:
        model = LocalTuristico
        fields = ('categoria',)
        labels = {'categoria': 'Tipo de local'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].queryset = CategoriaTurismo.objects.filter(ativo=True).select_related('pai')
        self.fields['categoria'].required = True


class LocalLocalizacaoForm(StyledModelForm):
    class Meta:
        model = LocalTuristico
        fields = (
            'cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade',
            'estado', 'ponto_referencia', 'latitude', 'longitude', 'precisao',
            'visibilidade_localizacao',
        )
        widgets = {
            'latitude': forms.NumberInput(attrs={'step': '0.000001', 'min': '-90', 'max': '90'}),
            'longitude': forms.NumberInput(attrs={'step': '0.000001', 'min': '-180', 'max': '180'}),
            'visibilidade_localizacao': forms.Select,
        }
        help_texts = {
            'visibilidade_localizacao': (
                'Pública: endereço e mapa visíveis. Aproximada: apenas bairro e cidade. '
                'Privada: disponível somente para administração.'
            ),
        }


class LocalInformacoesForm(StyledModelForm):
    gratuito = SimNaoField(label='O acesso é gratuito?')
    agendamento_necessario = SimNaoField(label='É necessário agendamento?')

    class Meta:
        model = LocalTuristico
        fields = (
            'horario', 'dias_funcionamento', 'gratuito', 'valor_inteiro',
            'valor_meia', 'valor_infantil', 'valor_informativo', 'link_compra',
            'agendamento_necessario', 'agendamento_telefone',
            'agendamento_whatsapp', 'agendamento_site', 'agendamento_link',
            'agendamento_instrucoes', 'agendamento_antecedencia_horas',
            'estruturas', 'servicos_disponiveis', 'recomendacoes',
            'regras_local', 'melhor_periodo', 'seguranca',
            'duracao_media_visita',
        )
        widgets = {
            'estruturas': forms.CheckboxSelectMultiple,
            'servicos_disponiveis': forms.CheckboxSelectMultiple,
            'recomendacoes': forms.Textarea(attrs={'rows': 3}),
            'regras_local': forms.Textarea(attrs={'rows': 3}),
            'melhor_periodo': forms.Textarea(attrs={'rows': 2}),
            'seguranca': forms.Textarea(attrs={'rows': 3}),
            'agendamento_instrucoes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estruturas'].queryset = EstruturaTurismo.objects.filter(ativo=True)
        self.fields['servicos_disponiveis'].queryset = ServicoTurismo.objects.filter(ativo=True)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('gratuito'):
            for field in ('valor_inteiro', 'valor_meia', 'valor_infantil'):
                cleaned[field] = None
            cleaned['valor_informativo'] = ''
            cleaned['link_compra'] = ''
        elif cleaned.get('valor_inteiro') is None:
            self.add_error('valor_inteiro', 'Informe o valor inteiro quando o acesso não for gratuito.')
        if not cleaned.get('agendamento_necessario'):
            for field in (
                'agendamento_telefone', 'agendamento_whatsapp', 'agendamento_site',
                'agendamento_link', 'agendamento_instrucoes',
            ):
                cleaned[field] = ''
            cleaned['agendamento_antecedencia_horas'] = None
        elif not any(cleaned.get(field) for field in (
            'agendamento_telefone', 'agendamento_whatsapp',
            'agendamento_site', 'agendamento_link',
        )):
            self.add_error('agendamento_telefone', 'Informe ao menos um canal para agendamento.')
        return cleaned


class LocalImagemPrincipalForm(StyledModelForm):
    class Meta:
        model = LocalTuristico
        fields = (
            'imagem_principal', 'imagem_texto_alternativo', 'imagem_credito',
            'imagem_legenda', 'imagem_foco_horizontal', 'imagem_foco_vertical',
        )

    def clean_imagem_principal(self):
        arquivo = self.cleaned_data.get('imagem_principal')
        if arquivo and hasattr(arquivo, 'temporary_file_path') or getattr(arquivo, 'size', None):
            return validar_imagem_turismo(arquivo)
        return arquivo

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('imagem_principal') and not cleaned.get('imagem_texto_alternativo'):
            self.add_error('imagem_texto_alternativo', 'Informe um texto alternativo acessível.')
        for field in ('imagem_foco_horizontal', 'imagem_foco_vertical'):
            value = cleaned.get(field)
            if value is not None and not 0 <= value <= 100:
                self.add_error(field, 'Use um valor entre 0 e 100.')
        return cleaned


class LocalContatosForm(StyledModelForm):
    class Meta:
        model = LocalTuristico
        fields = ('telefone_publico', 'whatsapp_publico', 'email_publico', 'site')


class LocalRelacoesForm(StyledModelForm):
    roteiros = forms.ModelMultipleChoiceField(
        queryset=RoteiroTuristico.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    experiencias = forms.ModelMultipleChoiceField(
        queryset=ExperienciaTuristica.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    videos = forms.ModelMultipleChoiceField(
        queryset=TurismoVideo.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    playlists = forms.ModelMultipleChoiceField(
        queryset=TurismoPlaylist.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = LocalTuristico
        fields = (
            'empresa_responsavel', 'empresas_relacionadas', 'guias_relacionados',
            'responsavel_administrativo',
        )
        widgets = {
            'empresas_relacionadas': forms.CheckboxSelectMultiple,
            'guias_relacionados': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        empresas = empresas_disponiveis_para_usuario(usuario).filter(ativo=True)
        self.fields['empresa_responsavel'].queryset = empresas
        self.fields['empresas_relacionadas'].queryset = empresas
        if usuario_tem_permissao(usuario, 'TURISMO_GUIA_EDITAR_TODOS'):
            guias = GuiaTuristico.objects.filter(ativo=True).filter(
                Q(status=TurismoStatus.PUBLICADO) | Q(verificado=True),
            )
        else:
            guias = GuiaTuristico.objects.filter(
                ativo=True, usuario_criador=usuario,
            ).filter(Q(status=TurismoStatus.PUBLICADO) | Q(verificado=True))
        self.fields['guias_relacionados'].queryset = guias
        self.fields['responsavel_administrativo'].queryset = get_user_model().objects.filter(pk=usuario.pk)
        global_access = usuario_tem_permissao(usuario, 'TURISMO_LOCAL_EDITAR_TODOS')
        filters = {} if global_access else {'usuario_criador': usuario}
        self.fields['roteiros'].queryset = RoteiroTuristico.objects.filter(ativo=True, **filters)
        self.fields['experiencias'].queryset = ExperienciaTuristica.objects.filter(ativo=True, **filters)
        self.fields['videos'].queryset = TurismoVideo.objects.filter(ativo=True, **filters)
        self.fields['playlists'].queryset = TurismoPlaylist.objects.filter(ativo=True, **filters)
        if self.instance.pk:
            self.fields['roteiros'].initial = self.instance.roteiros.all()
            self.fields['experiencias'].initial = self.instance.experiencias.all()
            self.fields['videos'].initial = self.instance.videos.all()
            self.fields['playlists'].initial = self.instance.playlists.all()

    def _save_m2m(self):
        super()._save_m2m()
        local = self.instance
        selected = {
            'roteiros': self.cleaned_data['roteiros'],
            'experiencias': self.cleaned_data['experiencias'],
            'videos': self.cleaned_data['videos'],
            'playlists': self.cleaned_data['playlists'],
        }
        local.roteiros.clear()
        for item in selected['roteiros']:
            item.locais.add(local)
        self.fields['experiencias'].queryset.filter(local=local).exclude(
            pk__in=selected['experiencias'],
        ).update(local=None)
        selected['experiencias'].update(local=local)
        for name in ('videos', 'playlists'):
            self.fields[name].queryset.filter(local=local).exclude(
                pk__in=selected[name],
            ).update(local=None)
            selected[name].update(local=local)


class ContatoTurismoForm(StyledModelForm):
    publico = SimNaoField(label='Exibir este contato publicamente?')
    principal = SimNaoField(label='Este é o contato principal?', required=False)

    class Meta:
        model = ContatoTurismo
        fields = ('tipo', 'valor', 'nome_exibicao', 'publico', 'principal', 'ordem')

    def clean(self):
        cleaned = super().clean()
        tipo, valor = cleaned.get('tipo'), (cleaned.get('valor') or '').strip()
        if tipo in {ContatoTurismo.Tipo.SITE, ContatoTurismo.Tipo.AGENDAMENTO} and not valor.lower().startswith(('http://', 'https://')):
            self.add_error('valor', 'Informe uma URL iniciada por http:// ou https://.')
        if tipo == ContatoTurismo.Tipo.EMAIL:
            try:
                forms.EmailField().clean(valor)
            except forms.ValidationError:
                self.add_error('valor', 'Informe um e-mail válido.')
        if tipo in {ContatoTurismo.Tipo.TELEFONE, ContatoTurismo.Tipo.WHATSAPP}:
            digits = re.sub(r'\D', '', valor)
            if not 10 <= len(digits) <= 13:
                self.add_error('valor', 'Informe telefone ou WhatsApp com DDD.')
            else:
                cleaned['valor'] = f'+{digits}' if len(digits) > 11 else digits
        return cleaned


class RedeSocialTurismoForm(StyledModelForm):
    publico = SimNaoField(label='Exibir esta rede publicamente?')

    class Meta:
        model = RedeSocialTurismo
        fields = ('tipo', 'url', 'nome_exibicao', 'publico', 'ordem')


class LocalVideoForm(StyledModelForm):
    class Meta:
        model = TurismoVideo
        fields = ('titulo', 'descricao', 'url_youtube', 'ordem', 'destaque')


class LocalPlaylistForm(StyledModelForm):
    class Meta:
        model = TurismoPlaylist
        fields = ('titulo', 'slug', 'descricao', 'capa', 'url_youtube')
